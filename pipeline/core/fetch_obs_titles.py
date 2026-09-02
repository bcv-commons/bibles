#!/usr/bin/env python3
"""Fetch per-story vernacular titles for /obs/<iso>/media.json's `stories`
entries — a client-requested field (2026-09-01) for a browse/category grid
that needs a real title per story without fetching all 50 full stories
per language itself.

This is deliberately the ONE place this pipeline fetches real story
CONTENT, not just existence/routing metadata — every other OBS script
(fetch_obs_catalog.py, fetch_obs_repos.py) stays strictly at the
existence/routing layer. Checked first whether that could stay true here
too: door43's raw content endpoint does NOT honor HTTP Range requests
(verified — a `Range: bytes=0-100` request still returns the full file,
HTTP 200 not 206), so there's no way to fetch just a title line without
pulling the whole story. Each story's first line is therefore fetched
here — reading a `.md` file stops after its first line (a stream read,
not a full download) — but only that line is ever kept, the rest is
discarded immediately in memory, never written to disk, same "resolve
display metadata, not content" spirit as catalog-books.json's vernacular
book names (an existing precedent for exactly this kind of exception).

Where to fetch from, per story, comes from fetch_obs_repos.py's resolved
`titleUrls` — usually `<content_base_url>/<NN>.md` (standard OBS layout,
title is the first line's `# N. Title`/`# Title` heading), but a `.txt`
per-story-title-file layout for a handful of older `ts-desktop`-format
repos (`<content_base_url>/<NN>/title.txt` — title IS the file's one
line, no `#` heading involved). Both layouts get the same leading
`#`/number-prefix strip applied, so this script doesn't need to know
which layout it's looking at.

Population: every story in every language's `titleUrls` (from
fetch_obs_repos.py's cache) — title applies regardless of whether a
language has audio, so this covers every language with a resolved story
layout (214 minus any still-unresolved edge cases). ~10,000 requests
total; run with a thread pool (network-bound, door43 has no documented
rate limit but --workers is tunable if one shows up).

Resumable: skips any (iso, story_id) already cached unless --refresh.

Usage:
    python3 pipeline/core/fetch_obs_titles.py               # fetch new only
    python3 pipeline/core/fetch_obs_titles.py --refresh      # re-fetch everything
    python3 pipeline/core/fetch_obs_titles.py --workers 20   # default 15
"""
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import OBS_REPOS_FILE, OBS_TITLES_FILE  # noqa: E402

# Strips an optional leading `#`(s) (markdown heading marker) and an
# optional leading story-number prefix in front of the real title text.
# Handles all three formats seen in practice: "# 1. Title" (most repos),
# "# Title" (no number, e.g. bn_obs), and "1- Title" (ts-desktop
# title.txt files, no `#` at all, dash separator, and the story number
# can be in any script's digits — \d matches Arabic-Indic etc. under
# Python's default Unicode mode, not just ASCII 0-9).
CLEAN_TITLE_RE = re.compile(r"^#*\s*(?:\d+[.\-:]?\s*)?")


def fetch_title(url: str) -> str | None:
    """Read the first non-empty line and strip it down to just the title."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            title = CLEAN_TITLE_RE.sub("", line, count=1).strip()
            return title or None
    return None


def main():
    args = sys.argv[1:]
    refresh = "--refresh" in args
    workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 15

    if not OBS_REPOS_FILE.exists():
        print("[fetch-obs-titles] obs-repos.json not found. Run: make fetch-obs-repos")
        return
    repos = json.loads(OBS_REPOS_FILE.read_text())

    cache = json.loads(OBS_TITLES_FILE.read_text()) if OBS_TITLES_FILE.exists() else {}
    lock = Lock()

    jobs = []  # (iso, story_id, url)
    for iso, detail in repos.items():
        cached_iso = cache.get(iso, {})
        for sid, url in detail.get("titleUrls", {}).items():
            if not refresh and sid in cached_iso:
                continue
            jobs.append((iso, sid, url))

    if not jobs:
        total_cached = sum(len(v) for v in cache.values())
        print(f"[fetch-obs-titles] {total_cached} title(s) cached, nothing new to fetch.")
        return

    print(f"[fetch-obs-titles] fetching {len(jobs)} title(s) across {workers} worker(s)...")

    def do_one(job):
        iso, sid, url = job
        try:
            return iso, sid, fetch_title(url), None
        except Exception as e:  # noqa: BLE001 - one bad story shouldn't kill the batch
            return iso, sid, None, f"{type(e).__name__}: {e}"

    done, failed = 0, 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(do_one, job) for job in jobs]
        for i, fut in enumerate(as_completed(futures), 1):
            iso, sid, title, err = fut.result()
            if err or title is None:
                failed += 1
                if err:
                    print(f"  {iso}/{sid}: FAILED ({err})", file=sys.stderr)
            else:
                with lock:
                    cache.setdefault(iso, {})[sid] = title
                done += 1
            if i % 200 == 0 or i == len(jobs):
                with lock:
                    OBS_TITLES_FILE.parent.mkdir(parents=True, exist_ok=True)
                    OBS_TITLES_FILE.write_text(json.dumps(cache, ensure_ascii=False, sort_keys=True), encoding="utf-8")
                print(f"  [{i}/{len(jobs)}] {done} resolved, {failed} failed")

    OBS_TITLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    OBS_TITLES_FILE.write_text(json.dumps(cache, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(f"[fetch-obs-titles] done: {done} resolved, {failed} failed -> {OBS_TITLES_FILE}")


if __name__ == "__main__":
    main()
