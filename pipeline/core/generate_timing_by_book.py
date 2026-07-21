#!/usr/bin/env python3
"""Generate /dbt/<iso>/timing/<BOOK>.json from the full timing data.

Reads raw timing files from all sources (data/timing/BB, data/timing/contrib,
data/timing/helloao/aligned, data/legacy-timing-data, data/align-cache),
converts start-only timestamps to [start, end] pairs, and writes one file per
(iso, book) merging all audio filesets.

Sources are listed lowest-to-highest priority: later sources in the list
override earlier ones on conflicting (iso, book, audioFileset, chapter,
verse) keys. `data/align-cache` (pulled from cdn.bibel.wiki/align/ by
scripts/pull_align_cache.py — audio-sync's Contract B output) is last,
alongside data/legacy-timing-data (MONO's manually-copied re-alignment
runs, kept as a fallback until a real audio-sync batch has been verified
to reproduce it — see CLAUDE.local.md), since both represent the most
recent re-alignment data. See internal-docs/audio-sync-interface.md
(MONO) §3.

Output: export/dbt/<iso>/timing/<BOOK>.json

Format per the CDN contract (example/plan-docs/schema/timing.schema.json):
  { "iso": "ind", "book": "JHN",
    "<audioFileset>": { "<chapter>": { "<verse>": [start, end] } } }
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import EXPORT, TIMING_DIR, LEGACY_TIMING_DIR, ALIGN_CACHE_DIR  # noqa: E402

OUTPUT_DIR = EXPORT / "dbt"

TIMING_SOURCES = [
    TIMING_DIR / "BB",
    TIMING_DIR / "contrib",
    TIMING_DIR / "helloao" / "aligned",
    LEGACY_TIMING_DIR,
    ALIGN_CACHE_DIR,
]

ANCHORS = ("BB", "contrib", "aligned", "legacy-timing-data", "align-cache")


def convert_to_pairs(timing_rows: list[dict]) -> dict[str, list[float]]:
    """Convert start-only timing rows to {verse: [start, end]} pairs.

    Input: list of {verse_start, timestamp} dicts (one chapter).
    Output: {verse_num_str: [start_sec, end_sec]}.
    End of each verse = start of the next; last verse end = its own start
    (consumer should use audio duration).
    """
    # Filter to actual verses (skip verse 0 / headers for end-time calc)
    entries = []
    for row in timing_rows:
        vs = row.get("verse_start", "0")
        ts = float(row.get("timestamp", 0))
        entries.append((vs, ts))

    # Sort by timestamp
    entries.sort(key=lambda x: x[1])

    # Build [start, end] pairs
    result = {}
    for i, (vs, ts) in enumerate(entries):
        if vs == "0":
            continue
        # End = next entry's timestamp, or this entry's timestamp if last
        if i + 1 < len(entries):
            end = entries[i + 1][1]
        else:
            end = ts
        result[vs] = [round(ts, 3), round(end, 3)]

    return result


def parse_timing_path(tf: Path):
    """Extract (canon, iso, distinct_id, book, chapter, audio_fileset) from path."""
    parts = tf.parts
    for anchor in ANCHORS:
        if anchor in parts:
            idx = parts.index(anchor)
            if idx + 4 < len(parts):
                canon = parts[idx + 1]
                iso = parts[idx + 2]
                distinct_id = parts[idx + 3]
                book_dir = parts[idx + 4]

                name = tf.stem.replace("_timing", "")
                name_parts = name.split("_", 2)
                if len(name_parts) >= 3:
                    book = name_parts[0]
                    chapter = name_parts[1]
                    audio_fileset = name_parts[2]
                    return canon, iso, distinct_id, book, chapter, audio_fileset
            break
    return None


def main():
    from version_exclude import load_excludes, excluded_set
    excluded = excluded_set(load_excludes(), scope="align")

    # Collect: merged[iso][book][audioFileset][chapter] = {verse: [start, end]}
    merged: dict[str, dict[str, dict[str, dict[str, dict]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    )

    timing_files_read = 0
    skipped_excluded = 0

    for base in TIMING_SOURCES:
        if not base.exists():
            continue
        for tf in base.rglob("*_timing.json"):
            parsed = parse_timing_path(tf)
            if not parsed:
                continue

            canon, iso, distinct_id, book, chapter, audio_fileset = parsed

            if (iso, distinct_id) in excluded:
                skipped_excluded += 1
                continue

            try:
                data = json.loads(tf.read_text())
                if not isinstance(data, list):
                    continue
            except Exception:
                continue

            pairs = convert_to_pairs(data)
            if not pairs:
                continue

            # Strip leading zeros from chapter
            ch = str(int(chapter)) if chapter.isdigit() else chapter

            merged[iso][book][audio_fileset][ch].update(pairs)
            timing_files_read += 1

    # Write per (iso, book)
    # Clean old timing dirs first
    for iso_dir in OUTPUT_DIR.iterdir() if OUTPUT_DIR.exists() else []:
        if iso_dir.is_dir():
            timing_dir = iso_dir / "timing"
            if timing_dir.is_dir():
                import shutil
                shutil.rmtree(timing_dir)

    files_written = 0
    for iso in sorted(merged):
        for book in sorted(merged[iso]):
            output: dict = {"iso": iso, "book": book}

            for audio_fileset in sorted(merged[iso][book]):
                chapters = merged[iso][book][audio_fileset]
                sorted_chapters = {}
                for ch in sorted(chapters, key=lambda x: int(x) if x.isdigit() else x):
                    verses = chapters[ch]
                    sorted_verses = {}
                    for v in sorted(verses, key=lambda x: int(x) if x.isdigit() else x):
                        sorted_verses[v] = verses[v]
                    sorted_chapters[ch] = sorted_verses
                output[audio_fileset] = sorted_chapters

            out_dir = OUTPUT_DIR / iso / "timing"
            out_dir.mkdir(parents=True, exist_ok=True)
            with open(out_dir / f"{book}.json", "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
            files_written += 1

    print(f"[INFO] Read {timing_files_read} timing files, skipped {skipped_excluded} excluded")
    print(f"[INFO] Written {files_written} per-book timing files to export/dbt/*/timing/")
    print(f"[INFO] Languages with timing: {len(merged)}")


if __name__ == "__main__":
    main()
