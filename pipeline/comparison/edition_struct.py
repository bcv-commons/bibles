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
it with textual_basis.py's, psalm_titles.py's and edition_script.py's own output (pipeline/comparison/) where
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
import edition_script  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, CATALOG_DIR, COMPARISON_RESULTS_DIR, EXPORT  # noqa: E402

# All editions in one file: internal only (1.3 MB). What we publish is one file per language,
# catalog/<iso[0]>/<iso>/edition-struct.json (2026-10-26: clients work with one to a few languages).
OUT_PATH = COMPARISON_RESULTS_DIR / "edition-struct.json"
BIBLE_DETAILS_DIR = API_CACHE / "bibles" / "bible_details"
OPENBIBLE_TEXT_CACHE = API_CACHE / "openbible" / "text"
# Internal build artifact, not published on its own — see its own module
# docstring in textual_basis.py for why. We just fold its verdict in here.
TEXTUAL_BASIS_FILE = COMPARISON_RESULTS_DIR / "textual-basis.json"
# Same for psalm_titles.py: how the edition presents psalm titles (for lexeme-aligner).
PSALM_TITLES_FILE = COMPARISON_RESULTS_DIR / "psalm-titles.json"
# And edition_script.py: letters per script and normalization, read from each edition's text.
EDITION_SCRIPT_FILE = COMPARISON_RESULTS_DIR / "edition-script.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def dbt_record(distinct_id: str, iso: str) -> dict:
    detail = _load_json(BIBLE_DETAILS_DIR / f"{distinct_id}.json").get("data", {})
    return {
        "iso": iso, "provider": "DBT (4.dbt.io)",
        "name": detail.get("name"), "license": detail.get("mark"),
    }


def helloao_record(translation_id: str, iso: str, helloao_translations: dict) -> dict:
    e = helloao_translations.get(translation_id, {})
    return {
        "iso": iso, "provider": "helloAO",
        "name": e.get("name"), "license": e.get("licenseUrl"),
    }


def pkf_record(iso: str, pkf_manifest: dict) -> dict:
    entry = pkf_manifest.get(iso) or {}
    return {"iso": iso, "provider": "PKF", "name": entry.get("nm"), "license": None}


def openbible_record(project_id: str, abbr: str, iso: str, edition: dict) -> dict:
    """`edition` is the project's openbible-editions.json entry: an edition we don't publish
    carries `published: false` and the reason (nd_license, no_source, not_built)."""
    detail = _load_json(OPENBIBLE_TEXT_CACHE / f"{project_id}.json").get("project", {})
    record = {
        "iso": iso, "provider": "openbible (Biblica)",
        "name": detail.get("title"), "license": detail.get("rightsHolder"),
        "biblica_project": project_id,
    }
    if edition.get("published") is False:
        record["published"] = False
        record["reason"] = edition.get("reason")
    return record


