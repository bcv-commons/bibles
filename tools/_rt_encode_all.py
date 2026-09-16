#!/usr/bin/env python3
"""Internal helper for verify_pkf_usfmtc_roundtrip.py — NOT a public
example (unlike tools/pkf-encode-usfmtc-py/encode.py, which stays
single-file-only to keep its CLI contract simple). Encodes every *.usfm
in a directory to .pkf in one process (batched per source .pkf file,
instead of one subprocess per book) purely to keep the full-corpus
verification run fast — the encoding logic itself is unchanged, still
tools/pkf-encode-usfmtc-py's usj_to_builder.py + ../pkf-encode-py's
build_pkf.py.

Usage: python3 _rt_encode_all.py <dir-of-.usfm> <out-dir>
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools" / "pkf-encode-py"))
sys.path.insert(0, str(REPO / "tools" / "pkf-encode-usfmtc-py"))

from build_pkf import build_pkf_bytes  # noqa: E402
from usj_to_builder import build_from_usj  # noqa: E402
import usfmtc  # noqa: E402


def main():
    in_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    for usfm_path in sorted(in_dir.glob("*.usfm")):
        try:
            doc = usfmtc.readFile(str(usfm_path))
            usj = doc.outUsj()
            builder = build_from_usj(usj)
            pkf_bytes = build_pkf_bytes(builder, "xx", usfm_path.stem)
            (out_dir / f"{usfm_path.stem}.pkf").write_bytes(pkf_bytes)
        except Exception as e:
            print(f"ENCODE-FAIL {usfm_path.name}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
