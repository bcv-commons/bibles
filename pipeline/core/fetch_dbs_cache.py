#!/usr/bin/env python3
"""Fetch Digital Bible Society bible catalog to local cache.

Downloads all JSON files from:
  https://github.com/digitalbiblesociety/data/tree/main/bibles

Output: api-cache/dbs/bibles/*.json
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE  # noqa: E402

CACHE_DIR = API_CACHE / "dbs" / "bibles"
REPO = "digitalbiblesociety/data"
API_PATH = "repos/{}/contents/bibles"


def fetch_file_list():
    """Get list of all JSON files using Git Trees API (no pagination limit)."""
    cmd = [
        "gh", "api",
        f"repos/{REPO}/git/trees/main?recursive=1",
        "--jq", '.tree[] | select(.path | startswith("bibles/")) | .path',
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error listing files: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    # Extract just the filename from "bibles/XXXX.json"
    return [
        p.split("/", 1)[1]
        for p in result.stdout.strip().splitlines()
        if p.endswith(".json")
    ]


def download_file(filename):
    """Download a single JSON file from the repo."""
    cmd = [
        "gh", "api",
        f"repos/{REPO}/contents/bibles/{filename}",
        "--jq", ".content",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    import base64
    try:
        return base64.b64decode(result.stdout.strip()).decode("utf-8")
    except Exception:
        return None


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("[INFO] Fetching file list from DBS data repo...")
    files = fetch_file_list()
    print(f"[INFO] Found {len(files)} JSON files")

    existing = {f.name for f in CACHE_DIR.glob("*.json")}
    to_download = [f for f in files if f not in existing]
    already = len(files) - len(to_download)

    if already:
        print(f"[INFO] Already cached: {already}")
    if not to_download:
        print("[INFO] All files cached, nothing to download")
        return

    print(f"[INFO] Downloading {len(to_download)} files...")

    # Batch download using raw.githubusercontent.com for speed
    import urllib.request
    import urllib.error

    RAW_URL = "https://raw.githubusercontent.com/{}/main/bibles/{}".format(REPO, "{}")

    success = 0
    failed = 0
    for i, filename in enumerate(to_download, 1):
        if i % 100 == 0 or i == 1:
            print(f"  [{i}/{len(to_download)}] {filename}")
        url = RAW_URL.format(filename)
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8")
            # Validate JSON
            json.loads(content)
            (CACHE_DIR / filename).write_text(content, encoding="utf-8")
            success += 1
        except (urllib.error.URLError, json.JSONDecodeError, Exception) as e:
            print(f"  FAILED: {filename}: {e}")
            failed += 1

    print(f"\n[INFO] Done: {success} downloaded, {failed} failed, {already} already cached")
    print(f"[INFO] Total cached: {len(list(CACHE_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
