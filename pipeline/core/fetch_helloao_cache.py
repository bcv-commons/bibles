#!/usr/bin/env python3
"""
Fetch the HelloAO Bible translation catalog and sample chapters.

Step 1: Downloads the complete list of available translations.
Step 2: For each translation, fetches the books list to check which books
        are available, then downloads sample chapters (REV 15 for NT,
        PSA 117 for OT) to discover audio availability and confirm content.

Usage:
    python3 fetch_helloao_cache.py              # catalog only (7-day freshness)
    python3 fetch_helloao_cache.py --samples     # also download sample chapters
    python3 fetch_helloao_cache.py --force       # ignore freshness checks

Output:
    api-cache/helloao/available_translations.json   # translation catalog
    api-cache/helloao/audio_summary.json            # which translations have audio
    downloads/helloao/{translation_id}/books.json       # cached books list
    downloads/helloao/{translation_id}/nt/REV_015.json  # NT sample
    downloads/helloao/{translation_id}/ot/PSA_117.json  # OT sample

API Information:
    - URL: https://bible.helloao.org
    - No API key required
    - No rate limits
    - All content is freely licensed
"""

import argparse
import json
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, DOWNLOADS  # noqa: E402

API_BASE = "https://bible.helloao.org/api"
CATALOG_URL = f"{API_BASE}/available_translations.json"
CACHE_DIR = API_CACHE / "helloao"
CATALOG_FILE = CACHE_DIR / "available_translations.json"
AUDIO_SUMMARY_FILE = CACHE_DIR / "audio_summary.json"
DOWNLOADS_DIR = DOWNLOADS / "helloao"
FRESHNESS_DAYS = 7

# Sample chapters to probe
NT_SAMPLE = ("REV", 15)  # Revelation 15
OT_SAMPLE = ("PSA", 117)  # Psalm 117


def is_fresh(path: Path) -> bool:
    """Check if a file is less than FRESHNESS_DAYS old."""
    if not path.exists():
        return False
    age_seconds = time.time() - path.stat().st_mtime
    return age_seconds < FRESHNESS_DAYS * 86400


def fetch_catalog(force: bool = False) -> list[dict]:
    """Download the HelloAO translation catalog. Returns list of translations."""
    if not force and is_fresh(CATALOG_FILE):
        age_hours = (time.time() - CATALOG_FILE.stat().st_mtime) / 3600
        print(f"Catalog is fresh ({age_hours:.0f}h old). Use --force to re-fetch.")
        with open(CATALOG_FILE, encoding="utf-8") as f:
            return json.load(f).get("translations", [])

    print(f"Fetching catalog from {CATALOG_URL} ...")
    response = requests.get(CATALOG_URL, timeout=30)
    response.raise_for_status()

    data = response.json()
    translations = data.get("translations", [])

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    langs = set(t["language"] for t in translations)
    print(f"Cached {len(translations)} translations across {len(langs)} languages")
    return translations


