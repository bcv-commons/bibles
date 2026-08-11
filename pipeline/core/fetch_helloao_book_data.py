#!/usr/bin/env python3
"""Fetch helloAO's per-translation books.json (vernacular book names,
chapter counts, per-book verse totals) into
internal-data/api-cache/helloao-books/<translationId>.json — resumable,
skips files already cached. Live HTTP fetch, no auth needed
(doc/sources.md: "no API key, no documented rate limit"), but still
polite-paced (matches fetch_sources.py's helloao_text() sleep convention).
"""
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from paths import API_CACHE, HELLOAO_BOOKS_CACHE  # noqa: E402

TRANSLATIONS_FILE = API_CACHE / "helloao" / "available_translations.json"
HELLOAO_API = "https://bible.helloao.org/api"


def main():
    data = json.loads(TRANSLATIONS_FILE.read_text())
    translations = data["translations"]
    if "--limit" in sys.argv:
        n = int(sys.argv[sys.argv.index("--limit") + 1])
        translations = translations[:n]

    HELLOAO_BOOKS_CACHE.mkdir(parents=True, exist_ok=True)

    ok = fail = skipped = 0
    for i, t in enumerate(translations, 1):
        tid = t["id"]
        dest = HELLOAO_BOOKS_CACHE / f"{tid}.json"
        if dest.exists():
            skipped += 1
            continue
        try:
            r = requests.get(f"{HELLOAO_API}/{tid}/books.json", timeout=15)
        except requests.RequestException:
            fail += 1
            continue
        time.sleep(0.05)
        if r.status_code != 200:
            fail += 1
            continue
        dest.write_bytes(r.content)
        ok += 1

        if i % 100 == 0 or i == len(translations):
            print(f"[fetch-helloao-books] [{i}/{len(translations)}] ok={ok} skipped={skipped} fail={fail}", flush=True)

    print(f"[fetch-helloao-books] done: {ok} fetched, {skipped} already cached, {fail} failed")


if __name__ == "__main__":
    main()
