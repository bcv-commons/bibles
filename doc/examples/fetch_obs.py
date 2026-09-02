#!/usr/bin/env python3
"""Fetch an OBS (Open Bible Stories) language's media.json and print
story 01's real text, using whichever contentLayout that language
actually uses ("md" or "ts-desktop" - see doc/obs-media.md). No
dependencies - standard library only.

Usage: python3 fetch_obs.py <iso> [storyId]
  python3 fetch_obs.py ahr        # standard "md" layout, has audio
  python3 fetch_obs.py ar-xzn     # "ts-desktop" layout, text-only
"""
import json
import sys
import urllib.error
import urllib.request

MEDIA_URL = "https://cdn.bibel.wiki/obs/{iso}/media.json"


def fetch(url: str) -> str | None:
    # cdn.bibel.wiki 403s the default Python urllib User-Agent - always set a real one.
    req = urllib.request.Request(url, headers={"User-Agent": "bibles-examples/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def fetch_standard_story(media: dict, story_id: str) -> str:
    return fetch(f"{media['content_base_url']}/{story_id}.md")


def fetch_ts_desktop_story(media: dict, story_id: str) -> str:
    base = f"{media['content_base_url']}{story_id}/"
    title = fetch(base + "title.txt")
    paragraphs = []
    n = 1
    while True:
        text = fetch(base + f"{n:02d}.txt")
        if text is None:
            break
        paragraphs.append(text)
        n += 1
    reference = fetch(base + "reference.txt")
    return "\n".join([title, "", *paragraphs, "", reference or ""])


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python3 fetch_obs.py <iso> [storyId]")
    iso = sys.argv[1]
    story_id = sys.argv[2] if len(sys.argv) > 2 else "01"

    media_json = fetch(MEDIA_URL.format(iso=iso))
    if media_json is None:
        print(f"No OBS media.json for '{iso}' (check catalog/obs-index.json first).")
        return
    media = json.loads(media_json)

    content_layout = media.get("contentLayout", "md")  # older publishes may predate this field
    print(f"{iso}: {media['storyCount']} stories, {media['audioStories']} with audio, "
          f"{media['timingStories']} with real timing (layout: {content_layout})")
    if media.get("collectionTitle"):
        print(f"Collection title: {media['collectionTitle']}")

    if content_layout == "ts-desktop":
        text = fetch_ts_desktop_story(media, story_id)
    else:
        text = fetch_standard_story(media, story_id)

    print(f"\n--- Story {story_id} ---\n{text}")


if __name__ == "__main__":
    main()
