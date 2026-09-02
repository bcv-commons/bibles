#!/usr/bin/env python3
"""Resolve door43 OBS repo detail — content base URL, license, checking
level, real story count, AND resolved per-story audio URLs — directly
from door43's own catalog API, for EVERY OBS language (text-only or
audio-bearing alike).

Originally built text-only-only (fetch_obs_text_repos.py), on the
assumption audio-bearing languages' detail would come from audio-sync's
_obs_batches/<iso>.json staging manifests instead. That assumption caused
a real, reported gap: audio-sync's align/obs/ alignment output reached 14
languages while _obs_batches/ staging had only reached 1 — so
media.json (the discovery layer clients actually use) made 13 languages
with real, live timing data invisible. Root cause: media.json's audio
detail was needlessly gated on a *staging* pipeline's pace instead of
being resolved directly from origin, the same principle already applied
to the existence signal (catalog-obs-index.json) and text-only detail.

Fix: resolve audio here too. Verified door43 release assets already carry
the exact same per-story audio files audio-sync's staging resolves,
consistently named `<repo>_obs_v<version>_<NN>_<bitrate>kbps.m4a` across
languages and door43 orgs (checked ahr/hoc/bee/bfw/mai/sat/awa/bfy) — no
separate resolution step needed, no dependency on _obs_batches/ at all.
An asset list with zero audio-pattern matches (e.g. an "Android App"-only
release) naturally makes a language audio-less here even if door43's
hasAudio stats flag it — a real, useful cross-check on that flag rather
than a source of false positives.

Per language: one catalog/search call (repo identity, content path,
release ref + assets, manifest raw URL), one manifest fetch (license via
`rights:`, checking level via `checking_level:` — small targeted regex,
not a full YAML parse, to avoid a PyYAML dependency for two scalar
fields), one contents-listing call (real story count).

Older `ts-desktop`-format repos (17 of 214, mostly the `fa_gl` door43 org —
see doc/catalog-obs.md's "known gap" note) don't fit that shape at all:
their manifest.json has no `dublin_core.rights`/`checking.checking_level`
fields, and content lives at `<story>/<chunk>.txt` per chunk rather than
one `<story>.md` file — confirmed directly against `ar-xzn_obs`'s real
repo tree. Two fallbacks close this, both triggered only when the primary
path finds nothing (never override a real value):
  - **Stories**: when the `NN.md` scan finds zero files, check the same
    listing for `NN`-named subdirectories instead — each one's real title
    lives at `<content_base_url>/<NN>/title.txt`, recorded per-story in
    `titleUrls` (fetch_obs_titles.py fetches from there directly; the
    plain `.md` layout also gets a `titleUrls` entry, both layouts are
    handled uniformly downstream).
  - **License**: when `rights:` isn't found in the manifest, try the
    repo's `LICENSE.md` (confirmed present on the `ts-desktop` repos
    checked) for a `creativecommons.org/licenses/<type>/<version>` URL,
    the standard CC self-description every OBS license text seems to
    include regardless of manifest format.
`checking_level` has no reliable fallback for this format (the manifest's
only checking-level-shaped field describes the *source* text being
translated from, not this translation's own) — stays `null`.

Resumable: skips any iso already present in the cache unless --refresh.

Usage:
    python3 pipeline/core/fetch_obs_repos.py             # fetch new isos only
    python3 pipeline/core/fetch_obs_repos.py --refresh    # re-fetch everything
    python3 pipeline/core/fetch_obs_repos.py --limit 5    # cap for testing
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import OBS_DOOR43_CATALOG_FILE, OBS_REPOS_FILE  # noqa: E402

SEARCH_URL = "https://git.door43.org/api/v1/catalog/search?subject=Open%20Bible%20Stories&lang={iso}&stage=prod"
STORY_FILE_RE = re.compile(r"^(\d{2})\.md$")
STORY_DIR_RE = re.compile(r"^(\d{2})$")
AUDIO_ASSET_RE = re.compile(r"_obs_v\d+_(\d{2})_\d+kbps\.\w+$")
RIGHTS_RE = re.compile(r"^\s*rights:\s*['\"]?([^'\"\n]+)['\"]?\s*$", re.MULTILINE)
CHECKING_LEVEL_RE = re.compile(r"^\s*checking_level:\s*['\"]?(\d+)['\"]?\s*$", re.MULTILINE)
CC_LICENSE_RE = re.compile(r"creativecommons\.org/licenses/([a-z-]+)/(\d(?:\.\d+)?)")


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_text(url: str) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def resolve_audio(entry: dict) -> dict:
    assets = (entry.get("release") or {}).get("assets", [])
    audio = {}
    for a in assets:
        m = AUDIO_ASSET_RE.search(a.get("name", ""))
        if m:
            audio[m.group(1)] = a["browser_download_url"]
    return audio


def resolve_license_fallback(full_name: str, ref: str) -> str | None:
    """LICENSE.md's CC self-description URL, for repos whose manifest has no `rights:` field."""
    text = fetch_text(f"https://git.door43.org/{full_name}/raw/tag/{ref}/LICENSE.md")
    if not text:
        return None
    m = CC_LICENSE_RE.search(text)
    return f"CC {m.group(1).upper()} {m.group(2)}" if m else None


