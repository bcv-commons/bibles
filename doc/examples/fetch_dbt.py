#!/usr/bin/env python3
"""Fetch verse text from DBT (Bible Brain, Digital Bible Platform, by
Faith Comes By Hearing) - requires your own API key (this repo doesn't
proxy DBT access). Get one at https://www.faithcomesbyhearing.com/bible-brain

No dependencies beyond the Python standard library.

Usage:
    BIBLE_API_KEY=... python3 fetch_dbt.py <fileset_id> <BOOK> <chapter>
    BIBLE_API_KEY=... python3 fetch_dbt.py ENGESVN2DA REV 15
"""
import json
import os
import sys
import urllib.request

API_BASE = "https://4.dbt.io/api"


def main():
    if len(sys.argv) < 4:
        sys.exit("usage: fetch_dbt.py <fileset_id> <BOOK> <chapter>")
    api_key = os.environ.get("BIBLE_API_KEY")
    if not api_key:
        sys.exit("Set BIBLE_API_KEY first - get one at "
                  "https://www.faithcomesbyhearing.com/bible-brain")

    fileset_id, book, chapter = sys.argv[1], sys.argv[2], sys.argv[3]
    url = f"{API_BASE}/bibles/filesets/{fileset_id}/{book}/{chapter}?key={api_key}&v=4"
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read())

    verses = data.get("data") or []
    if verses and "path" in verses[0]:
        print("This fileset returns a downloadable file, not inline verses:")
        print(verses[0]["path"])
        return

    for verse in verses:
        print(f"{verse['verse_start']}. {verse['verse_text']}")


if __name__ == "__main__":
    main()
