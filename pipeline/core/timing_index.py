#!/usr/bin/env python3
"""Internal "does real timing exist, for which books" lookup for
generate_audio_metadata.py's media-code classification and its
timingBooks/timingBooksSet counts, and generate_sync_candidates.py's
dedup — the one legitimate remaining server-side use of timing existence
data (see pull_align_manifests.py's docstring for why this stopped being
a published, client-facing artifact on 2026-09-14).

Combines two sources:
  - internal-data/align-index.json — audio-sync's real work, distilled
    from their _runs/ manifests (pull_align_manifests.py).
  - BB/contrib/legacy-timing-data — bibles' own raw sources, scanned
    directly (real directory structure, not a published index).
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import ALIGN_INDEX_FILE, TIMING_DIR, LEGACY_TIMING_DIR  # noqa: E402

LOCAL_SOURCES = [TIMING_DIR / "BB", TIMING_DIR / "contrib", LEGACY_TIMING_DIR]


def load_resolved() -> dict:
    """{iso: {audio_fileset: {books}}} — every fileset with real timing
    from ANY source (audio-sync's real work + bibles' own owned sources),
    and which books it covers."""
    resolved: dict = defaultdict(lambda: defaultdict(set))

    if ALIGN_INDEX_FILE.exists():
        index = json.loads(ALIGN_INDEX_FILE.read_text())
        for iso, canons in index.items():
            for filesets in canons.values():
                for audio_fileset, books in filesets.items():
                    resolved[iso][audio_fileset].update(books)

    for base in LOCAL_SOURCES:
        if not base.exists():
            continue
        for tf in base.rglob("*_timing.json"):
            name_parts = tf.stem.replace("_timing", "").split("_", 2)
            if len(name_parts) < 3:
                continue
            book, _chapter, audio_fileset = name_parts
            try:
                iso = tf.relative_to(base).parts[1]
            except (ValueError, IndexError):
                continue
            resolved[iso][audio_fileset].add(book)

    return resolved


def resolved_of(resolved: dict, iso: str, known_fileset_ids) -> set:
    """Intersect a caller-supplied set of REAL audio fileset ids (read
    directly from sorted/BB's own bible.abbr-scoped metadata — the only
    reliable abbr<->fileset-id mapping) against what's actually resolved.
    Do not guess this by string-prefix on the abbr (verified false
    negatives: e.g. abbr "ACRNNT"'s real audio files are literally named
    "ACRWB1N2DA_timing.json", no shared prefix at all)."""
    return set(known_fileset_ids) & set(resolved.get(iso, {}).keys())
