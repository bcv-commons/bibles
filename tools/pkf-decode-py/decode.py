#!/usr/bin/env python3
"""Python sibling of ../pkf-decode/decode.mjs — decodes a PKF file (a
Proskomma "succinct docSet", gzip-compressed JSON) into one plain USFM file
per book. Same CLI shape, same output naming, same byte-for-byte USFM text
(verified against decode.mjs; see verify_corpus.py).

Usage:
  python3 decode.py <path-to.pkf> [--out <dir>] [--book <BOOKCODE>]
  python3 decode.py <dir-of-.pkf-files> [--out <dir>]
"""
import argparse
import sys
from pathlib import Path

from load import load_pkf
from usfm_render import calculate_usfm_chapter_positions, perf2usfm

# USFM/Paratext book id -> file number, for stable sortable filenames.
# 40 is reserved (skipped) between OT (39 books) and NT (starts at 41).
BOOK_NUM = {
    "GEN": "01", "EXO": "02", "LEV": "03", "NUM": "04", "DEU": "05", "JOS": "06", "JDG": "07",
    "RUT": "08", "1SA": "09", "2SA": "10", "1KI": "11", "2KI": "12", "1CH": "13",
    "2CH": "14", "EZR": "15", "NEH": "16", "EST": "17", "JOB": "18", "PSA": "19", "PRO": "20",
    "ECC": "21", "SNG": "22", "ISA": "23", "JER": "24", "LAM": "25", "EZK": "26", "DAN": "27",
    "HOS": "28", "JOL": "29", "AMO": "30", "OBA": "31", "JON": "32", "MIC": "33", "NAM": "34",
    "HAB": "35", "ZEP": "36", "HAG": "37", "ZEC": "38", "MAL": "39",
    "MAT": "41", "MRK": "42", "LUK": "43", "JHN": "44", "ACT": "45", "ROM": "46", "1CO": "47",
    "2CO": "48", "GAL": "49", "EPH": "50", "PHP": "51", "COL": "52", "1TH": "53",
    "2TH": "54", "1TI": "55", "2TI": "56", "TIT": "57", "PHM": "58", "HEB": "59",
    "JAS": "60", "1PE": "61", "2PE": "62", "1JN": "63", "2JN": "64", "3JN": "65",
    "JUD": "66", "REV": "67",
    # deuterocanon
    "TOB": "68", "JDT": "69", "ESG": "70", "WIS": "71", "SIR": "72", "BAR": "73", "LJE": "74",
    "S3Y": "75", "SUS": "76", "BEL": "77", "1MA": "78", "2MA": "79", "3MA": "80",
    "4MA": "81", "1ES": "82", "2ES": "83", "MAN": "84", "PS2": "85", "ODA": "86",
    "PSS": "87",
    # peripherals + user-defined "extra material" books (XXA-XXG)
    "FRT": "A0", "BAK": "A1", "OTH": "A2", "INT": "A7", "CNC": "A8", "GLO": "A9", "TDX": "B0",
    "NDX": "B1", "XXA": "94", "XXB": "95", "XXC": "96", "XXD": "97", "XXE": "98", "XXF": "99",
    "XXG": "100",
}


def decode_document(loaded, doc_id):
    doc = loaded["docs"][doc_id]
    docset_id, selectors = loaded["docset_id"], loaded["selectors"]
    report = calculate_usfm_chapter_positions(doc, docset_id, selectors)
    return perf2usfm(doc, docset_id, selectors, report)


def decode_pkf(pkf_path, out_dir, book_filter=None):
    loaded = load_pkf(Path(pkf_path).read_bytes())
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    n = 0
    unmapped = []
    for doc_id, doc in loaded["docs"].items():
        book_code = doc["headers"].get("bookCode")
        if book_filter and book_code != book_filter:
            continue
        usfm = decode_document(loaded, doc_id)
        num = BOOK_NUM.get(book_code)
        if not num:
            unmapped.append(book_code)
        name = f"{num}-{book_code}.usfm" if num else f"{book_code}.usfm"
        (out_dir / name).write_text(usfm)
        n += 1
    return n, unmapped


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("input", nargs="?")
    parser.add_argument("--out", default=None)
    parser.add_argument("--book", default=None)
    args = parser.parse_args()

    if not args.input:
        print("usage: python3 decode.py <path-to.pkf-or-dir> [--out <dir>] [--book <BOOKCODE>]", file=sys.stderr)
        sys.exit(2)

    book_filter = args.book.upper() if args.book else None
    input_path = Path(args.input)
    if input_path.is_dir():
        pkf_files = sorted(input_path.glob("*.pkf"))
    else:
        pkf_files = [input_path]

    if not pkf_files:
        print(f"[pkf-decode] no .pkf files found in {args.input}", file=sys.stderr)
        sys.exit(1)

    base_out = Path(args.out) if args.out else Path("out")
    multi = len(pkf_files) > 1
    for pkf_path in pkf_files:
        base = pkf_path.name.split(".")[0]
        out_dir = (base_out / base) if multi else base_out
        n, unmapped = decode_pkf(pkf_path, out_dir, book_filter)
        msg = f"[pkf-decode] {base}: {n} book(s) -> {out_dir}/"
        if unmapped:
            msg += f"  (unknown book code, named without a number prefix: {', '.join(unmapped)})"
        print(msg)


if __name__ == "__main__":
    main()
