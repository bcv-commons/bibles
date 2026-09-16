#!/usr/bin/env python3
"""Full-corpus round-trip verification for tools/pkf-decode-usfmtc-py and
tools/pkf-encode-usfmtc-py, against every real .pkf file in
internal-data/api-cache/pkf/ (586 files as of 2026-09-19).

Per .pkf file:
  1. Decode with the ORIGINAL, already-validated ../pkf-decode-py (its own
     decode.py CLI, one subprocess per file, directory-batched output).
  2. Re-encode every resulting .usfm with tools/pkf-encode-usfmtc-py's
     logic (via _rt_encode_all.py, one subprocess per file — batched
     per-file rather than per-book purely for speed; the encoding logic
     itself is that package's real usj_to_builder.py + ../pkf-encode-py's
     build_pkf.py, unchanged).
  3. Decode the new .pkf bytes again with ../pkf-decode-py (one more
     subprocess, directory-batched).
  4. Compare extracted verse text (pipeline/core/usfm_to_verses.py,
     usfmtc-based) between step 1 and step 3's output, per book.

Each phase runs in its OWN subprocess deliberately: ../pkf-decode-py and
../pkf-encode-py both define a bare-name module `byte_array.py` (and
`defs.py`) — importing both into one process clobbers sys.modules'
'byte_array' with whichever loaded last (found running this script's
first draft: every load_pkf() call failed with "'ByteArray' object has no
attribute 'from_base64'" because encode-py's byte_array.py, with no such
method, shadowed decode-py's). Separate subprocesses side-step this
entirely — it's how the real CLIs are actually used anyway, so this also
doesn't test anything the public tools don't already guarantee.
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "pipeline" / "core"))
from usfm_to_verses import extract_verses_from_file  # noqa: E402

PKF_DIR = REPO / "internal-data" / "api-cache" / "pkf"
DECODE_PY = REPO / "tools" / "pkf-decode-py" / "decode.py"
ENCODE_ALL = REPO / "tools" / "_rt_encode_all.py"

WORK = Path("/tmp/pkf_rt_work")


def run(args):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True)


def verses_for_dir(d):
    """{book_code: verses_dict} for every *.usfm in d, book_code from the
    NN-BOOK.usfm filename (see decode.py's own BOOK_NUM naming)."""
    out = {}
    for f in sorted(Path(d).glob("*.usfm")):
        stem = f.stem
        book = stem.split("-", 1)[1] if "-" in stem else stem
        try:
            out[book] = extract_verses_from_file(str(f))
        except Exception as e:
            out[book] = {"__parse_error__": f"{type(e).__name__}: {e}"}
    return out


def main():
    pkf_files = sorted(PKF_DIR.rglob("*.pkf"))
    print(f"[verify] {len(pkf_files)} .pkf files under {PKF_DIR}", flush=True)

    totals = {"files": 0, "books": 0, "diffs": 0, "encode_fail": 0,
              "decode1_fail": 0, "decode2_fail": 0}
    fail_log = []

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    start = time.time()
    for i, pkf_path in enumerate(pkf_files, 1):
        rel = pkf_path.relative_to(PKF_DIR)
        src_dir = WORK / "src"
        pkf2_dir = WORK / "pkf2"
        rt_dir = WORK / "rt"
        for d in (src_dir, pkf2_dir, rt_dir):
            if d.exists():
                shutil.rmtree(d)

        r1 = run([str(DECODE_PY), str(pkf_path), "--out", str(src_dir)])
        if r1.returncode != 0 or not any(src_dir.glob("*.usfm")):
            totals["decode1_fail"] += 1
            fail_log.append(f"DECODE1-FAIL {rel}: {(r1.stderr or r1.stdout).strip()[-300:]}")
            continue

        r2 = run([str(ENCODE_ALL), str(src_dir), str(pkf2_dir)])
        for line in r2.stdout.splitlines():
            if line.startswith("ENCODE-FAIL"):
                totals["encode_fail"] += 1
                fail_log.append(f"ENCODE-FAIL {rel}::{line}")

        if not any(pkf2_dir.glob("*.pkf")):
            totals["files"] += 1
            continue

        r3 = run([str(DECODE_PY), str(pkf2_dir), "--out", str(rt_dir)])
        if r3.returncode != 0:
            totals["decode2_fail"] += 1
            fail_log.append(f"DECODE2-FAIL {rel}: {(r3.stderr or r3.stdout).strip()[-300:]}")

        # decode.py in multi-file mode nests output under a subdir named
        # after each input .pkf's stem (see its own `multi` logic) — walk
        # those instead of assuming a flat directory.
        src_verses = verses_for_dir(src_dir)
        rt_verses = {}
        for sub in rt_dir.glob("*"):
            if sub.is_dir():
                rt_verses.update(verses_for_dir(sub))

        totals["files"] += 1
        for book, sv in src_verses.items():
            totals["books"] += 1
            rv = rt_verses.get(book)
            if rv is None:
                totals["diffs"] += 1
                fail_log.append(f"MISSING-BOOK {rel}::{book} (not re-encoded/re-decoded)")
                continue
            if sv != rv:
                totals["diffs"] += 1
                first = None
                for ch in sorted(set(sv) | set(rv)):
                    a, b = sv.get(ch, {}), rv.get(ch, {})
                    if a != b:
                        for vs in sorted(set(a) | set(b), key=lambda x: (len(x), x)):
                            if a.get(vs) != b.get(vs):
                                first = f"ch{ch} v{vs}: orig={a.get(vs)!r:.100} rt={b.get(vs)!r:.100}"
                                break
                    if first:
                        break
                fail_log.append(f"DIFF {rel}::{book}: {first}")

        if i % 20 == 0 or i == len(pkf_files):
            elapsed = time.time() - start
            print(f"[verify] {i}/{len(pkf_files)} files, {totals['files']} processed, "
                  f"{totals['books']} books, {totals['diffs']} diffs, "
                  f"{totals['encode_fail']} encode-fail, {totals['decode1_fail']} decode1-fail, "
                  f"{totals['decode2_fail']} decode2-fail ({elapsed:.0f}s elapsed)", flush=True)

    shutil.rmtree(WORK, ignore_errors=True)

    print("\n[verify] ==== FINAL TOTALS ====")
    print(json.dumps(totals, indent=1))
    print(f"\n[verify] {len(fail_log)} logged issues:")
    for line in fail_log:
        print(" ", line)


if __name__ == "__main__":
    main()
