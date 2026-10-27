#!/usr/bin/env python3
"""Fetch video-sync's YouTube data for video-only OBS languages into a local cache, for
generate_obs_metadata.py (per-story `youtube_id`) and generate_obs_index.py (the `v` flag).

video-sync publishes cdn.bibel.wiki/obs-video/index.json (one entry per video-only language)
and, for each language whose entry says `"youtube": true` (every story mapped to a video, every
offset measured), obs-video/<iso>/youtube.json. Only those languages are cached: a language with
`"youtube": false` has no published youtube.json and gets no video fields here.

These are the OBS-OBS4All languages whose door43 text is a single "Video only" placeholder; their
door43 audio (.m4a, one per story) is the untrimmed video soundtrack, so the YouTube video plays
the same audio. video-sync republishes whenever playlists or timing change; obs-metadata runs this
script each time. If the CDN can't be reached, the previous cache is kept.

Usage:
    python3 pipeline/core/fetch_obs_video.py
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import OBS_VIDEO_FILE  # noqa: E402

BASE_URL = "https://cdn.bibel.wiki/obs-video"


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main():
    try:
        index = fetch_json(f"{BASE_URL}/index.json")
        youtube = {
            iso: fetch_json(f"{BASE_URL}/{iso}/youtube.json")
            for iso, entry in sorted(index.get("languages", {}).items())
            if entry.get("youtube")
        }
    except OSError as e:
        print(f"[fetch-obs-video] CDN not reachable ({e}); keeping {OBS_VIDEO_FILE}")
        return

    OBS_VIDEO_FILE.parent.mkdir(parents=True, exist_ok=True)
    OBS_VIDEO_FILE.write_text(
        json.dumps({"index": index, "youtube": youtube}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"[fetch-obs-video] {len(index.get('languages', {}))} video-only language(s), "
          f"{len(youtube)} with youtube.json -> {OBS_VIDEO_FILE}")


if __name__ == "__main__":
    main()
