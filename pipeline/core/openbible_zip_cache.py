"""Shared persistent zip cache for Biblica (Open Bible) text artifacts —
internal-data/api-cache/openbible/text-zips/<project_id>.zip, current-
version USFM only (the one format this repo's tooling actually uses).

Added 2026-09-16: earlier Biblica zip fetches (fetch_openbible_book_coverage.py,
fetch_sources.py's openbible_text()) were deliberately ephemeral (fetch to
memory/tmpdir, discard immediately) — the same "verdict-only, never retain"
discipline PKF's *comparison* fetches use. That discipline is about never
PUBLISHING source text, not about local caching — PKF already has a real
645MB persistent local cache for its own tooling (internal-data/api-cache/pkf/),
so there's no reason Biblica's much smaller ~378MB (553 current-version USFM
zips) shouldn't have the same. Nothing about this changes what gets
published — still verdict-only on the CDN side.
"""
import time
import urllib.request
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE  # noqa: E402

ZIP_CACHE_DIR = API_CACHE / "openbible" / "text-zips"
OPENBIBLE_API = "https://openbible-api-1.biblica.com"
USER_AGENT = "bibles-cdn-bibel-wiki-research/1.0 (+https://cdn.bibel.wiki; catalog research, low-rate)"
REQUEST_DELAY = 0.25
MAX_RETRIES = 4


def cached_zip_path(project_id: str) -> Path:
    return ZIP_CACHE_DIR / f"{project_id}.zip"


def get_zip_bytes(project_id: str, artifact_id: str) -> bytes | None:
    """Cache-first fetch of a text project's current-version USFM zip.
    Returns the raw zip bytes, or None on failure. Writes to the
    persistent cache on a real fetch; a cache hit does no network call."""
    path = cached_zip_path(project_id)
    if path.is_file():
        return path.read_bytes()

    delay = 2.0
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(f"{OPENBIBLE_API}/artifactContent/{artifact_id}",
                                          headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            time.sleep(REQUEST_DELAY)
            ZIP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return data
        except Exception as e:
            print(f"    [retry {attempt + 1}/{MAX_RETRIES}] {e}")
            time.sleep(delay)
            delay *= 2
    return None
