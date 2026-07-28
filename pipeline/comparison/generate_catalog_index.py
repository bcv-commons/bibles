#!/usr/bin/env python3
"""Publish the thin existence/availability pointer across all three sources
(DBT, PKF, helloAO) — companion to catalog-overlap.json (which is strictly
about comparisons and only covers languages with >=1 real comparison run).
This file answers a different question: "what exists at all, per source,
per testament, complete or Portions" — including the 168 helloAO-only /
1364 DBT-only / 21 PKF-only languages that catalog-overlap.json never
touches (there was nothing to compare them against).

Row shape: [iso, canon_tag, source, count?]
  canon_tag reuses DBT's own nt/ntp/ot/otp convention directly (full vs
  Portions) instead of a separate completeness field — one language with a
  complete Bible gets TWO rows (one "nt", one "ot"), never a combined
  "full bible" tag, consistent with the whole project's principle that NT
  and OT coverage must be assessed independently.
  source is a single letter: d=dbt, p=pkf, h=helloao.
  count = number of distinct versions from that source for this (iso,
  canon_tag) pair; omitted when exactly 1 (the overwhelming majority).

Per-source completeness signal:
  - DBT: canon tags (nt/ntp/ot/otp) come straight from DBT's own catalog,
    no inference needed there — but a "d" row is only emitted when
    resolve_fileset() confirms the row has independently fetchable text of
    its own. Some DBT catalog rows are external-source POINTERS
    (t:helloao:<id> / t:ebible:<id>) — DBT's metadata references another
    source's text rather than hosting its own. Counting those as a real
    "d" source used to make catalog-index.json say "2 sources" for a
    language where catalog-overlap.json correctly had nothing (DBT
    contributed no independently comparable candidate) — fixed 2026-07-28
    after a client hit this exact contradiction across both files.
  - helloAO: exact, verified against each translation's real book list
    (data/helloao-book-completeness.json, built from downloads/helloao/
    <id>/books.json via fetch_helloao_cache.py --samples) — checks all 27
    canonical NT book codes / all 39 OT book codes are actually present,
    not just a book COUNT (a raw numberOfBooks==27 could in principle be
    27 non-NT books; checked the actual codes to be sure).
  - PKF: no per-book-code data available without decoding every collection
    (out of scope here) — uses the "books" count as a proxy, refined by the
    "coverage" field where present:
      coverage.n == "full"       -> full NT
      coverage.n is a dict       -> Portions NT
      coverage.o present, covers all 39 OT codes -> full OT
      coverage.o present, partial -> Portions OT
      coverage.o absent          -> no OT row at all
      no coverage field at all   -> confirmed empirically clean in this
        manifest: books==27 -> full NT only; books>=66 -> full NT + full OT
        (no observed in-between case in the current manifest — every
        no-coverage collection is exactly 27, 66, or 78 books).

Usage:
    python3 scripts/generate_catalog_index.py [--out PATH]
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, DOWNLOADS, EXPORT, HELLOAO_BOOK_COMPLETENESS_FILE  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
from confirm_text_availability import resolve_fileset  # noqa: E402

OT_BOOKS = {"GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA", "1KI", "2KI",
            "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO", "ECC", "SNG", "ISA", "JER",
            "LAM", "EZK", "DAN", "HOS", "JOL", "AMO", "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL"}
NT_BOOKS = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL",
            "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"}

DBT_CATALOG_URL = "https://cdn.bibel.wiki/dbt/_catalog.json"
PKF_MANIFEST_URL = "https://cdn.bibel.wiki/pkf/manifest.json"
HELLOAO_CATALOG_URL = "https://bible.helloao.org/api/available_translations.json"


def dbt_rows():
    catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())
    counts = defaultdict(int)
    for row in catalog["versions"]:
        iso, canon = row[0], row[2]
        text_spec = next((f for f in row[3:] if f.split(":", 1)[0] in ("t", "T")), None)
        if not text_spec:
            continue  # audio-only row — text pointer only for now, audio owned by another repo
        # A `t:`/`T:` tag existing is NOT enough on its own — some DBT rows
        # are external-source POINTERS (t:helloao:<id> / t:ebible:<id>),
        # meaning DBT's own catalog has no independently fetchable text at
        # all for this row, just a reference to another source's text.
        # resolve_fileset() (the same check compare_all.py already uses to
        # build real candidates) returns None for these — reusing it here
        # closes a real client-facing gap (2026-07-28): 22 languages showed
        # "2 sources" in this index (DBT + helloAO) while catalog-overlap.json
        # correctly had nothing at all for them, because DBT's "source" was
        # never independently comparable in the first place. Fixing the
        # count here to match what's ACTUALLY fetchable removes the
        # contradiction instead of requiring a client to learn about it.
        if not resolve_fileset(row[1], text_spec):
            continue
        counts[(iso, canon, "d")] += 1
    return counts


def pkf_rows():
    pkf = json.loads((API_CACHE / "pkf-manifest.json").read_text())["languages"]
    counts = defaultdict(int)
    for iso, entry in pkf.items():
        for c in (entry.get("collections") or []):
            cov = c.get("coverage")
            books = c.get("books") or 0
            if cov is None:
                if books == 27:
                    counts[(iso, "nt", "p")] += 1
                elif books >= 66:
                    counts[(iso, "nt", "p")] += 1
                    counts[(iso, "ot", "p")] += 1
                elif books > 0:
                    counts[(iso, "ntp", "p")] += 1
                continue
            n, o = cov.get("n"), cov.get("o")
            if n == "full":
                counts[(iso, "nt", "p")] += 1
            elif isinstance(n, dict):
                counts[(iso, "ntp", "p")] += 1
            if isinstance(o, dict):
                if OT_BOOKS.issubset(o.keys()):
                    counts[(iso, "ot", "p")] += 1
                else:
                    counts[(iso, "otp", "p")] += 1
    return counts


def helloao_rows():
    hao = json.loads(HELLOAO_BOOK_COMPLETENESS_FILE.read_text())
    counts = defaultdict(int)
    for tid, r in hao.items():
        iso = r["iso"]
        if r["has_full_nt"]:
            counts[(iso, "nt", "h")] += 1
        elif r.get("has_any_nt"):
            counts[(iso, "ntp", "h")] += 1
        if r["has_full_ot"]:
            counts[(iso, "ot", "h")] += 1
        elif r.get("has_any_ot"):
            counts[(iso, "otp", "h")] += 1
    return counts


def main():
    args = sys.argv[1:]
    out_path = Path(args[args.index("--out") + 1]) if "--out" in args else EXPORT / "dbt" / "_app" / "catalog-index.json"

    # helloao-book-completeness.json (built earlier this session) only has
    # has_full_nt/has_full_ot — add has_any_nt/has_any_ot (Portions signal)
    # by re-deriving from the same books.json data, so Portions rows aren't
    # silently dropped for translations that have SOME but not all books.
    hao_path = HELLOAO_BOOK_COMPLETENESS_FILE
    hao_raw = json.loads(hao_path.read_text())
    helloao_translations = json.loads((API_CACHE / "helloao" / "available_translations.json").read_text())["translations"]
    for e in helloao_translations:
        tid = e["id"]
        books_file = DOWNLOADS / "helloao" / tid / "books.json"
        if tid not in hao_raw or not books_file.exists():
            continue
        try:
            book_ids = {b.get("id") for b in json.loads(books_file.read_text()).get("books", [])}
        except Exception:
            continue
        hao_raw[tid]["has_any_nt"] = bool(book_ids & NT_BOOKS)
        hao_raw[tid]["has_any_ot"] = bool(book_ids & OT_BOOKS)
    hao_path.write_text(json.dumps(hao_raw, indent=2), encoding="utf-8")

    all_counts = defaultdict(int)
    for counts in (dbt_rows(), pkf_rows(), helloao_rows()):
        for k, v in counts.items():
            all_counts[k] += v

    entries = []
    for (iso, canon, source), count in sorted(all_counts.items()):
        row = [iso, canon, source]
        if count > 1:
            row.append(count)
        entries.append(row)

    output = {
        "generated_at": None,
        "sources": [{"d": DBT_CATALOG_URL}, {"p": PKF_MANIFEST_URL}, {"h": HELLOAO_CATALOG_URL}],
        "entries": entries,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"[generate-catalog-index] {len(entries)} entries -> {out_path}")


if __name__ == "__main__":
    main()
