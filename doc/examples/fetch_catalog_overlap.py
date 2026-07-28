#!/usr/bin/env python3
"""Resolve the distinct options + a recommended default for a language from
catalog-overlap.json. No dependencies beyond the Python standard library.

No `default` field is published (removed 2026-07-28) - it's a one-line
computation from `priority` + `ids` that every client can do itself, so
this example does exactly that rather than relying on a precomputed field.

Usage:
    python3 fetch_catalog_overlap.py <iso> [canon]
    python3 fetch_catalog_overlap.py spa nt
"""
import json
import sys
import urllib.request

URL = "https://cdn.bibel.wiki/dbt/_app/catalog-overlap.json"
SOURCE_NAME = {"d": "dbt", "h": "helloao", "p": "pkf"}


def pick_default(ids, priority):
    rank = {name: i for i, name in enumerate(priority)}
    return min(ids, key=lambda i: rank[SOURCE_NAME[i.split(":", 1)[0]]])


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

    clusters = data["entries"].get(f"{iso}:{canon}")
    if not clusters:
        print(f"No comparison data for '{iso}' ({canon}). Either only one candidate exists "
              f"for this language (nothing to compare against - check catalog-index.json), "
              f"or nothing has been fetched yet.")
        return

    print(f"Distinct options for '{iso}' ({canon}):")
    for cluster in clusters:
        ids = cluster["ids"]
        if cluster.get("r") is False:
            note = " [CONFIRMED REMOVED]" if cluster.get("confirmed_removed") else " [currently unreachable]"
            print(f"  {ids[0]}{note}")
            continue
        default = pick_default(ids, data["priority"])
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
