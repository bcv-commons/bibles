#!/usr/bin/env python3
"""Look up what's available for a language from catalog-index.json.
No dependencies beyond the Python standard library.

Usage:
    python3 fetch_catalog_index.py <iso>
    python3 fetch_catalog_index.py spa
"""
import json
import sys
import urllib.request

URL = "https://cdn.bibel.wiki/catalog/index.json"
SOURCE_NAMES = {"d": "DBT", "p": "PKF", "h": "helloAO"}


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: fetch_catalog_index.py <iso>")
    iso = sys.argv[1]

    # Cloudflare (fronting cdn.bibel.wiki) rejects urllib's default
    # User-Agent with a 403 - always set a real one.
    req = urllib.request.Request(URL, headers={"User-Agent": "bibles-examples/1.0"})
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())

    matches = [row for row in data["entries"] if row[0] == iso]
    if not matches:
        print(f"No entries found for '{iso}'.")
        return

    print(f"Availability for '{iso}':")
    for row in matches:
        canon, source = row[1], row[2]
        count = row[3] if len(row) > 3 else 1
        portions = " (Portions - partial coverage)" if canon.endswith("p") else ""
        print(f"  {canon:4s} {SOURCE_NAMES[source]:8s} {count} version(s){portions}")


if __name__ == "__main__":
    main()