def fetch_books_list(translation_id: str, force: bool = False) -> list | None:
    """Fetch and cache the books list for a translation. Returns list of book objects or None."""
    books_dir = DOWNLOADS_DIR / translation_id
    books_file = books_dir / "books.json"

    if not force and books_file.exists():
        with open(books_file, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("books", [])

    url = f"{API_BASE}/{translation_id}/books.json"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            books_dir.mkdir(parents=True, exist_ok=True)
            with open(books_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return data.get("books", [])
    except requests.RequestException:
        pass
    return None


def fetch_sample_chapter(translation_id: str, book: str, chapter: int) -> dict | None:
    """Fetch a single chapter. Returns the JSON data or None on failure."""
    url = f"{API_BASE}/{translation_id}/{book}/{chapter}.json"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None


def fetch_samples(translations: list[dict], force: bool = False) -> None:
    """Download NT/OT sample chapters for all translations."""
    audio_summary = {}
    total = len(translations)
    fetched = 0
    skipped = 0
    errors = 0
    books_skipped = 0

    print(f"\nFetching sample chapters for {total} translations...")

    for i, t in enumerate(translations, 1):
        tid = t["id"]
        lang = t["language"]

        # Fetch the books list to know which books this translation actually has
        books = fetch_books_list(tid, force=force)
        if books is None:
            errors += 1
            if i % 100 == 0 or i == total:
                print(f"  [{i}/{total}] fetched={fetched} skipped={skipped} books_skipped={books_skipped} errors={errors} with_audio={len(audio_summary)}")
            continue

        # Extract book codes (books list contains objects with "id" field, or plain strings)
        if books and isinstance(books[0], dict):
            book_codes = [b.get("id", b.get("name", "")) for b in books]
        else:
            book_codes = list(books)

        has_rev = NT_SAMPLE[0] in book_codes
        has_psa = OT_SAMPLE[0] in book_codes

        audio_readers = {}

        # NT sample: REV 15
        nt_dir = DOWNLOADS_DIR / tid / "nt"
        nt_file = nt_dir / f"REV_{NT_SAMPLE[1]:03d}.json"
        if has_rev:
            if not force and nt_file.exists():
                # Read existing to extract audio info
                with open(nt_file, encoding="utf-8") as f:
                    nt_data = json.load(f)
                nt_audio = nt_data.get("thisChapterAudioLinks", {})
                if nt_audio:
                    audio_readers["nt"] = list(nt_audio.keys())
                skipped += 1
            else:
                nt_data = fetch_sample_chapter(tid, NT_SAMPLE[0], NT_SAMPLE[1])
                if nt_data:
                    nt_dir.mkdir(parents=True, exist_ok=True)
                    with open(nt_file, "w", encoding="utf-8") as f:
                        json.dump(nt_data, f, ensure_ascii=False, indent=2)
                    nt_audio = nt_data.get("thisChapterAudioLinks", {})
                    if nt_audio:
                        audio_readers["nt"] = list(nt_audio.keys())
                    fetched += 1
                else:
                    errors += 1
        else:
            books_skipped += 1

        # OT sample: PSA 117
        ot_dir = DOWNLOADS_DIR / tid / "ot"
        ot_file = ot_dir / f"PSA_{OT_SAMPLE[1]:03d}.json"
        if has_psa:
            if not force and ot_file.exists():
                with open(ot_file, encoding="utf-8") as f:
                    ot_data = json.load(f)
                ot_audio = ot_data.get("thisChapterAudioLinks", {})
                if ot_audio:
                    audio_readers["ot"] = list(ot_audio.keys())
                skipped += 1
            else:
                ot_data = fetch_sample_chapter(tid, OT_SAMPLE[0], OT_SAMPLE[1])
                if ot_data:
                    ot_dir.mkdir(parents=True, exist_ok=True)
                    with open(ot_file, "w", encoding="utf-8") as f:
                        json.dump(ot_data, f, ensure_ascii=False, indent=2)
                    ot_audio = ot_data.get("thisChapterAudioLinks", {})
                    if ot_audio:
                        audio_readers["ot"] = list(ot_audio.keys())
                    fetched += 1
                else:
                    errors += 1
        else:
            books_skipped += 1

        if audio_readers:
            audio_summary[tid] = {
                "language": lang,
                "readers": audio_readers,
            }

        # Progress
        if i % 100 == 0 or i == total:
            print(f"  [{i}/{total}] fetched={fetched} skipped={skipped} books_skipped={books_skipped} errors={errors} with_audio={len(audio_summary)}")

    # Save audio summary
    with open(AUDIO_SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(audio_summary, f, ensure_ascii=False, indent=2)

    audio_langs = set(v["language"] for v in audio_summary.values())
    print(f"\nDone. {len(audio_summary)} translations with audio across {len(audio_langs)} languages")
    print(f"  → {AUDIO_SUMMARY_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Fetch HelloAO Bible translation catalog and samples")
    parser.add_argument("--force", action="store_true", help="Ignore freshness checks")
    parser.add_argument("--samples", action="store_true", help="Also download sample chapters (REV 15 / PSA 117)")
    args = parser.parse_args()

    translations = fetch_catalog(force=args.force)

    if args.samples:
        fetch_samples(translations, force=args.force)


if __name__ == "__main__":
    main()
