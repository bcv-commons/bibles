#!/usr/bin/env python3
"""Fetch every real .pkf file listed in internal-data/api-cache/pkf-manifest.json
into internal-data/api-cache/pkf/<iso>/<file> — the test corpus for verifying
the Python/Rust PKF-decode sibling implementations against decode.mjs
byte-for-byte. Same rclone/R2 mechanism as pipeline/comparison/fetch_sources.py's
pkf_text() (reused directly, not reimplemented). Resumable: skips files that
already exist locally with the expected size.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline" / "comparison"))
from fetch_sources import rclone_env  # noqa: E402

API_CACHE = ROOT / "internal-data" / "api-cache"
MANIFEST = API_CACHE / "pkf-manifest.json"
OUT_DIR = API_CACHE / "pkf"


def main():
    manifest = json.loads(MANIFEST.read_text())["languages"]
    env, bucket = rclone_env()

    todo = []
    for iso, entry in manifest.items():
        for c in entry.get("collections", []):
            fname = c["pkf"]
            expected = c.get("pkf_bytes")
            dest = OUT_DIR / iso / fname
            if dest.exists() and (expected is None or dest.stat().st_size == expected):
                continue
            todo.append((iso, fname, expected, dest))

    total = sum(len(e.get("collections", [])) for e in manifest.values())
    print(f"[fetch_pkf_corpus] {total - len(todo)}/{total} already cached, fetching {len(todo)}")

    ok = fail = 0
    for i, (iso, fname, expected, dest) in enumerate(todo, 1):
        dest.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["rclone", "copyto", f"R2:{bucket}/pkf/{iso}/{fname}", str(dest)],
            capture_output=True, text=True, env=env,
        )
        if result.returncode != 0 or not dest.exists():
            fail += 1
            print(f"[{i}/{len(todo)}] FAIL {iso}/{fname}: {result.stderr.strip()[:200]}")
            continue
        if expected is not None and dest.stat().st_size != expected:
            fail += 1
            print(f"[{i}/{len(todo)}] SIZE MISMATCH {iso}/{fname}: got {dest.stat().st_size}, expected {expected}")
            continue
        ok += 1
        if i % 25 == 0 or i == len(todo):
            print(f"[{i}/{len(todo)}] fetched ({ok} ok, {fail} fail so far)")

    print(f"[fetch_pkf_corpus] done: {ok} fetched, {fail} failed")


if __name__ == "__main__":
    main()
