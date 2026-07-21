#!/usr/bin/env python3
"""
Publish a DBT-style-fileset-id -> helloAO-translation-id crosswalk.

helloAO's own translation IDs are DBT-style IDs with letters lowercased and
an underscore inserted (e.g. DBT "GAZBIB" -> helloAO "gaz_bib"). This is a
convention helloAO applies on import, not a coincidence to statistically
verify against a separate catalog — so the crosswalk is built purely from
helloAO's own published catalog: for every helloAO id, the reverse transform
(uppercase, strip underscore) IS the DBT-style id it corresponds to.

This fixes the class of bug where downstream clients try to query helloAO
using a raw DBT fileset id directly (which doesn't match helloAO's own id
scheme) and silently get no results.

Usage:
    python3 generate_helloao_crosswalk.py

Reads:  internal-data/api-cache/helloao/available_translations.json (fetch_helloao_cache.py)
Writes: export/dbt/_helloao-crosswalk.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, EXPORT  # noqa: E402

CATALOG = API_CACHE / "helloao" / "available_translations.json"
OUT_PATH = EXPORT / "dbt" / "_helloao-crosswalk.json"


def main():
    if not CATALOG.exists():
        raise SystemExit(f"{CATALOG} not found. Run: python3 fetch_helloao_cache.py")

    translations = json.loads(CATALOG.read_text())["translations"]

    crosswalk = {}
    collisions = []
    for entry in translations:
        hid = entry["id"]
        dbt_style = hid.upper().replace("_", "")
        if dbt_style in crosswalk and crosswalk[dbt_style] != hid:
            collisions.append((dbt_style, crosswalk[dbt_style], hid))
        crosswalk[dbt_style] = hid

    if collisions:
        # Two helloAO ids collapsing to the same DBT-style id would make the
        # map ambiguous — surface it instead of silently picking one.
        raise SystemExit(f"[ERROR] {len(collisions)} colliding DBT-style ids: {collisions[:5]}")

    output = {
        "description": (
            "DBT-style fileset id -> helloAO translation id. Derived from "
            "helloAO's own catalog (id = DBT id lowercased with '_' inserted); "
            "look up your DBT fileset id here before querying the helloAO API."
        ),
        "source": "helloAO's own published translation catalog (available_translations.json)",
        "helloao_api_base": "https://bible.helloao.org/api",
        "count": len(crosswalk),
        "map": dict(sorted(crosswalk.items())),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[helloao-crosswalk] {len(crosswalk)} entries -> {OUT_PATH}")


if __name__ == "__main__":
    main()
