#!/usr/bin/env python3
"""Verify pkf-encode-py round-trips: decode a real .pkf via pkf-decode-py,
re-encode that USFM via pkf-encode-py, decode the re-encoded .pkf again
using the REAL decode.mjs (not pkf-decode-py — see below), and diff the
two decoded USFM texts — they should be identical (decode is
deterministic; if the encoder faithfully captured everything the first
decode pass produced, encoding it and decoding again must reproduce the
same text).

The second decode MUST go through the real, installed proskomma-core
library (decode.mjs), not pkf-decode-py, even though the two are already
verified byte-for-byte identical on real .pkf files. Confirmed by direct
experience: an earlier version of this script used pkf-decode-py for both
decodes and reported 1077/1077 clean, but the encoder had a real bug (a
sequential seq1/seq2/.../seq10/seq11 graft-target id scheme, where "seq1"
being a literal string prefix of "seq10" etc. caused the REAL library to
silently resolve the wrong footnote's content — pkf-decode-py has no such
bug, so it decoded the exact same corrupted bytes correctly and the
mismatch never surfaced). The two decoders being independently verified
identical on *real* PKF content doesn't guarantee they behave identically
on content this encoder is capable of producing but real PKF never
happens to — only decoding through the real library actually tests "is
this genuinely valid, loadable PKF."

This is the only realistic test corpus available: no first-published-here
content exists yet (see the conversation that led to this script), so real
PKF content's own decoded USFM stands in for it. Since pkf-encode-py only
supports a subset of USFM (see tools/pkf-encode-py/usfm_lexer.py), most
real books will fail to encode at all (unsupported marker) — that's
expected and reported separately from actual round-trip mismatches, which
are the real bug signal.

Usage:
  python3 verify_pkf_encode_roundtrip.py [--sample N] [--seed N] [--book BOOKCODE]
"""
import argparse
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKF_DIR = ROOT / "internal-data" / "api-cache" / "pkf"
DECODE_PY = ROOT / "tools" / "pkf-decode-py" / "decode.py"
DECODE_JS = ROOT / "tools" / "pkf-decode" / "decode.mjs"
ENCODE_PY = ROOT / "tools" / "pkf-encode-py" / "encode.py"


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def verify_one(pkf_path, book_filter):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        first_out = tmp / "first"
        r = run(["python3", str(DECODE_PY), str(pkf_path), "--out", str(first_out)]
                + (["--book", book_filter] if book_filter else []))
        if r.returncode != 0:
            return [], []

        results = []
        errors = []
        for usfm_path in sorted(first_out.glob("*.usfm")):
            lang = pkf_path.parent.name
            book = usfm_path.stem.split("-", 1)[-1]
            reencoded = tmp / f"{book}.pkf"
            r = run(["python3", str(ENCODE_PY), str(usfm_path), "--lang", lang, "--abbr", "RT",
                     "--out", str(reencoded)])
            if r.returncode != 0:
                errors.append((pkf_path, book, "encode_unsupported", r.stderr.strip().splitlines()[-1] if r.stderr else ""))
                continue

            second_out = tmp / f"{book}_second"
            r = run(["node", str(DECODE_JS), str(reencoded), "--out", str(second_out)])
            if r.returncode != 0:
                errors.append((pkf_path, book, "reencode_decode_error", r.stderr.strip().splitlines()[-1] if r.stderr else ""))
                continue

            second_files = list(second_out.glob("*.usfm"))
            if len(second_files) != 1:
                errors.append((pkf_path, book, "unexpected_book_count", str(len(second_files))))
                continue

            original_text = usfm_path.read_text()
            roundtrip_text = second_files[0].read_text()
            if original_text == roundtrip_text:
                results.append((pkf_path, book, "ok"))
            else:
                errors.append((pkf_path, book, "mismatch", _first_diff(original_text, roundtrip_text)))
        return results, errors


def _first_diff(a, b):
    for i, (ca, cb) in enumerate(zip(a, b)):
        if ca != cb:
            return f"at char {i}: ...{a[max(0,i-30):i+30]!r} vs ...{b[max(0,i-30):i+30]!r}"
    return f"length differs: {len(a)} vs {len(b)}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--book", default=None, help="restrict to one book code, e.g. REV")
    args = parser.parse_args()

    all_pkfs = sorted(PKF_DIR.glob("*/*.pkf"))
    if not all_pkfs:
        print(f"No .pkf files found under {PKF_DIR}", file=sys.stderr)
        sys.exit(1)
    random.seed(args.seed)
    targets = random.sample(all_pkfs, min(args.sample, len(all_pkfs)))

    ok_count = 0
    unsupported_count = 0
    mismatches = []
    other_errors = []
    for i, pkf_path in enumerate(targets, 1):
        results, errors = verify_one(pkf_path, args.book)
        ok_count += len(results)
        for _, book, kind, detail in errors:
            if kind == "encode_unsupported":
                unsupported_count += 1
            elif kind == "mismatch":
                mismatches.append((pkf_path, book, detail))
            else:
                other_errors.append((pkf_path, book, kind, detail))
        print(f"[{i}/{len(targets)}] {pkf_path.name}: {len(results)} ok, "
              f"{sum(1 for e in errors if e[2] == 'encode_unsupported')} unsupported, "
              f"{sum(1 for e in errors if e[2] == 'mismatch')} MISMATCH", flush=True)

    print(f"\nFinal: {ok_count} round-tripped ok, {unsupported_count} unsupported marker (expected, v1 scope), "
          f"{len(mismatches)} real mismatches, {len(other_errors)} other errors")
    if mismatches:
        print("\nMismatches:")
        for path, book, detail in mismatches[:20]:
            print(f"  {path.relative_to(ROOT)} {book}: {detail}")
    if other_errors:
        print("\nOther errors:")
        for path, book, kind, detail in other_errors[:20]:
            print(f"  {path.relative_to(ROOT)} {book}: {kind} — {detail}")
    sys.exit(1 if (mismatches or other_errors) else 0)


if __name__ == "__main__":
    main()
