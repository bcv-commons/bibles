#!/usr/bin/env python3
"""Generate export/helloao-usj/<translationId>/<BOOK>.json — real
book-level USJ, built from helloAO's own real "complete translation" API
(`https://bible.helloao.org/api/<id>/complete.json` — one HTTP fetch per
translation, confirmed live 2026-09-19: BSB's complete.json is 8.1MB and
contains every book/chapter already nested under `books[].chapters[].chapter`,
the exact same per-chapter shape `helloao_to_usj.chapter_to_usj()` was
already built against). Using this single endpoint instead of one request
per book+chapter (helloAO's only other real per-chapter granularity) cuts
the fetch to 1 request/translation instead of ~30-66.

This is the helloAO side of the reduced publish scheme (USJ at book level,
Sofria at chapter level) — helloAO is the one source with no native USFM
(see helloao_to_usj.py's own module docstring), so this script is the only
place USJ is DERIVED (not parsed) for this source.

Raw complete.json responses are cached locally (resumable across runs,
same convention as fetch_helloao_book_data.py) since re-downloading
multi-MB files per run would be wasteful; only the derived per-book USJ is
published under export/.

Usage:
    python3 generate_helloao_usj.py               # all cached translations
    python3 generate_helloao_usj.py --limit N      # first N only (smoke test)
    python3 generate_helloao_usj.py --force         # re-derive USJ even if present
"""
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helloao_to_usj import chapter_to_usj  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, EXPORT, DOWNLOADS  # noqa: E402

HELLOAO_API = "https://bible.helloao.org/api"
TRANSLATIONS_FILE = API_CACHE / "helloao" / "available_translations.json"
COMPLETE_CACHE = DOWNLOADS / "helloao-complete"
OUT_DIR = EXPORT / "helloao-usj"


def fetch_complete(tid: str) -> dict | None:
    dest = COMPLETE_CACHE / f"{tid}.json"
    if dest.exists():
        return json.loads(dest.read_text())
    try:
        r = requests.get(f"{HELLOAO_API}/{tid}/complete.json", timeout=60)
    except requests.RequestException as e:
        print(f"  WARNING: {tid} fetch error: {e}")
        return None
    time.sleep(0.05)
    if r.status_code != 200:
        print(f"  WARNING: {tid} HTTP {r.status_code}")
        return None
    COMPLETE_CACHE.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return json.loads(r.text)


def merge_book_usj(book_code: str, chapters_json: list[dict]) -> dict:
    """Concatenate this book's real per-chapter USJ docs (each produced by
    chapter_to_usj()) into one book-level USJ — keep the first doc's "book"
    node, then append every doc's "chapter"+content nodes after it (each
    chapter doc already starts with its own "book" node we drop past)."""
    merged_content: list = []
    for i, cj in enumerate(chapters_json):
        usj = chapter_to_usj(cj, book_code)
        nodes = usj["content"]
        if i == 0:
            merged_content.extend(nodes)
        else:
            merged_content.extend(n for n in nodes if n.get("type") != "book")
    return {"type": "USJ", "version": "3.0", "content": merged_content}


def main():
    force = "--force" in sys.argv
    data = json.loads(TRANSLATIONS_FILE.read_text())
    translations = data["translations"]
    if "--limit" in sys.argv:
        n = int(sys.argv[sys.argv.index("--limit") + 1])
        translations = translations[:n]

    written, skipped, fetch_failed, book_failed = 0, 0, 0, 0
    total_books = 0

    for i, t in enumerate(translations, 1):
        tid = t["id"]
        tdir = OUT_DIR / tid
        if tdir.exists() and not force:
            skipped += 1
            continue

        complete = fetch_complete(tid)
        if complete is None:
            fetch_failed += 1
            continue

        tdir.mkdir(parents=True, exist_ok=True)
        books_written = 0
        for book in complete.get("books", []):
            book_code = book.get("id")
            chapters = book.get("chapters", [])
            if not book_code or not chapters:
                continue
            try:
                usj = merge_book_usj(book_code, chapters)
            except Exception as e:
                print(f"  WARNING: {tid}/{book_code} USJ build failed: {e}")
                book_failed += 1
                continue
            out_path = tdir / f"{book_code}.json"
            out_path.write_text(
                json.dumps(usj, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            books_written += 1
            total_books += 1

        if books_written:
            written += 1

        if i % 50 == 0 or i == len(translations):
            print(f"[generate-helloao-usj] [{i}/{len(translations)}] written={written} "
                  f"skipped={skipped} fetch_failed={fetch_failed} books={total_books}", flush=True)

    print(f"[generate-helloao-usj] {written} translations written, {total_books} book files, "
          f"{skipped} skipped (already present), {fetch_failed} fetch failures, "
          f"{book_failed} book build failures -> {OUT_DIR}")


if __name__ == "__main__":
    main()
