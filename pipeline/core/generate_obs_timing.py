#!/usr/bin/env python3
"""Generate export/obs/<iso>/timing.json — per-story OBS timing, the OBS
analogue of /dbt/<iso>/timing/<BOOK>.json.

Source: locally-cached real audio-sync alignment output
(pull_obs_align.py — run that first), align/obs/<iso>/<story>_timing.json,
a flat array of point timestamps: {story, segment, timestamp, score,
source}. Converted here into the same nested [start, end]-pair shape DBT
timing already uses, per an explicit client request — this is a direct
drop-in for the same loadBookTiming()-style client code already used for
Bible chapters, no new parsing logic needed on the client side.

One file per language (not split per-story like DBT splits per book) —
OBS only has 50 stories total, no need for DBT's book/chapter-scale
sharding.

end = next segment's start; the last segment's end = its own start (same
convention as convert_to_pairs() in generate_timing_by_book.py) — the
client is expected to use the audio's real duration for the true end of
the last segment. If a segment has more than one recorded attempt (only
possible if audio-sync ever republishes with retries), the highest-`score`
entry wins.

The published `iso` (top-level field and `/obs/<iso>/` directory name) is
normalize_obs_iso()'d — see generate_obs_metadata.py's docstring and
data/obs-iso-639-1.toml for why. The align-cache directory name itself
stays as audio-sync's raw code, since that's the real path on disk.

Usage:
    python3 pipeline/core/generate_obs_timing.py [--out DIR]
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from obs_iso import normalize_obs_iso  # noqa: E402
from paths import OBS_ALIGN_CACHE_DIR, OBS_DIR  # noqa: E402


def load_story_segments(path: Path) -> dict:
    """{segment_int: timestamp}, keeping the highest-score entry per segment."""
    rows = json.loads(path.read_text())
    best = {}
    best_score = {}
    for row in rows:
        seg = row.get("segment")
        ts = row.get("timestamp")
        score = row.get("score", 0)
        if seg is None or ts is None:
            continue
        if seg not in best or score > best_score[seg]:
            best[seg] = ts
            best_score[seg] = score
    return best


def to_pairs(segments: dict) -> dict:
    ordered = sorted(segments.items())
    pairs = {}
    for i, (seg, ts) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else ts
        pairs[str(seg)] = [ts, end]
    return pairs


def main():
    args = sys.argv[1:]
    out_dir = Path(args[args.index("--out") + 1]) if "--out" in args else OBS_DIR

    if not OBS_ALIGN_CACHE_DIR.exists():
        print(f"[generate-obs-timing] {OBS_ALIGN_CACHE_DIR} not found. Run: make pull-obs-align")
        return

    lang_count = 0
    for lang_dir in sorted(p for p in OBS_ALIGN_CACHE_DIR.iterdir() if p.is_dir()):
        raw_iso = lang_dir.name
        iso = normalize_obs_iso(raw_iso)
        stories = defaultdict(dict)
        for story_file in sorted(lang_dir.glob("*_timing.json")):
            story_id = story_file.stem.replace("_timing", "")
            segments = load_story_segments(story_file)
            if segments:
                stories[story_id] = to_pairs(segments)

        if not stories:
            continue

        output = {"iso": iso, **stories}
        iso_dir = out_dir / iso
        iso_dir.mkdir(parents=True, exist_ok=True)
        (iso_dir / "timing.json").write_text(
            json.dumps(output, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
        )
        lang_count += 1

    print(f"[generate-obs-timing] {lang_count} language(s) -> {out_dir}/<iso>/timing.json")


if __name__ == "__main__":
    main()
