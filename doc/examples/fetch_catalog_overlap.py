#!/usr/bin/env python3
"""Resolve the distinct options + recommended default for a language from
catalog-overlap.json. No dependencies beyond the Python standard library.

Usage:
    python3 fetch_catalog_overlap.py <iso> [canon]
    python3 fetch_catalog_overlap.py spa nt
"""
import json
import sys
import urllib.request

URL = "https://cdn.bibel.wiki/dbt/_app/catalog-overlap.json"


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: fetch_catalog_overlap.py <iso> [canon]")
    iso = sys.argv[1]
    canon = sys.argv[2] if len(sys.argv) > 2 else "nt"

    # Cloudflare (fronting cdn.bibel.wiki) rejects urllib's default
    # User-Agent with a 403 - always set a real one.
    req = urllib.request.Request(URL, headers={"User-Agent": "bibles-examples/1.0"})
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())

    matches = [row for row in data["entries"] if row[0] == iso and row[1] == canon]
    if not matches:
        print(f"No comparison data for '{iso}' ({canon}). Either only one source exists "
              f"for this language, or nothing has been compared yet - check "
              f"catalog-index.json instead.")
        return

    print(f"Distinct options for '{iso}' ({canon}):")
    for _, _, cluster in matches:
        ids = cluster["ids"]
        default = cluster.get("default", ids[0])
        alternatives = [i for i in ids if i != default]
        line = f"  -> {default}"
        if alternatives:
            line += f"  (identical to: {', '.join(alternatives)})"
        print(line)
        if "likely" in cluster:
            print(f"     not identical to anything - closest is {cluster['closest']} "
                  f"({cluster['likely']}, score {cluster['score']})")


if __name__ == "__main__":
    main()
