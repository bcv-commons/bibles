#!/usr/bin/env python3
"""Write per-language copies of the all-language catalog files, next to books.json and
edition-struct.json: export/catalog/<iso[0]>/<iso>/{audio,text,text-route,overlap}.json and
versification.json (from export/dbt/_vrs/index.json).

A client works with one to a few languages; the combined files are 200-430 KB each. Each
per-language file keeps the combined file's keys and shape, holding only that language's
entries, so a client's lookups don't change: only the URL. The combined file's other top-level
fields (base, routes, priority, vrs_base, sentinels, ...) are small and copied as they are.

Versification keys carry no iso for helloAO, PKF and eBible (`helloao:<id>`, `pkf:<iso>_<id>`,
`ebible:<id>`); their iso comes from books.json / edition-struct.json (`h:`, `e:`), the PKF id
itself, or eBible's translations.csv. A key whose iso can't be found is reported, not guessed.

The combined files stay published until their clients have moved (2026-10-26).

    python3 pipeline/comparison/split_catalog.py
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import CATALOG_DIR, DOWNLOADS, EXPORT  # noqa: E402

CANON_FILES = ["audio.json", "text.json", "text-route.json", "overlap.json"]  # entries keyed "<iso>:<canon>"
VRS_INDEX = EXPORT / "dbt" / "_vrs" / "index.json"
VRS_SECTIONS = ["l", "nt", "ot", "assumed"]  # keyed per edition; everything else is copied
EBIBLE_CSV = DOWNLOADS / "ebible" / "translations.csv"


def write(iso: str, name: str, payload: dict) -> None:
    path = CATALOG_DIR / iso[0] / iso / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def split_canon_file(name: str) -> int:
    combined = json.loads((CATALOG_DIR / name).read_text(encoding="utf-8"))
    header = {k: v for k, v in combined.items() if k != "entries"}
    by_iso: dict[str, dict] = {}
    for key, value in combined["entries"].items():
        by_iso.setdefault(key.split(":")[0], {})[key] = value
    for iso, entries in by_iso.items():
        write(iso, name, {**header, "entries": entries})
    return len(by_iso)


def edition_isos() -> dict[str, str]:
    """Catalog id (`h:<id>`, `e:<id>`) -> iso, from the per-language files already written."""
    out = {}
    for name in ("books.json", "edition-struct.json"):
        for f in CATALOG_DIR.glob(f"*/*/{name}"):
            data = json.loads(f.read_text(encoding="utf-8"))
            for key in data.get("entries") or data.get("editions") or {}:
                out.setdefault(key, f.parent.name)
    if EBIBLE_CSV.exists():
        with EBIBLE_CSV.open(encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                out.setdefault(f"e:{row['translationId']}", row["languageCode"])
    return out


def vrs_iso(key: str, isos: dict[str, str]) -> str | None:
    if "/" in key:
        return key.split("/")[0]  # DBT: <iso>/<abbr>
    source, ident = key.split(":", 1)
    if source == "pkf":
        return ident.split("_")[0]  # <iso>_<collection>
    return isos.get({"helloao": "h:", "ebible": "e:"}.get(source, "?") + ident)


def split_vrs() -> int:
    combined = json.loads(VRS_INDEX.read_text(encoding="utf-8"))
    header = {k: v for k, v in combined.items() if k not in VRS_SECTIONS}
    isos = edition_isos()
    by_iso: dict[str, dict] = {}
    unplaced = []
    for section in VRS_SECTIONS:
        for key, value in combined.get(section, {}).items():
            iso = vrs_iso(key, isos)
            if not iso:
                unplaced.append(key)
                continue
            by_iso.setdefault(iso, {s: {} for s in VRS_SECTIONS})[section][key] = value
    for iso, sections in by_iso.items():
        write(iso, "versification.json", {**header, **{s: v for s, v in sections.items() if v}})
    if unplaced:
        print(f"[split-catalog] versification: no iso for {len(unplaced)} key(s): {sorted(set(unplaced))[:10]}")
    return len(by_iso)


def main():
    for name in CANON_FILES:
        if (CATALOG_DIR / name).exists():
            print(f"[split-catalog] {name}: {split_canon_file(name)} languages")
        else:
            print(f"[split-catalog] {name}: not found, skipped")
    if VRS_INDEX.exists():
        print(f"[split-catalog] versification.json (from dbt/_vrs/index.json): {split_vrs()} languages")


if __name__ == "__main__":
    main()
