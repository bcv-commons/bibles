#!/usr/bin/env python3
"""Compute incremental delta for CDN publishing of export/dbt/.

Compares the local export/dbt/ tree against a state file
(export/.dbt-published.json) and emits --files-from lists for rclone.

State file format: { "<relative_path>": { "size": N, "mtime": T }, ... }

Usage:
    python scripts/cdn_dbt_delta.py [--state export/.dbt-published.json]

Writes to:
    export/.dbt-upload-media.txt    (media.json files, pass 1)
    export/.dbt-upload-timing.txt   (everything else — coverage.json,
                                      sync-candidates.json, timing-raw/**,
                                      etc. — pass 2; the name predates
                                      several of these, kept for stability)

Two categories are computed but deliberately never written to an upload
list (see the [INFO] lines each prints):

- HELD_BACK_OTHER_FILES: _text-availability.json (explicitly held back
  pending an explicit publish decision, per
  examples/content-availability-confirmation.md) and _helloao-crosswalk.json
  (fine to publish, just caught in the same net) — genuinely held back,
  not excluded permanently.
- STALE_APP_CATALOG_FILES: _app/catalog-{index,overlap,text,audio}.json —
  stale, orphaned pre-2026-08-11 duplicates that nothing generates anymore
  (superseded by export/catalog/), never intended to be published from
  this path again; consider deleting them from export/dbt/_app/ locally
  instead of just excluding them here.

timing-raw/** (bibles' own BB/contrib/legacy sources, republished
byte-for-byte by publish_timing_raw.py) was held back the same way from
2026-08-12 until 2026-09-12, back when this bucket was instead a
per-book merge with no way to tell DBT-native/legacy timing apart from
real audio-sync alignment in the output alone. That merge — and later a
short-lived pointer-index replacement for it — is retired: audio-sync's
own align/_runs/ manifests now carry a mandatory `audio_fileset` field
and `status: "ok"` already IS the existence signal, so the real URL for
any audio-sync-aligned chapter is a pure formula from their manifests
directly (see doc/dbt-timing.md) — nothing for bibles to publish for
that part at all. timing-raw/** publishes normally now (falls into
timing_files below, no special-casing) since it's just bibles' own raw
files at a fixed path, same as media.json always was.

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
        print("[ERROR] export/dbt/ not found. Run generate_audio_metadata.py and publish_timing_raw.py first.")
        sys.exit(1)

    old_state = load_state(STATE_FILE)
    current = scan_source(SOURCE_DIR)

    media_files = []
    timing_files = []
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
        else:
            timing_files.append(rel)

    # Detect deletions (in old state but not in current)
    deleted = set(old_state.keys()) - set(current.keys())
    if deleted:
        print(f"[INFO] {len(deleted)} files removed locally (will need manual CDN cleanup)")

    MEDIA_LIST.write_text("\n".join(sorted(media_files)) + "\n" if media_files else "")
    TIMING_LIST.write_text("\n".join(sorted(timing_files)) + "\n" if timing_files else "")

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
