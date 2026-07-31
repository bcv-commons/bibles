#!/usr/bin/env python3
"""Verify the Python and Rust pkf-decode siblings both produce byte-for-byte
identical output to the reference decode.mjs, across the real PKF corpus
(internal-data/api-cache/pkf/, fetched via scripts/fetch_pkf_corpus.py).

This is the actual correctness gate for pkf-decode-py/ and pkf-decode-rs/ —
proskomma-core's succinct/PERF format has no published spec, so "does it
match the real installed library's real output" is the only ground truth.
Run after any change to either sibling, and periodically as the corpus
grows.

Usage:
  python3 verify_pkf_decode.py [--sample N] [--seed N] [--only py|rs]
"""
import argparse
import filecmp
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKF_DIR = ROOT / "internal-data" / "api-cache" / "pkf"
JS_DECODE = ROOT / "tools" / "pkf-decode" / "decode.mjs"
PY_DECODE = ROOT / "tools" / "pkf-decode-py" / "decode.py"
RS_BIN = ROOT / "tools" / "pkf-decode-rs" / "target" / "release" / "pkf-decode"


def decode_with(cmd, pkf_path, out_dir):
    result = subprocess.run(cmd + [str(pkf_path), "--out", str(out_dir)],
                             capture_output=True, text=True)
    return result.returncode == 0, result.stderr


def diff_dirs(ref_dir, ref_name, other_dir, other_name):
    ref_files = sorted(p.name for p in ref_dir.glob("*.usfm")) if ref_dir.is_dir() else []
    other_files = sorted(p.name for p in other_dir.glob("*.usfm")) if other_dir.is_dir() else []
    if ref_files != other_files:
        return "file_list_mismatch", f"{ref_name}={ref_files} {other_name}={other_files}"
    mismatches = [name for name in ref_files if not filecmp.cmp(ref_dir / name, other_dir / name, shallow=False)]
    if mismatches:
        return "content_mismatch", ",".join(mismatches)
    return "ok", None


def verify_one(pkf_path, langs):
    with tempfile.TemporaryDirectory() as tmp:
        js_out = Path(tmp) / "js"
        js_ok, js_err = decode_with(["node", str(JS_DECODE)], pkf_path, js_out)
        if not js_ok:
            return {lang: ("js_error", js_err[:300]) for lang in langs}

        results = {}
        for lang in langs:
            out_dir = Path(tmp) / lang
            if lang == "py":
                ok, err = decode_with([sys.executable, str(PY_DECODE)], pkf_path, out_dir)
            else:
                ok, err = decode_with([str(RS_BIN)], pkf_path, out_dir)
            if not ok:
                results[lang] = (f"{lang}_error", err[:300])
                continue
            results[lang] = diff_dirs(js_out, "js", out_dir, lang)
        return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None, help="random sample size (default: all)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--only", choices=["py", "rs"], default=None)
    args = parser.parse_args()

    langs = [args.only] if args.only else ["py", "rs"]
    if "rs" in langs and not RS_BIN.exists():
        print(f"Rust binary not found at {RS_BIN} — run: cd tools/pkf-decode-rs && cargo build --release", file=sys.stderr)
        sys.exit(1)

    all_pkfs = sorted(PKF_DIR.glob("*/*.pkf"))
    if not all_pkfs:
        print(f"No .pkf files found under {PKF_DIR} — run scripts/fetch_pkf_corpus.py first", file=sys.stderr)
        sys.exit(1)

    targets = all_pkfs
    if args.sample and args.sample < len(all_pkfs):
        random.seed(args.seed)
        targets = random.sample(all_pkfs, args.sample)

    counts = {lang: {} for lang in langs}
    failures = []
    start = time.monotonic()
    for i, pkf_path in enumerate(targets, 1):
        t0 = time.monotonic()
        results = verify_one(pkf_path, langs)
        elapsed = time.monotonic() - t0
        for lang, (status, detail) in results.items():
            counts[lang][status] = counts[lang].get(status, 0) + 1
            if status != "ok":
                failures.append((pkf_path, lang, status, detail))
        avg = (time.monotonic() - start) / i
        eta = avg * (len(targets) - i)
        # Real per-file heartbeat, not just every-20 batches — a single slow
        # file (more books/larger content) used to look indistinguishable
        # from a hang for up to several minutes.
        print(f"  [{i}/{len(targets)}] {pkf_path.name} ({elapsed:.1f}s, ~{eta/60:.1f}m left) "
              f"{ {lang: r[0] for lang, r in results.items()} }", flush=True)
        if i % 20 == 0 or i == len(targets):
            print(f"[{i}/{len(targets)}] {counts}")

    print(f"\nFinal: {counts}")
    if failures:
        print(f"\n{len(failures)} failure(s):")
        for path, lang, status, detail in failures[:50]:
            print(f"  [{lang}] {path.relative_to(ROOT)}: {status} — {detail}")
        sys.exit(1)
    print("All matched byte-for-byte.")


if __name__ == "__main__":
    main()
