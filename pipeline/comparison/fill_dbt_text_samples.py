#!/usr/bin/env python3
"""Fill remaining gaps in internal-data/text/BB/nt/'s REV 15 DBT text
samples, for the DBT/PKF overlap languages where the published catalog
(dbt/_catalog.json) says a text fileset exists but no local sample has
been fetched yet.

Companion to confirm_text_availability.py (which only records
present/absent/never-checked) — this one actually writes usable verse text
to disk, in the same one-verse-per-line format fetch_verse_count() in
fingerprint_versification.py already uses, so the PKF-comparison work can
read it directly.

Tracks and reports the nt/ntp (Portions) canon split per fetched row —
Portions filesets are DBT's own "book may or may not actually be present"
claim (see fileset_contains_book()'s docstring elsewhere in this repo), so
a sample fetched from a `ntp` row is weaker evidence of full coverage than
one from a plain `nt` row.

Usage:
    python3 fill_dbt_text_samples.py [--book REV] [--chapter 15]

Reads:  cdn.bibel.wiki/dbt/_catalog.json (cached at internal-data/api-cache/dbt-catalog.json)
        cdn.bibel.wiki/pkf/manifest.json (cached at internal-data/api-cache/pkf-manifest.json)
        internal-data/text/BB/nt/ (what's already sampled)
Writes: internal-data/text/BB/nt/<iso>/<distinct_id>/<BOOK>/<BOOK>_<CHAP>_<fileset>.txt
        internal-data/comparison-results/text-fill-log.json (local record of this run, gitignored)
"""
import json
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import download_language_content as dl  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
from confirm_text_availability import fetch_catalog, resolve_fileset  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, TEXT_DIR, TEXT_FILL_LOG_FILE  # noqa: E402

PKF_MANIFEST_URL = "https://cdn.bibel.wiki/pkf/manifest.json"
PKF_MANIFEST_CACHE = API_CACHE / "pkf-manifest.json"
SAMPLE_DIR = TEXT_DIR / "BB"
LOG_FILE = TEXT_FILL_LOG_FILE


