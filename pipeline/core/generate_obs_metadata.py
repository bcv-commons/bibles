#!/usr/bin/env python3
"""Generate export/obs/<iso>/media.json — per-language OBS (Open Bible
Stories) detail, the OBS analogue of /dbt/<iso>/media.json.

Primary source: fetch_obs_repos.py's cache (OBS_REPOS_FILE), resolved
directly from door43's own catalog/release APIs for EVERY OBS language,
text-only or audio-bearing alike. This is deliberately NOT gated on
audio-sync's _obs_batches/<iso>.json staging pace — a real, client-reported
gap existed when it was: audio-sync's align/obs/ alignment output reached
14 languages while _obs_batches/ staging had only reached 1, making 13
languages with real, live timing invisible to this file (the layer clients
actually use for discovery). See fetch_obs_repos.py's docstring for the
full story; see doc/catalog-obs.md for the historical note.

`_obs_batches/<iso>.json`, when present for a language, is used only as an
OPTIONAL enrichment source for `segmentCount` (audio-sync's own narration-
segment-count claim per story, not derivable from door43's catalog alone)
— never required for a language's media.json to exist.

- `audioStories` / `audioStoriesSet` follow the same
  count-always-set-only-when-partial convention as `audioBooks`/
  `audioBooksSet` in generate_audio_metadata.py.
- `timingStories` / `timingStoriesSet` reflect real audio-sync alignment
  output pulled by pull_obs_align.py (align/obs/<iso>/<story>_timing.json).
- `stories` (per-story map) is present whenever `storyCount > 0`, for
  every language — text-only included, not just audio-bearing. Each
  entry always carries `title` (from fetch_obs_titles.py — the one place
  this pipeline fetches real story content, see that script's docstring)
  when resolved; `audio_url`/`segmentCount` only appear when that story
  has real audio.

The published `iso` (top-level field and `/obs/<iso>/` directory name) is
normalize_obs_iso()'d — door43's raw code for 36 of 214 languages is a
2-letter ISO 639-1 code, not the 3-letter ISO 639-3 every other file in
this repo uses. Internal cache lookups (align/, _obs_batches/) still key
off the RAW code, since that's what door43/audio-sync actually use — see
pipeline/obs_iso.py and data/obs-iso-639-1.toml.

Usage:
    python3 pipeline/core/generate_obs_metadata.py [--out DIR]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from obs_iso import normalize_obs_iso  # noqa: E402
from paths import (  # noqa: E402
    OBS_ALIGN_CACHE_DIR,
    OBS_BATCHES_CACHE_DIR,
    OBS_DIR,
    OBS_REPOS_FILE,
    OBS_TITLES_FILE,
)

FULL_STORY_COUNT = 50  # canonical OBS story count


def timing_story_ids(iso: str) -> list:
    lang_dir = OBS_ALIGN_CACHE_DIR / iso
    if not lang_dir.exists():
        return []
    return sorted(f.stem.replace("_timing", "") for f in lang_dir.glob("*_timing.json"))


def segment_counts_from_batch(iso: str) -> dict:
    """{story_id: segment_count}, from audio-sync's staging manifest if cached — best-effort enrichment only."""
    path = OBS_BATCHES_CACHE_DIR / f"{iso}.json"
    if not path.exists():
        return {}
    manifest = json.loads(path.read_text())
    return {sid: s.get("segment_count") for sid, s in manifest.get("stories", {}).items()}


def build_media(detail: dict, titles: dict) -> dict:
    raw_iso = detail["iso"]  # door43's own code — needed to key into align/_obs_batches caches
    story_ids = detail.get("storyIds", [])
    audio = detail.get("audio", {})
    audio_ids = sorted(audio.keys())
    timing_ids = timing_story_ids(raw_iso)
    segment_counts = segment_counts_from_batch(raw_iso)
    lang_titles = titles.get(raw_iso, {})

    media = {
        "iso": normalize_obs_iso(raw_iso),
        "source": detail.get("source"),
        "source_repo": detail.get("source_repo"),
        "content_base_url": detail.get("content_base_url"),
        "contentLayout": detail.get("contentLayout", "md"),
        "license": detail.get("license"),
        "checking_level": detail.get("checking_level"),
        "storyCount": len(story_ids),
        "audioStories": len(audio_ids),
        "timingStories": len(timing_ids),
    }
    if detail.get("collectionTitle"):
        media["collectionTitle"] = detail["collectionTitle"]
    if story_ids:
        stories = {}
        for sid in story_ids:
            entry = {}
            if sid in lang_titles:
                entry["title"] = lang_titles[sid]
            if sid in audio:
                entry["audio_url"] = audio[sid]
                entry["segmentCount"] = segment_counts.get(sid)
            if entry:
                stories[sid] = entry
        if stories:
            media["stories"] = stories
    if 0 < len(audio_ids) < FULL_STORY_COUNT:
        media["audioStoriesSet"] = audio_ids
    if 0 < len(timing_ids) < FULL_STORY_COUNT:
        media["timingStoriesSet"] = timing_ids
    return media


def main():
    args = sys.argv[1:]
    out_dir = Path(args[args.index("--out") + 1]) if "--out" in args else OBS_DIR

    if not OBS_REPOS_FILE.exists():
        print(f"[generate-obs-metadata] {OBS_REPOS_FILE} not found. Run: make fetch-obs-repos")
        return

    repos = json.loads(OBS_REPOS_FILE.read_text())
    titles = json.loads(OBS_TITLES_FILE.read_text()) if OBS_TITLES_FILE.exists() else {}
    count = 0
    for detail in repos.values():
        media = build_media(detail, titles)
        iso_dir = out_dir / media["iso"]
        iso_dir.mkdir(parents=True, exist_ok=True)
        (iso_dir / "media.json").write_text(
            json.dumps(media, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
        )
        count += 1

    print(f"[generate-obs-metadata] {count} language(s) -> {out_dir}/<iso>/media.json")


if __name__ == "__main__":
    main()
