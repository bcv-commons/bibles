#!/usr/bin/env python3
"""Alternate Python sibling of ../pkf-encode-py/encode.py — encodes a USFM
file into a .pkf file, same as that package, but PARSES the source USFM
with `usfmtc` (a real, independently-maintained USFM parser,
https://pypi.org/project/usfmtc/) instead of this repo's own hand-rolled
usfm_lexer.py tokenizer.

This does NOT replace ../pkf-encode-py — it's a second, alternate example
for clients who'd rather pull in one well-maintained external USFM library
than carry a hand-rolled lexer. The succinct-encoding BACKEND
(build_pkf.py / succinct_write.py / enum_builder.py) is reused entirely
unchanged, imported from ../pkf-encode-py — only the frontend (USFM text
-> intermediate structure) differs: usj_to_builder.py walks usfmtc's USJ
output and drives the same usfm_to_items.Builder ../pkf-encode-py's own
tokenizer-driven build() drives.

Requires: pip install usfmtc

Usage:
  python3 encode.py <path-to.usfm> --lang <iso> --abbr <version-abbr> [--out <path.pkf>]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pkf-encode-py"))
from build_pkf import build_pkf_bytes  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from usj_to_builder import build_from_usj  # noqa: E402

import usfmtc  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--lang", required=True)
    parser.add_argument("--abbr", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    doc = usfmtc.readFile(args.input)
    if doc.errors:
        # Non-fatal — usfmtc reports "unknown tag" warnings for markers
        # outside its own default grammar (e.g. \\zaln-s) while still
        # parsing them correctly via a generic fallback (confirmed
        # directly; see ../pkf-decode-usfmtc-py's equivalent note). Surface
        # them so a real problem doesn't pass silently, but don't abort.
        for err in doc.errors:
            print(f"[pkf-encode-usfmtc] usfmtc warning: {err}", file=sys.stderr)
    usj = doc.outUsj()

    builder = build_from_usj(usj)
    pkf_bytes = build_pkf_bytes(builder, args.lang, args.abbr)

    out_path = Path(args.out) if args.out else Path(args.input).with_suffix(".pkf")
    out_path.write_bytes(pkf_bytes)
    print(f"[pkf-encode-usfmtc] {args.input} -> {out_path} ({len(pkf_bytes)} bytes, book={builder.book_code})")


if __name__ == "__main__":
    main()
