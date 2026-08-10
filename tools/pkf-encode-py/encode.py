#!/usr/bin/env python3
"""Encode a USFM file into a .pkf file — the write-side sibling of
../pkf-decode-py/decode.py.

Usage:
  python3 encode.py <path-to.usfm> --lang <iso> --abbr <version-abbr> [--out <path.pkf>]
"""
import argparse
import sys
from pathlib import Path

from build_pkf import build_pkf_bytes
from usfm_to_items import build


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--lang", required=True)
    parser.add_argument("--abbr", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    usfm_text = Path(args.input).read_text(encoding="utf-8")
    builder = build(usfm_text)
    pkf_bytes = build_pkf_bytes(builder, args.lang, args.abbr)

    out_path = Path(args.out) if args.out else Path(args.input).with_suffix(".pkf")
    out_path.write_bytes(pkf_bytes)
    print(f"[pkf-encode] {args.input} -> {out_path} ({len(pkf_bytes)} bytes, book={builder.book_code})")


if __name__ == "__main__":
    main()