def resolve_one(iso: str) -> dict | None:
    search = fetch_json(SEARCH_URL.format(iso=iso))
    entries = search.get("data") or []
    if not entries:
        return None
    entry = entries[0]  # first prod entry; a language with >1 repo (rare) just uses the first

    full_name = entry["full_name"]
    ref = entry.get("branch_or_tag_name") or entry["release"]["tag_name"]
    ingredient = next((i for i in entry.get("ingredients", []) if i.get("identifier") == "obs"), None)
    content_path = (ingredient or {}).get("path", "./content").lstrip("./")
    content_base_url = f"https://git.door43.org/{full_name}/raw/tag/{ref}/{content_path}"

    manifest_text = fetch_text(entry["metadata_url"]) or ""
    rights_match = RIGHTS_RE.search(manifest_text)
    level_match = CHECKING_LEVEL_RE.search(manifest_text)
    license_value = rights_match.group(1).strip() if rights_match else None

    contents = fetch_json(f"https://git.door43.org/api/v1/repos/{full_name}/contents/{content_path}?ref={ref}")
    story_ids = sorted(m.group(1) for f in contents if (m := STORY_FILE_RE.match(f.get("name", ""))))
    title_urls = {sid: f"{content_base_url}/{sid}.md" for sid in story_ids}
    content_layout = "md"

    collection_title = None
    if not story_ids:
        # Older ts-desktop layout fallback: <story>/<chunk>.txt per chunk,
        # title at <story>/title.txt — see module docstring.
        story_ids = sorted(
            m.group(1) for f in contents
            if f.get("type") == "dir" and (m := STORY_DIR_RE.match(f.get("name", "")))
        )
        title_urls = {sid: f"{content_base_url}/{sid}/title.txt" for sid in story_ids}
        content_layout = "ts-desktop"
        if license_value is None:
            license_value = resolve_license_fallback(full_name, ref)
        # This layout also carries a real translated collection title
        # (the vernacular equivalent of "Open Bible Stories" itself) at
        # front/title.txt — confirmed against ar-xzn_obs. The standard
        # .md layout has no equivalent anywhere (content/ is always just
        # 01.md-50.md, manifest `title:` is always the fixed English
        # string, README.md is boilerplate) — checked directly, genuinely
        # nothing to fetch there, not left out by oversight.
        collection_title_text = fetch_text(f"{content_base_url}front/title.txt")
        collection_title = collection_title_text.strip() if collection_title_text else None

    return {
        "iso": iso,
        "source": entry.get("owner"),
        "source_repo": full_name,
        "content_base_url": content_base_url,
        "contentLayout": content_layout,
        "collectionTitle": collection_title,
        "license": license_value,
        "checking_level": level_match.group(1) if level_match else None,
        "storyIds": story_ids,
        "titleUrls": title_urls,
        "audio": resolve_audio(entry),
    }


def main():
    args = sys.argv[1:]
    refresh = "--refresh" in args
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None

    if not OBS_DOOR43_CATALOG_FILE.exists():
        print("[fetch-obs-repos] door43 catalog cache not found. Run: make fetch-obs-catalog")
        return
    door43 = json.loads(OBS_DOOR43_CATALOG_FILE.read_text())
    all_isos = sorted(door43.get("languages_all", {}).keys())

    cache = json.loads(OBS_REPOS_FILE.read_text()) if OBS_REPOS_FILE.exists() else {}
    todo = all_isos if refresh else [iso for iso in all_isos if iso not in cache]
    if limit:
        todo = todo[:limit]

    if not todo:
        print(f"[fetch-obs-repos] {len(cache)} cached, nothing new to fetch.")
        return

    print(f"[fetch-obs-repos] resolving {len(todo)} of {len(all_isos)} language(s)...")
    resolved, failed = 0, 0
    for i, iso in enumerate(todo, 1):
        try:
            detail = resolve_one(iso)
        except Exception as e:  # noqa: BLE001 - one bad repo/network hiccup shouldn't lose the whole run
            print(f"  [{i}/{len(todo)}] {iso}: FAILED ({type(e).__name__}: {e})", file=sys.stderr)
            failed += 1
            continue
        if detail is None:
            print(f"  [{i}/{len(todo)}] {iso}: no prod catalog entry found")
            failed += 1
            continue
        cache[iso] = detail
        resolved += 1
        # Flush every item — population is a few hundred at most, so the
        # cost is negligible next to losing progress to a mid-run hiccup
        # (~3 door43 API calls per language, sequentially).
        OBS_REPOS_FILE.parent.mkdir(parents=True, exist_ok=True)
        OBS_REPOS_FILE.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
        if i % 20 == 0 or i == len(todo):
            print(f"  [{i}/{len(todo)}] progress: {resolved} resolved, {failed} failed")

    print(f"[fetch-obs-repos] done: {resolved} resolved, {failed} failed -> {OBS_REPOS_FILE}")


if __name__ == "__main__":
    main()
