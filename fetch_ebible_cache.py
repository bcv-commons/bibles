#!/usr/bin/env python3
"""Fetch eBible.org translations catalog to local cache.

Downloads: https://ebible.org/Scriptures/translations.csv
Output: api-cache/ebible/translations.csv

The catalog contains ~1500 translations with metadata including
ISO codes, book counts, redistributability, and download URLs.

Text can be fetched per-translation as USFM:
  https://ebible.org/Scriptures/{translationId}_usfm.zip
"""

import urllib.request
from pathlib import Path

CACHE_DIR = Path("api-cache/ebible")
CATALOG_URL = "https://ebible.org/Scriptures/translations.csv"


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CACHE_DIR / "translations.csv"

    print(f"[INFO] Fetching eBible catalog from {CATALOG_URL}")
    try:
        req = urllib.request.Request(CATALOG_URL, headers={"User-Agent": "bible-story-builder/1.0"})
        with urllib.request.urlopen(req) as resp:
            out_path.write_bytes(resp.read())
        # Count entries
        lines = out_path.read_text(encoding="utf-8-sig").strip().splitlines()
        print(f"[INFO] Saved {len(lines) - 1} translations to {out_path}")
    except Exception as e:
        print(f"[ERROR] Failed to fetch: {e}")
        return

    # Print summary
    import csv
    with open(out_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    redistributable = sum(1 for r in rows if r.get("Redistributable") == "True")
    isos = len(set(r["languageCode"] for r in rows))
    full_nt = sum(1 for r in rows if int(r.get("NTbooks", "0") or 0) >= 27)

    print(f"[INFO] Summary: {len(rows)} translations, {isos} languages")
    print(f"[INFO]   Redistributable: {redistributable}")
    print(f"[INFO]   Full NT (>=27 books): {full_nt}")


if __name__ == "__main__":
    main()
