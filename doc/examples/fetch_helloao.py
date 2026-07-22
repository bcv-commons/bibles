#!/usr/bin/env python3
"""Fetch a chapter of text from helloAO - no API key needed.
No dependencies beyond the Python standard library.

Usage:
    python3 fetch_helloao.py <translation_id> <BOOK> <chapter>
    python3 fetch_helloao.py eng_kjv REV 15
"""
import json
import sys
import urllib.request

API_BASE = "https://bible.helloao.org/api"


def main():
    if len(sys.argv) < 4:
        sys.exit("usage: fetch_helloao.py <translation_id> <BOOK> <chapter>")
    translation_id, book, chapter = sys.argv[1], sys.argv[2], sys.argv[3]

    url = f"{API_BASE}/{translation_id}/{book}/{chapter}.json"
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read())

    for block in data["chapter"]["content"]:
        if block.get("type") != "verse":
            continue
        # Verse content items are plain strings, {"text":..., "poem": N}
        # (poetic sub-lines), or markup-only dicts like {"noteId": ...} /
        # {"lineBreak": true} - skip anything without real text.
        parts = []
        for item in block["content"]:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
        print(f"{block['number']}. {' '.join(parts)}")


if __name__ == "__main__":
    main()
