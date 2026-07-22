#!/usr/bin/env python3
"""Fetch a language's PKF manifest entry and .pkf file - no API key needed.
No dependencies beyond the Python standard library.

A .pkf file is a gzip-compressed Proskomma "succinct docSet", not plain
text or USFM - decoding it requires Node (there's no practical Python
equivalent). This script only handles the fetch; see ../../tools/pkf-decode/
for the actual decode step, e.g.:

    node ../../tools/pkf-decode/decode.mjs <iso>.pkf --out out/ --book REV

Usage:
    python3 fetch_pkf.py <iso>
    python3 fetch_pkf.py aai
"""
import json
import sys
import urllib.request

MANIFEST_URL = "https://cdn.bibel.wiki/pkf/manifest.json"
HEADERS = {"User-Agent": "bibles-examples/1.0"}  # Cloudflare 403s urllib's default UA


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as r:
        return r.read()


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: fetch_pkf.py <iso>")
    iso = sys.argv[1]

    manifest = json.loads(fetch(MANIFEST_URL))

    entry = manifest["languages"].get(iso)
    if not entry or not entry.get("collections"):
        print(f"No PKF collection for '{iso}'.")
        return

    collection = entry["collections"][0]
    print(f"Collection info: {json.dumps(collection, indent=2)}")

    pkf_url = f"https://cdn.bibel.wiki/pkf/{iso}/{collection['pkf']}"
    dest = f"{iso}.pkf"
    print(f"Fetching {pkf_url} ...")
    with open(dest, "wb") as f:
        f.write(fetch(pkf_url))
    print(f"Saved to {dest}")
    print()
    print("This is a gzip-compressed Proskomma succinct docSet, not plain text.")
    print(f"Decode it with: node ../../tools/pkf-decode/decode.mjs {dest} --out out/ --book REV")


if __name__ == "__main__":
    main()
