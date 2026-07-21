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

    for rel, info in current.items():
        old = old_state.get(rel)
        if old and old["size"] == info["size"] and old["mtime"] == info["mtime"]:
            continue
        if (rel.endswith("/media.json") or rel.endswith("/media-index.json")
                or rel in ("_vrs/index.json", "_vrs/irregular.json")):
            media_files.append(rel)
        else:
            timing_files.append(rel)

    # Detect deletions (in old state but not in current)
    deleted = set(old_state.keys()) - set(current.keys())
    if deleted:
        print(f"[INFO] {len(deleted)} files removed locally (will need manual CDN cleanup)")

    MEDIA_LIST.write_text("\n".join(sorted(media_files)) + "\n" if media_files else "")
    TIMING_LIST.write_text("\n".join(sorted(timing_files)) + "\n" if timing_files else "")

    total = len(media_files) + len(timing_files)
    print(f"[INFO] Delta: {len(media_files)} media.json, {len(timing_files)} timing files ({total} total)")

    if total == 0:
        print("[INFO] Nothing changed.")
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
