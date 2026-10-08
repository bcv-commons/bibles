#!/usr/bin/env python3
"""One merged metadata record per catalog edition, simplified from lexeme-aligner's
eval/edition_struct.py to fit our own catalog instead of their ingest-time pins.

Their version resolves `iso` via publish/compact-alignments/manifest.json (their own
onboarding record) and `pinned` fields via config/pins/<tag>.json (their ingest-time
snapshot of each source's own record). We don't have, and don't need, either: `iso`
already matches ours exactly for DBT/PKF/helloAO/openbible-sourced tags (verified
2026-10-07 against their own aaamlt.json), and the "pinned" fields they could not
derive from a source catalog (sha256 of their fetched file, their own ingested book
count) are theirs alone, not something a catalog merge can ever give us anyway.

So this reads metadata we already cache locally — no live network calls — and merges
it with textual_basis.py's own output (pipeline/comparison/textual_basis.py) where
available. id format matches catalog-overlap.json's own convention (d:/h:/p:/o:
prefix), not lexeme-aligner's lowercase "tag" — one less naming scheme to carry.

Usage:
    python3 pipeline/comparison/edition_struct.py --scan   # every candidate edition
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_all import all_candidates, OPENBIBLE_PROJECTS_FILE, OPENBIBLE_EDITIONS_FILE  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, CATALOG_DIR, COMPARISON_RESULTS_DIR  # noqa: E402

OUT_PATH = CATALOG_DIR / "edition-struct.json"  # the one file we actually publish
BIBLE_DETAILS_DIR = API_CACHE / "bibles" / "bible_details"
OPENBIBLE_TEXT_CACHE = API_CACHE / "openbible" / "text"
# Internal build artifact, not published on its own — see its own module
# docstring in textual_basis.py for why. We just fold its verdict in here.
TEXTUAL_BASIS_FILE = COMPARISON_RESULTS_DIR / "textual-basis.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def dbt_record(distinct_id: str, iso: str) -> dict:
    detail = _load_json(BIBLE_DETAILS_DIR / f"{distinct_id}.json").get("data", {})
    return {
        "iso": iso, "provider": "DBT (4.dbt.io)",
        "name": detail.get("name"), "license": detail.get("mark"),
        "script": (detail.get("alphabet") or {}).get("script"),
    }


def helloao_record(translation_id: str, iso: str, helloao_translations: dict) -> dict:
    e = helloao_translations.get(translation_id, {})
    return {
        "iso": iso, "provider": "helloAO",
        "name": e.get("name"), "license": e.get("licenseUrl"),
        "script": None if e.get("textDirection") is None else
                  ("Latn" if e["textDirection"] == "ltr" else None),
    }


def pkf_record(iso: str, pkf_manifest: dict) -> dict:
    entry = pkf_manifest.get(iso) or {}
    return {"iso": iso, "provider": "PKF", "name": entry.get("nm"), "license": None, "script": None}


def openbible_record(project_id: str, abbr: str, iso: str) -> dict:
    detail = _load_json(OPENBIBLE_TEXT_CACHE / f"{project_id}.json").get("project", {})
    return {
        "iso": iso, "provider": "openbible (Biblica)",
        "name": detail.get("title"), "license": detail.get("rightsHolder"),
        "script": detail.get("script"),
    }


def main() -> None:
    if "--scan" not in sys.argv:
        print("[edition-struct] pass --scan")
        return

    catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())
    helloao_translations_list = json.loads((API_CACHE / "helloao" / "available_translations.json").read_text())["translations"]
    helloao_translations = {e["id"]: e for e in helloao_translations_list}
    helloao_by_iso = defaultdict(list)
    for e in helloao_translations_list:
        helloao_by_iso[e["language"]].append(e["id"])
    pkf_manifest = json.loads((API_CACHE / "pkf-manifest.json").read_text())["languages"]
    openbible_projects = json.loads(OPENBIBLE_PROJECTS_FILE.read_text()) if OPENBIBLE_PROJECTS_FILE.exists() else []
    openbible_by_iso = defaultdict(list)
    for p in openbible_projects:
        if p.get("type") == "text" and not p.get("disabled"):
            openbible_by_iso[p["languageCode"]].append(p["id"])
    openbible_abbr = (json.loads(OPENBIBLE_EDITIONS_FILE.read_text())["entries"]
                      if OPENBIBLE_EDITIONS_FILE.exists() else {})
    textual_basis = _load_json(TEXTUAL_BASIS_FILE).get("editions", {})

    editions: dict[str, dict] = {}
    for canon in ("nt", "ot"):
        candidates = all_candidates(catalog, helloao_by_iso, pkf_manifest, openbible_by_iso, openbible_abbr, canon)
        for iso, (dbt_ids, hao_ids, pkf_files, ob_ids) in candidates.items():
            for distinct_id in dbt_ids:
                editions[f"d:{distinct_id}"] = dbt_record(distinct_id, iso)
                tb = textual_basis.get(f"{iso}:dbt:{distinct_id}")
                if tb:
                    editions[f"d:{distinct_id}"]["textual_basis"] = tb["verdict"]
            for hid in hao_ids:
                editions[f"h:{hid}"] = helloao_record(hid, iso, helloao_translations)
                tb = textual_basis.get(f"{iso}:helloao:{hid}")
                if tb:
                    editions[f"h:{hid}"]["textual_basis"] = tb["verdict"]
            if pkf_files:
                editions[f"p:{iso.upper()}PKF"] = pkf_record(iso, pkf_manifest)
                tb = textual_basis.get(f"{iso}:pkf:{iso.upper()}PKF")
                if tb:
                    editions[f"p:{iso.upper()}PKF"]["textual_basis"] = tb["verdict"]
            for project_id, abbr in ob_ids:
                editions[f"o:{abbr}"] = openbible_record(project_id, abbr, iso)
                tb = textual_basis.get(f"{iso}:openbible:{abbr}")
                if tb:
                    editions[f"o:{abbr}"]["textual_basis"] = tb["verdict"]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "note": "iso/name/license/script merged from our own cached source catalogs (DBT bible_details, "
                "helloAO available_translations, PKF manifest, openbible project cache) — no live fetch. "
                "textual_basis (when present) comes from pipeline/comparison/textual_basis.py's own scan, "
                "not every edition has one yet.",
        "editions": dict(sorted(editions.items())),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[edition-struct] {len(editions)} editions -> {OUT_PATH}")


if __name__ == "__main__":
    main()
