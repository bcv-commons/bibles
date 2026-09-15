#!/usr/bin/env python3
"""Fetch Biblica's Open Bible catalog into a local cache.

Source: https://openbible-api-1.biblica.com — the real backing API behind
both open.bible's website (blocked to automated fetches by a Cloudflare
challenge — not attempted here) and yaapi.bible (a curated, text-only,
452-version subset of what's actually there: 1,909 versions, 943
projects, 19,069 artifacts including 14,086 real per-book MP3 files and
841 real per-book Timing files, confirmed live 2026-09-15).

Three-phase, all resumable and rate-limited (no documented rate limit
found, so REQUEST_DELAY below is a conservative default, not a known
threshold — back off further if 429s ever appear in practice):

  Phase 1 — ALL projects (~943, ~10 paginated requests: /projects itself
  returns 100 at a time). Projects already carry real language/title/type
  metadata directly (`type`: "text"/"audio"/"video", `languageCode` real
  ISO 639-3, `title`/`titleEnglish`, `audioPageUrl`) — cheap and by far
  the most useful signal on its own.

  Phase 2 — for `type: "audio"` projects only (~357, not all 1,909
  versions or 19,069 artifacts): walk /projects/{id}/versions then
  /versions/{id}/artifacts to confirm REAL uploaded content (a project's
  `type` alone doesn't guarantee artifacts actually exist — some are
  `disabled`/`contentUpdateRequired`) and collect real book-level
  coverage, same shape this repo already uses elsewhere (classify()'s
  TEXT/AUDIO/TIMED matrix).

  Phase 3 — for `type: "text"` projects only (~554): same walk, but text
  artifacts are per-EDITION zips (one artifact = the whole Bible, 66
  USFM/USX files inside — confirmed live 2026-09-15), not per-book like
  audio, so there is no book-level coverage to compute here — just the
  real artifact id/format/fileSize/license per version, enough to link
  to (`artifactContent/<id>`, confirmed a real, direct, no-auth,
  CloudFront-served download) without mirroring the content.

Output:
    internal-data/api-cache/openbible/projects.json       (phase 1, all ~943)
    internal-data/api-cache/openbible/audio/<project_id>.json  (phase 2, per audio project)
    internal-data/api-cache/openbible/text/<project_id>.json   (phase 3, per text project)

Usage:
    python3 pipeline/core/fetch_openbible_cache.py             # all phases
    python3 pipeline/core/fetch_openbible_cache.py --projects-only
    python3 pipeline/core/fetch_openbible_cache.py --force     # re-fetch phases 2+3 even if cached
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE  # noqa: E402

BASE = "https://openbible-api-1.biblica.com"
PROJECTS_FILE = API_CACHE / "openbible" / "projects.json"
AUDIO_DIR = API_CACHE / "openbible" / "audio"
TEXT_DIR = API_CACHE / "openbible" / "text"

# Honest identification (this API isn't blocking/hostile, unlike open.bible's
# own frontend — no reason to masquerade as a browser here).
USER_AGENT = "bibles-cdn-bibel-wiki-research/1.0 (+https://cdn.bibel.wiki; catalog research, low-rate)"
REQUEST_DELAY = 0.25  # seconds between requests — conservative default, no published limit found
MAX_RETRIES = 4


def fetch_json(url: str) -> dict:
    """GET with exponential backoff on failure (429s or transient errors)."""
    delay = 2.0
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
            time.sleep(REQUEST_DELAY)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                print(f"    [retry {attempt + 1}/{MAX_RETRIES}] {e.code} on {url}, backing off {delay:.0f}s")
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"    [retry {attempt + 1}/{MAX_RETRIES}] {e} on {url}, backing off {delay:.0f}s")
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"Giving up on {url} after {MAX_RETRIES} retries")


def fetch_all_pages(path: str, embedded_key: str) -> list:
    items = []
    page = 0
    total_pages = None
    while total_pages is None or page < total_pages:
        d = fetch_json(f"{BASE}/{path}?page={page}&size=100")
        items.extend(d.get("_embedded", {}).get(embedded_key, []))
        if total_pages is None:
            total_pages = d["page"]["totalPages"]
            print(f"  {path}: {d['page']['totalElements']} total, {total_pages} page(s)")
        page += 1
    return items


def fetch_projects():
    if PROJECTS_FILE.exists():
        print(f"[fetch-openbible] {PROJECTS_FILE} already exists, skipping phase 1 (delete to re-fetch)")
        return json.loads(PROJECTS_FILE.read_text())
    print("[fetch-openbible] phase 1: fetching all projects...")
    projects = fetch_all_pages("projects", "projects")
    PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROJECTS_FILE.write_text(json.dumps(projects, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"[fetch-openbible] phase 1: {len(projects)} project(s) -> {PROJECTS_FILE}")
    return projects


def fetch_project_detail(project: dict, kind: str) -> dict:
    """Real versions + artifacts for one project — confirms actual uploaded
    content rather than trusting `type` alone.

    kind="audio": artifacts are per-BOOK zips -> compute real book-level
    coverage + timing presence, same shape classify() uses elsewhere.
    kind="text": artifacts are per-EDITION zips (whole Bible in one zip,
    confirmed live 2026-09-15) -> no book coverage to compute; just record
    the real artifact id/format/fileSize/license so it can be linked to
    (`artifactContent/<id>`) without mirroring the content.
    """
    versions_url = project["_links"]["versions"]["href"]
    versions = fetch_json(versions_url).get("_embedded", {}).get("versions", [])
    result: dict = {"project": project, "versions": []}
    for v in versions:
        # NOTE: version objects returned by this per-project sub-resource carry
        # no `_links` at all (confirmed live 2026-09-15) — unlike the flat
        # /versions collection, whose entries do carry `_links.artifacts.href`.
        # Construct the artifacts URL directly from the version id instead
        # (confirmed correct via direct curl against a known-real version id).
        vid = v.get("id")
        artifacts = fetch_json(f"{BASE}/versions/{vid}/artifacts").get("_embedded", {}).get("artifacts", []) if vid else []
        entry = {
            "id": v.get("id"), "current": v.get("current"),
            "processingComplete": v.get("processingComplete"),
            "licenses": v.get("licenses"),
        }
        if kind == "audio":
            books = sorted({a["bookCode"] for a in artifacts if a.get("bookCode") and a.get("format") == "MP3"})
            has_timing = any(a.get("format") == "Timing" for a in artifacts)
            entry["audioBooks"] = books
            entry["hasTiming"] = has_timing
        else:
            entry["artifacts"] = [
                {
                    "id": a.get("id"), "format": a.get("format"), "mimeType": a.get("mimeType"),
                    "fileName": a.get("fileName"), "fileSize": a.get("fileSize"),
                }
                for a in artifacts
            ]
        result["versions"].append(entry)
    return result


def fetch_details(projects: list, kind: str, out_dir: Path, force: bool):
    matching = [p for p in projects if p.get("type") == kind and not p.get("disabled")]
    label = "2" if kind == "audio" else "3"
    print(f"[fetch-openbible] phase {label}: {len(matching)} non-disabled {kind} project(s)")
    out_dir.mkdir(parents=True, exist_ok=True)

    done, failed = 0, 0
    for i, p in enumerate(matching):
        out = out_dir / f"{p['id']}.json"
        if out.exists() and not force:
            done += 1
            continue
        try:
            detail = fetch_project_detail(p, kind)
        except Exception as e:
            print(f"  [{i + 1}/{len(matching)}] FAILED {p.get('titleEnglish', p['id'])}: {e}")
            failed += 1
            continue
        out.write_text(json.dumps(detail, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        done += 1
        if (i + 1) % 25 == 0:
            print(f"  ...{i + 1}/{len(matching)} processed")

    print(f"[fetch-openbible] phase {label}: {done} cached, {failed} failed (re-run to retry failures) -> {out_dir}")


def main():
    force = "--force" in sys.argv
    projects_only = "--projects-only" in sys.argv

    projects = fetch_projects()
    if not projects_only:
        fetch_details(projects, "audio", AUDIO_DIR, force)
        fetch_details(projects, "text", TEXT_DIR, force)


if __name__ == "__main__":
    main()