def own_record(path: str, iso: str) -> dict:
    """An edition we republish (eBible, CrossWire, Door43; openbible and audiobiblia come from
    their project caches above), from its _meta.json."""
    kind, _, edition = path.strip("/").split("/")
    meta = _load_json(EXPORT / edition_script.OWN_USJ[kind] / iso / edition / "_meta.json")
    lic = meta.get("licenses") or [{}]
    return {"iso": iso, "provider": meta.get("provider"), "name": meta.get("name"), "license": lic[0].get("type")}


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
    psalm_titles = _load_json(PSALM_TITLES_FILE).get("editions", {})
    measured = _load_json(EDITION_SCRIPT_FILE)
    stated = edition_script.stated_metadata()

    editions: dict[str, dict] = {}

    def add(edition_id: str, record: dict, scan_key: str) -> None:
        tb = textual_basis.get(scan_key)
        if tb:
            record["textual_basis"] = tb["verdict"]
        pt = psalm_titles.get(scan_key)
        if pt:
            record["psalm_titles"] = pt["psalm_titles"]
            record["psalm_titles_basis"] = pt["basis"]
        record.update(edition_script.verdict(measured.get(edition_id), *stated.get(edition_id, (None, None))))
        editions[edition_id] = record

    for canon in ("nt", "ot"):
        # Our own editions (eBible, CrossWire, Door43) are added from text-route.json below.
        candidates = all_candidates(catalog, helloao_by_iso, pkf_manifest, openbible_by_iso, openbible_abbr, canon, {})
        for iso, (dbt_ids, hao_ids, pkf_files, ob_ids, _) in candidates.items():
            for distinct_id in dbt_ids:
                add(f"d:{distinct_id}", dbt_record(distinct_id, iso), f"{iso}:dbt:{distinct_id}")
            for hid in hao_ids:
                add(f"h:{hid}", helloao_record(hid, iso, helloao_translations), f"{iso}:helloao:{hid}")
            if pkf_files:
                add(f"p:{iso.upper()}PKF", pkf_record(iso, pkf_manifest), f"{iso}:pkf:{iso.upper()}PKF")
            for project_id, abbr in ob_ids:
                add(f"o:{abbr}", openbible_record(project_id, abbr, iso, openbible_abbr.get(project_id, {})),
                    f"{iso}:openbible:{abbr}")
    # Editions only text-route.json lists: the ones we republish from eBible, CrossWire and Door43
    # (and audiobiblia's two), and DBT versions that only text-route.json found (e.g.
    # not_in_fileset_listing), which all_candidates() doesn't return.
    for edition_id, (iso, route) in edition_script.editions().items():
        if edition_id in editions:
            continue
        src, eid = edition_id.split(":", 1)
        if route.get("path"):
            name = {"e": "ebible", "c": "crosswire", "g": "door43", "o": "openbible"}[src]
            add(edition_id, own_record(route["path"], iso), f"{iso}:{name}:{eid}")
        elif src == "d":
            add(edition_id, dbt_record(eid, iso), f"{iso}:dbt:{eid}")
        elif src == "h":
            add(edition_id, helloao_record(eid, iso, helloao_translations), f"{iso}:helloao:{eid}")

    retired = CATALOG_DIR / "edition-struct.json"  # published there until 2026-10-26
    if retired.exists():
        retired.unlink()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "note": "iso/name/license merged from our own cached source catalogs (DBT bible_details, "
                "helloAO available_translations, PKF manifest, openbible project cache, our editions' "
                "_meta.json) — no live fetch. script, scripts, direction, spaces, normalization and basis "
                "come from edition_script.py, read from each edition's text (doc/catalog-edition-struct.md). "
                "textual_basis (when present) comes from pipeline/comparison/textual_basis.py's own scan, "
                "not every edition has one yet. psalm_titles (when present) comes from psalm_titles.py: "
                "numbered (the title is counted as a verse), mixed (numbered in one probe psalm, not the other), heading (a title marker before verse 1, "
                "not counted), note (the title is only a footnote), unmarked (no marker: inline in verse 1 "
                "or left out). psalm_titles_basis is 'markup' or 'verse-count' (DBT plain text has no "
                "heading markup, so it can only show numbered or unmarked).",
        "editions": dict(sorted(editions.items())),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[edition-struct] {len(editions)} editions -> {OUT_PATH}")

    # The same records per language, for clients that work with one or a few languages:
    # catalog/<iso[0]>/<iso>/edition-struct.json, next to that language's books.json.
    by_iso: dict[str, dict] = defaultdict(dict)
    for edition_id, record in sorted(editions.items()):
        by_iso[record["iso"]][edition_id] = {k: v for k, v in record.items() if k != "iso"}
    for iso, eds in by_iso.items():
        f = CATALOG_DIR / iso[0] / iso / "edition-struct.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"iso": iso, "editions": eds}, ensure_ascii=False, separators=(",", ":")) + "\n",
                     encoding="utf-8")
    print(f"[edition-struct] {len(by_iso)} languages -> {CATALOG_DIR}/<iso[0]>/<iso>/edition-struct.json")


if __name__ == "__main__":
    main()
