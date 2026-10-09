#!/usr/bin/env python3
"""Add publish details to catalog/openbible-editions.json, so a client can choose an
openbible edition without fetching every _meta.json (requested by demo-bibel-wiki,
2026-10-09).

Each entry keeps `abbr` and `iso` (generate_openbible_abbr.py) and gains:
    published  true when the edition's Sofria + USJ are built and staged for the CDN
    books      book codes published (books with at least one chapter)
    canon      "nt" | "ntp" | "ot" | "otp" values the books cover (p = portions)
    licenses   as in the edition's _meta.json
    path       the edition folder on the CDN, relative to cdn.bibel.wiki
or, when not published:
    published  false
    reason     "nd_license" (only no-derivatives licenses), "no_source" (Biblica's
               text zip or project record isn't cached), or "not_built"
A top-level `formats` gives the file patterns inside an edition folder.

Run after generate_openbible_usj.py and the Sofria conversion (make stage-sofria);
generate_openbible_abbr.py rewrites the file without these fields.

Usage:
    python3 pipeline/core/enrich_openbible_editions.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edition_formats import FORMATS, META_FILE  # noqa: E402
from generate_openbible_usj import current_licenses, has_non_nd_license  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, CATALOG_DIR, EXPORT  # noqa: E402

EDITIONS_FILE = CATALOG_DIR / "openbible-editions.json"
USJ_DIR = EXPORT / "openbible-usj"
STAGE_DIR = EXPORT / "publish" / "stage" / "openbible"
TEXT_CACHE = API_CACHE / "openbible" / "text"
ZIP_CACHE = API_CACHE / "openbible" / "text-zips"

NT = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL", "1TH",
      "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"}
OT = {"GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA", "1KI", "2KI", "1CH",
      "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO", "ECC", "SNG", "ISA", "JER", "LAM", "EZK",
      "DAN", "HOS", "JOL", "AMO", "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL"}


def canon(books: set) -> list[str]:
    out = []
    if NT <= books:
        out.append("nt")
    elif books & NT:
        out.append("ntp")
    if OT <= books:
        out.append("ot")
    elif books & OT:
        out.append("otp")
    return out


def main() -> None:
    doc = json.loads(EDITIONS_FILE.read_text(encoding="utf-8"))
    counts = {"published": 0, "nd_license": 0, "no_source": 0, "not_built": 0}
    for project_id, e in doc["entries"].items():
        base = {"abbr": e["abbr"], "iso": e["iso"]}
        meta_path = USJ_DIR / e["iso"] / e["abbr"] / META_FILE
        staged = STAGE_DIR / e["iso"] / e["abbr"] / META_FILE
        if meta_path.is_file() and staged.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            books = set(meta.get("books", []))
            doc["entries"][project_id] = {**base, "published": True, "books": sorted(books),
                                          "canon": canon(books), "licenses": meta.get("licenses", []),
                                          "path": f"openbible/{e['iso']}/{e['abbr']}/"}
            counts["published"] += 1
            continue
        detail_path = TEXT_CACHE / f"{project_id}.json"
        if not detail_path.is_file() or not (ZIP_CACHE / f"{project_id}.zip").is_file():
            reason = "no_source"
        elif not has_non_nd_license(current_licenses(json.loads(detail_path.read_text(encoding="utf-8")))):
            reason = "nd_license"
        else:
            reason = "not_built"
        doc["entries"][project_id] = {**base, "published": False, "reason": reason}
        counts[reason] += 1
    doc["formats"] = FORMATS
    doc["note"] = ("project_id -> yaapi.bible edition abbreviation + iso, and whether it is published: "
                   "books, canon, licenses and the CDN folder (path); formats gives the file patterns "
                   "inside that folder. Only covers projects with a real yaapi.bible match "
                   "(see doc/openbible-chapters.md).")
    EDITIONS_FILE.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"[openbible-editions] {len(doc['entries'])} editions: {counts} -> {EDITIONS_FILE}")


if __name__ == "__main__":
    main()
