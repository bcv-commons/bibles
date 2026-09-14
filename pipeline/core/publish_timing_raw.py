#!/usr/bin/env python3
"""Republish bibles' own raw timing sources (BB, contrib, legacy-timing-data)
under /dbt/<iso>/timing-raw/<source>/... unchanged, at the fixed path the
published standard (doc/dbt-timing.md) defines.

Replaces generate_timing_index.py (2026-09-14): that script also built a
per-audioFileset pointer index (timing/<audioFileset>.json) resolving
which source wins per chapter and pointing at audio-sync's live align/
tree. Neither is needed anymore — audio-sync's own manifests now carry a
mandatory `audio_fileset` field and `status: "ok"` already IS the
existence signal (confirmed 2026-09-14), so the real URL for any given
chapter is a pure formula a client (or us) computes directly from data
audio-sync already delivers, nothing to resolve or publish on our side.

What bibles is still the only host for — these three raw sources, since
no external producer serves them — is unchanged: republish the file
byte-for-byte at the documented path, nothing more. `has_timing` for
media.json's classification and generate_sync_candidates.py's dedup is
answered separately, straight from timing_index.load_resolved()
(this repo's own owned sources scanned directly + audio-sync's manifest
digest) — that's internal bookkeeping, not something this script needs
to produce.

Output: export/dbt/<iso>/timing-raw/<source>/<canon>/<abbr>/<book>/
        <book>_<chapter>_<audioFileset>_timing.json  (byte-identical copy)

Usage:
    python3 pipeline/core/publish_timing_raw.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import EXPORT, TIMING_DIR, LEGACY_TIMING_DIR  # noqa: E402

OUTPUT_DIR = EXPORT / "dbt"

# (source name, local base dir) — matches doc/dbt-timing.md's documented
# source list for the two sources with no external producer.
LOCAL_SOURCES = [
    ("BB", TIMING_DIR / "BB"),
    ("contrib", TIMING_DIR / "contrib"),
    ("legacy", LEGACY_TIMING_DIR),
]


def parse_timing_file(tf: Path, base: Path):
    """(canon, iso, abbr, book) from a raw path shaped
    <base>/<canon>/<iso>/<abbr>/<BOOK>/<BOOK>_<CH>_<audioFileset>_timing.json."""
    try:
        parts = tf.relative_to(base).parts
    except ValueError:
        return None
    if len(parts) < 5:
        return None
    return parts[0], parts[1], parts[2], parts[3]


def main():
    from version_exclude import load_excludes, excluded_set
    excluded = excluded_set(load_excludes(), scope="align")

    # Clean prior output before writing fresh (source files can be renamed/
    # removed upstream; a stale copy here would otherwise never go away).
    if OUTPUT_DIR.exists():
        for iso_dir in OUTPUT_DIR.iterdir():
            d = iso_dir / "timing-raw"
            if d.is_dir():
                shutil.rmtree(d)

    files_copied, files_skipped = 0, 0
    for source, base in LOCAL_SOURCES:
        if not base.exists():
            continue
        for tf in base.rglob("*_timing.json"):
            parsed = parse_timing_file(tf, base)
            if not parsed:
                continue
            canon, iso, abbr, book = parsed
            if (iso, abbr) in excluded:
                files_skipped += 1
                continue
            dest = OUTPUT_DIR / iso / "timing-raw" / source / canon / abbr / book / tf.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(tf, dest)
            files_copied += 1

    print(f"[publish-timing-raw] {files_copied} file(s) republished, "
          f"{files_skipped} skipped (version-excluded) -> export/dbt/<iso>/timing-raw/")


if __name__ == "__main__":
    main()
