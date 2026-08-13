#!/usr/bin/env python3
"""Compute incremental delta for CDN publishing of export/dbt/.

Compares the local export/dbt/ tree against a state file
(export/.dbt-published.json) and emits --files-from lists for rclone.

State file format: { "<relative_path>": { "size": N, "mtime": T }, ... }

Usage:
    python scripts/cdn_dbt_delta.py [--state export/.dbt-published.json]

Writes to:
    export/.dbt-upload-media.txt    (media.json files, pass 1)
    export/.dbt-upload-timing.txt   (timing/*.json files, pass 2)

Two categories are computed but deliberately never written to an upload
list — held back, not silently dropped (see the [INFO] lines each prints):

- Per-book timing/<BOOK>.json (2026-08-12): the bulk of this data isn't
  real audio-sync alignment yet — data/align-cache (the actual audio-sync
  integration point) is empty; the overwhelming majority is DBT's own
  native timing plus a legacy manually-copied re-alignment set. Held back
  until that's sorted out. Re-enable by folding this bucket back into
  timing_files below.
- "other" DBT-root json that isn't media/timing shaped: _text-availability.json
  (explicitly held back pending an explicit publish decision, per
  examples/content-availability-confirmation.md) and _helloao-crosswalk.json
  (fine to publish, just caught in the same net) both land here rather
  than in timing_files, since neither is timing data — the old bucketing
  put them there only because "not media-shaped" was the sole test.
  _app/catalog-{index,overlap,text,audio}.json are also caught here: these
  are stale, orphaned pre-2026-08-11 duplicates that nothing generates
  anymore (superseded by export/catalog/) — never intended to be
  published from this path again; consider deleting them from
  export/dbt/_app/ locally instead of just excluding them here.

Exit code 0 = files to upload, exit code 2 = nothing changed.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import EXPORT  # noqa: E402

SOURCE_DIR = EXPORT / "dbt"
STATE_FILE = EXPORT / ".dbt-published.json"
MEDIA_LIST = EXPORT / ".dbt-upload-media.txt"
TIMING_LIST = EXPORT / ".dbt-upload-timing.txt"

# Old, no-longer-generated duplicates from the pre-2026-08-11 /catalog/
# migration. Never publish these from here again.
STALE_APP_CATALOG_FILES = {
    "_app/catalog-index.json",
    "_app/catalog-overlap.json",
    "_app/catalog-text.json",
    "_app/catalog-audio.json",
}
# Not timing data, but also not ready/decided to publish yet — see module
# docstring.
HELD_BACK_OTHER_FILES = {
    "_text-availability.json",
    "_helloao-crosswalk.json",
}


def load_state(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_state(path: Path, state: dict):
    with open(path, "w") as f:
        json.dump(state, f, separators=(",", ":"), sort_keys=True)


def scan_source(source_dir: Path) -> dict:
    """Scan source directory and return {relpath: {size, mtime}}."""
    result = {}
    for p in sorted(source_dir.rglob("*.json")):
        rel = str(p.relative_to(source_dir))
        st = p.stat()
        result[rel] = {"size": st.st_size, "mtime": st.st_mtime}
    return result


def main():
    if not SOURCE_DIR.is_dir():
        print("[ERROR] export/dbt/ not found. Run generate_audio_metadata.py and generate_timing_by_book.py first.")
        sys.exit(1)

    old_state = load_state(STATE_FILE)
    current = scan_source(SOURCE_DIR)

    media_files = []
    timing_files = []
    held_back_timing = []
    held_back_other = []
    stale_app_catalog = []

    for rel, info in current.items():
        old = old_state.get(rel)
        if old and old["size"] == info["size"] and old["mtime"] == info["mtime"]:
            continue
        if (rel.endswith("/media.json") or rel.endswith("/media-index.json")
                or rel in ("_vrs/index.json", "_vrs/irregular.json")):
            media_files.append(rel)
        elif rel in STALE_APP_CATALOG_FILES:
            stale_app_catalog.append(rel)
        elif rel in HELD_BACK_OTHER_FILES:
            held_back_other.append(rel)
        elif "/timing/" in rel:
            held_back_timing.append(rel)
        else:
            timing_files.append(rel)

    # Detect deletions (in old state but not in current)
    deleted = set(old_state.keys()) - set(current.keys())
    if deleted:
        print(f"[INFO] {len(deleted)} files removed locally (will need manual CDN cleanup)")

    MEDIA_LIST.write_text("\n".join(sorted(media_files)) + "\n" if media_files else "")
    TIMING_LIST.write_text("\n".join(sorted(timing_files)) + "\n" if timing_files else "")

    if held_back_timing:
        print(f"[INFO] {len(held_back_timing)} per-book timing files changed but held back "
              "(not real audio-sync data yet) — not written to any upload list.")
    if held_back_other:
        print(f"[INFO] {len(held_back_other)} file(s) held back pending an explicit publish "
              f"decision: {sorted(held_back_other)}")
    if stale_app_catalog:
        print(f"[INFO] {len(stale_app_catalog)} stale _app/catalog-*.json file(s) excluded "
              "(orphaned pre-2026-08-11 duplicates — consider deleting locally): "
              f"{sorted(stale_app_catalog)}")

    total = len(media_files) + len(timing_files)
    print(f"[INFO] Delta: {len(media_files)} media.json, {len(timing_files)} other timing-bucket files ({total} total to upload)")

    if total == 0:
        print("[INFO] Nothing changed.")
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
