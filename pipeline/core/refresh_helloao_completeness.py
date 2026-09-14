#!/usr/bin/env python3
"""Refresh internal-data/comparison-results/helloao-book-completeness.json
so it covers every translation currently in helloAO's live catalog.

Prerequisite for the "sources"/"h" live-derivation in
generate_audio_metadata.py — verified directly (2026-09-12) that this file
was silently missing several real, currently-live translations (e.g.
tee_tbl, tsn_bib) because generate_catalog_index.py's own enrichment step
only updates translations already present as keys, never adds new ones.
This script fixes that: for every translation in
api-cache/helloao/available_translations.json, fetch its books list if not
already cached (downloads/helloao/<tid>/books.json — reuses
fetch_helloao_cache.py's fetch_books_list(), same on-disk cache) and
(re)compute has_full_nt/has_full_ot/has_full_bible/has_any_nt/has_any_ot
from scratch, so the completeness file's key set tracks the live catalog
instead of whatever translations happened to exist when it was first built.

Usage:
    python3 pipeline/core/refresh_helloao_completeness.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_helloao_cache import fetch_books_list  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, COMPARISON_RESULTS_DIR, HELLOAO_BOOK_COMPLETENESS_FILE  # noqa: E402

OT_BOOKS = {"GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA", "1KI", "2KI",
            "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO", "ECC", "SNG", "ISA", "JER",
            "LAM", "EZK", "DAN", "HOS", "JOL", "AMO", "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL"}
NT_BOOKS = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL",
            "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"}


def main():
    translations = json.loads((API_CACHE / "helloao" / "available_translations.json").read_text())["translations"]

    existing = {}
    if HELLOAO_BOOK_COMPLETENESS_FILE.exists():
        existing = json.loads(HELLOAO_BOOK_COMPLETENESS_FILE.read_text())

    result = {}
    fetched = 0
    failed = 0
    for entry in translations:
        tid = entry["id"]
        iso = entry.get("language", "")

        books = fetch_books_list(tid)
        if books is None:
            failed += 1
            # Keep a prior entry rather than dropping known-good data just
            # because today's live fetch failed transiently.
            if tid in existing:
                result[tid] = existing[tid]
            continue
        fetched += 1

        book_ids = {b.get("id") for b in books}
        result[tid] = {
            "iso": iso,
            "has_full_nt": NT_BOOKS.issubset(book_ids),
            "has_full_ot": OT_BOOKS.issubset(book_ids),
            "has_full_bible": NT_BOOKS.issubset(book_ids) and OT_BOOKS.issubset(book_ids),
            "has_any_nt": bool(book_ids & NT_BOOKS),
            "has_any_ot": bool(book_ids & OT_BOOKS),
        }

    COMPARISON_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    HELLOAO_BOOK_COMPLETENESS_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[refresh-helloao-completeness] {len(result)} translations "
          f"({fetched} freshly computed, {failed} fetch failures kept from prior data) "
          f"-> {HELLOAO_BOOK_COMPLETENESS_FILE}")


if __name__ == "__main__":
    main()