def fetch_pkf_manifest() -> dict:
    try:
        req = urllib.request.Request(PKF_MANIFEST_URL, headers={"User-Agent": "bibles/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        PKF_MANIFEST_CACHE.parent.mkdir(parents=True, exist_ok=True)
        PKF_MANIFEST_CACHE.write_bytes(raw)
        return json.loads(raw)
    except Exception as e:
        if PKF_MANIFEST_CACHE.exists():
            print(f"[fill-samples] live PKF manifest fetch failed ({e}), using cache", file=sys.stderr)
            return json.loads(PKF_MANIFEST_CACHE.read_text())
        raise


def local_samples(canon_dir: str, book: str, chapter: int) -> dict[str, set[str]]:
    """iso -> {distinct_id, ...} already sampled for this book/chapter."""
    have: dict[str, set[str]] = defaultdict(set)
    probe = f"{book}_{chapter:03d}_"
    base = SAMPLE_DIR / canon_dir
    if not base.is_dir():
        return have
    for f in base.rglob(f"{probe}*.txt"):
        parts = f.relative_to(base).parts  # <iso>/<distinct_id>/<BOOK>/file
        have[parts[0]].add(parts[1])
    return have


def missing_rows(book: str, chapter: int, canon_plain: str) -> list[tuple[str, str, str, str]]:
    """[(iso, distinct_id, canon, fileset_id), ...] for catalog rows with a
    text field, in a DBT/PKF overlap language, not yet sampled locally."""
    catalog = fetch_catalog()
    pkf = fetch_pkf_manifest()["languages"]
    dbt_isos = {row[0] for row in catalog["versions"]}
    overlap = dbt_isos & set(pkf.keys())

    canon_dir = "nt" if canon_plain == "nt" else "ot"
    have = local_samples(canon_dir, book, chapter)

    rows = []
    for row in catalog["versions"]:
        iso, distinct_id, canon = row[0], row[1], row[2]
        if canon not in (canon_plain, canon_plain + "p") or iso not in overlap:
            continue
        if distinct_id in have.get(iso, set()):
            continue
        text_field = next((f for f in row[3:] if f.split(":", 1)[0] in ("t", "T")), None)
        if text_field is None:
            continue
        fileset_id = resolve_fileset(distinct_id, text_field)
        if fileset_id:
            rows.append((iso, distinct_id, canon, fileset_id))
    return rows


def write_sample(canon_dir: str, iso: str, distinct_id: str, book: str, chapter: int,
                  fileset_id: str, result: dict) -> bool:
    """Write one verse per line, matching fetch_verse_count()'s format.
    Only handles the inline 'verses' response shape — 'path' (downloadable
    JSON/USX) filesets are skipped and reported, not silently dropped."""
    if result.get("type") != "verses":
        return False
    by_verse = {}
    for item in result["data"]:
        vs = item.get("verse_start")
        txt = " ".join(item.get("verse_text", "").split())
        if vs is None or not txt:
            continue
        by_verse[vs] = (by_verse.get(vs, "") + " " + txt).strip()
    if not by_verse:
        return False
    verses = [by_verse[k] for k in sorted(by_verse)]
    dest = SAMPLE_DIR / canon_dir / iso / distinct_id / book / f"{book}_{chapter:03d}_{fileset_id}.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(verses) + "\n", encoding="utf-8")
    return True


def main():
    args = sys.argv[1:]
    book = "REV"
    chapter = 15
    if "--book" in args:
        book = args[args.index("--book") + 1]
    if "--chapter" in args:
        chapter = int(args[args.index("--chapter") + 1])

    catalog = fetch_catalog()
    ref_books = catalog.get("reference_books", {"nt": "REV", "ot": "PSA"})
    canon_plain = next((c for c, b in ref_books.items() if b == book), None)
    if canon_plain is None:
        sys.exit(f"[fill-samples] --book {book} isn't a catalog reference book ({ref_books})")
    canon_dir = "nt" if canon_plain == "nt" else "ot"

    rows = missing_rows(book, chapter, canon_plain)
    plain_rows = [r for r in rows if r[2] == canon_plain]
    portions_rows = [r for r in rows if r[2] == canon_plain + "p"]
    print(f"[fill-samples] {len(rows)} candidate row(s) to fetch for {book} {chapter} "
          f"({len(plain_rows)} plain-canon, {len(portions_rows)} Portions)")

    log = {"checked_at": datetime.now(timezone.utc).isoformat(), "book": book,
           "chapter": chapter, "written": [], "failed": [], "skipped_path_type": []}

    written, failed, skipped_path = 0, 0, 0
    # Plain-canon rows first — same confirmation-priority reasoning as
    # confirm_text_availability.py.
    for iso, distinct_id, canon, fileset_id in plain_rows + portions_rows:
        result = dl.get_text_content(fileset_id, book, chapter)
        is_portions = canon != canon_plain
        if not result:
            status = dl._classify_api_failure()
            failed += 1
            log["failed"].append({"iso": iso, "distinct_id": distinct_id, "fileset_id": fileset_id,
                                   "portions": is_portions, "status": status})
            print(f"  {iso}/{fileset_id}{' (portions)' if is_portions else ''}: {status}")
        elif write_sample(canon_dir, iso, distinct_id, book, chapter, fileset_id, result):
            written += 1
            log["written"].append({"iso": iso, "distinct_id": distinct_id, "fileset_id": fileset_id,
                                    "portions": is_portions})
            print(f"  {iso}/{fileset_id}{' (portions)' if is_portions else ''}: written")
        else:
            skipped_path += 1
            log["skipped_path_type"].append({"iso": iso, "distinct_id": distinct_id,
                                              "fileset_id": fileset_id, "portions": is_portions})
            print(f"  {iso}/{fileset_id}{' (portions)' if is_portions else ''}: "
                  f"confirmed but 'path'-type response (JSON/USX download) — not written, needs separate handling")
        time.sleep(0.1)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(log, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[fill-samples] done: {written} written, {failed} failed/absent, "
          f"{skipped_path} skipped (path-type, needs separate handling). Log: {LOG_FILE}")


if __name__ == "__main__":
    main()
