#!/usr/bin/env python3
"""Upload dbt/_vrs/index.json and dbt/_vrs/irregular.json, nothing else, and check the
live sha256 of each. (publish-dbt.sh would also push the whole dbt/ tree.)

Usage:
    python3 pipeline/core/publish_vrs_index.py [--dry-run]
"""
import hashlib
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comparison"))
from fetch_sources import rclone_env  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import EXPORT  # noqa: E402

FILES = ["index.json", "irregular.json"]


def main() -> None:
    dry = "--dry-run" in sys.argv
    env, bucket = rclone_env()
    for name in FILES:
        local = EXPORT / "dbt" / "_vrs" / name
        h = hashlib.sha256(local.read_bytes()).hexdigest()
        if dry:
            print(f"[dry run] would upload {local} -> dbt/_vrs/{name}  sha256 {h}")
            continue
        subprocess.run(["rclone", "copyto", str(local), f"R2:{bucket}/dbt/_vrs/{name}",
                        "--header-upload", "Cache-Control: max-age=3600"], env=env, check=True)
        req = urllib.request.Request(f"https://cdn.bibel.wiki/dbt/_vrs/{name}?v={time.time()}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        live = hashlib.sha256(urllib.request.urlopen(req, timeout=30).read()).hexdigest()
        print(f"  {'OK  ' if live == h else 'DIFF'}  dbt/_vrs/{name}  {live}")


if __name__ == "__main__":
    main()
