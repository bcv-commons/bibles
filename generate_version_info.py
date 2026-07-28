#!/usr/bin/env python3
"""Generate versions.json for each language in the export.

Scans export/ALL-langs/ for fileset directories, then enriches with
metadata from sorted cache, DBS cache, eBible catalog, helloAO catalog,
curated notes, and cross-reference data.

Output: export/versions-data/{iso}/versions.json

Version ID = DBS suffix after stripping ISO prefix (usually 3 chars).
Source availability per testament uses compact codes:
  a = audio, t = text, w = with-timecode
  Examples: "atw" = audio+text+timecode, "a" = audio only, "t" = text only
"""

import csv
import json
import tomllib
from collections import defaultdict
from pathlib import Path

EXPORT_DIR = Path("export/ALL-langs")
VERSIONS_DIR = Path("export/versions-data")
SORTED_DIR = Path("sorted/BB")
DBS_DIR = Path("api-cache/dbs/bibles")
EBIBLE_CATALOG = Path("api-cache/ebible/translations.csv")
HELLOAO_CATALOG = Path("api-cache/helloao/available_translations.json")
BIBLE_DETAILS_DIR = Path("api-cache/bibles/bible_details")
NOTES_FILE = Path("data/version-notes.toml")
CROSSREF_FILE = Path("data/version-crossref.json")


def load_dbs_index():
    """Build index: abbr -> DBS metadata."""
    index = {}
    if not DBS_DIR.is_dir():
        return index
    for f in DBS_DIR.glob("*.json"):
        try:
            d = json.load(open(f))
            if not isinstance(d, dict):
                continue
            abbr = d.get("abbr", "")
            if abbr:
                index[abbr] = d
        except Exception:
            pass
    return index


def load_notes():
    """Load curated version notes from TOML."""
    if not NOTES_FILE.exists():
        return {}
    with open(NOTES_FILE, "rb") as f:
        return tomllib.load(f)


def load_crossref():
    """Load cross-reference data."""
    if not CROSSREF_FILE.exists():
        return {}
    with open(CROSSREF_FILE) as f:
        return json.load(f)


def load_ebible_by_iso():
    """Load eBible translations grouped by ISO."""
    ebible = defaultdict(dict)  # iso -> {tid: {nt_books, ot_books}}
    if not EBIBLE_CATALOG.exists():
        return ebible
    with open(EBIBLE_CATALOG, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("Redistributable") != "True":
                continue
            iso = r["languageCode"]
            tid = r["translationId"]
            ebible[iso][tid] = {
                "nt": int(r.get("NTbooks", "0") or 0) >= 27,
                "ot": int(r.get("OTbooks", "0") or 0) >= 39,
            }
    return ebible


def load_helloao_by_iso():
    """Load helloAO translations grouped by ISO."""
    helloao = defaultdict(set)
    if not HELLOAO_CATALOG.exists():
        return helloao
    with open(HELLOAO_CATALOG) as f:
        data = json.load(f)
    for t in data.get("translations", []):
        if isinstance(t, dict):
            iso = t.get("language", "") or t.get("iso_639_3", "")
            tid = t.get("id", "")
            if iso and tid:
                helloao[iso].add(tid)
    return helloao


def load_bible_details():
    """Load direction/script from bible detail API responses. Returns {abbr: {direction, script}}."""
    details = {}
    if not BIBLE_DETAILS_DIR.is_dir():
        return details
    for f in BIBLE_DETAILS_DIR.glob("*.json"):
        try:
            d = json.load(open(f))
            if isinstance(d, dict) and "data" in d:
                d = d["data"]
            abbr = d.get("abbr", "")
            alphabet = d.get("alphabet")
            if abbr and alphabet and isinstance(alphabet, dict):
                direction = alphabet.get("direction")
                script = alphabet.get("script")
                if direction:
                    details[abbr] = {"direction": direction, "script": script or ""}
        except Exception:
            pass
    return details


def find_multi_direction_languages(bible_details):
    """Identify languages that have bibles in both LTR and RTL directions."""
    from collections import defaultdict as dd
    lang_dirs = dd(set)
    for f in BIBLE_DETAILS_DIR.glob("*.json"):
        try:
            d = json.load(open(f))
            if isinstance(d, dict) and "data" in d:
                d = d["data"]
            iso = d.get("iso", "")
            alphabet = d.get("alphabet")
            if iso and alphabet and isinstance(alphabet, dict):
                direction = alphabet.get("direction")
                if direction:
                    lang_dirs[iso].add(direction)
        except Exception:
            pass
    return {iso for iso, dirs in lang_dirs.items() if len(dirs) > 1}


def get_sorted_meta(iso, distinct_id):
    """Get bible metadata from sorted cache for a fileset."""
    iso_dir = SORTED_DIR / iso
    if not iso_dir.is_dir():
        return None
    for m in iso_dir.glob("*/metadata.json"):
        try:
            d = json.load(open(m))
            fid = d.get("fileset", {}).get("id", "")
            if fid.startswith(distinct_id):
                return d
        except Exception:
            pass
    return None


def extract_version_id(iso, distinct_id):
    """Extract short version ID by stripping ISO prefix and separator."""
    iso_upper = iso.upper()
    did_upper = distinct_id.upper()
    if did_upper.startswith(iso_upper):
        suffix = distinct_id[len(iso_upper):]
        # Strip leading separator (underscore or dash) from helloAO/eBible IDs
        if suffix and suffix[0] in ("_", "-"):
            suffix = suffix[1:]
        return suffix.upper() if suffix else distinct_id
    return distinct_id


def dbt_source_code(data_json, category):
    """Compute compact source code for DBT from data.json and category."""
    has_a = "a" in data_json and not data_json.get("a", "").startswith("contrib:")
    has_t = "t" in data_json and not data_json.get("t", "").startswith(("helloao:", "ebible:", "contrib:"))
    has_w = category in ("with-timecode", "audio-with-timecode")
    code = ""
    if has_a:
        code += "a"
    if has_t:
        code += "t"
    if has_w:
        code += "w"
    return code or None


def main():
    if not EXPORT_DIR.is_dir():
        print("[ERROR] export/ALL-langs not found. Run export-stories first.")
        return

    dbs_index = load_dbs_index()
    bible_details = load_bible_details()
    multi_dir_langs = find_multi_direction_languages(bible_details)
    notes = load_notes()
    xref = load_crossref()
    ebible_by_iso = load_ebible_by_iso()
    helloao_by_iso = load_helloao_by_iso()

    print(f"[INFO] DBS index: {len(dbs_index)} entries")
    print(f"[INFO] Version notes: {len(notes)} entries")
    print(f"[INFO] Crossref: {len(xref)} languages")

    # Collect all versions per language from export
    # Key: (iso, version_id) -> {testament -> [list of {category, data_json, distinct_id}]}
    lang_raw = defaultdict(lambda: defaultdict(list))

    for testament_dir in sorted(EXPORT_DIR.iterdir()):
        if not testament_dir.is_dir():
            continue
        testament = testament_dir.name
        for cat_dir in sorted(testament_dir.iterdir()):
            if not cat_dir.is_dir():
                continue
            category = cat_dir.name
            for iso_dir in sorted(cat_dir.iterdir()):
                if not iso_dir.is_dir():
                    continue
                iso = iso_dir.name
                for did_dir in sorted(iso_dir.iterdir()):
                    if not did_dir.is_dir() or not (did_dir / "data.json").exists():
                        continue
                    distinct_id = did_dir.name
                    with open(did_dir / "data.json") as f:
                        data_json = json.load(f)

                    vid = extract_version_id(iso, distinct_id)
                    lang_raw[(iso, vid)][testament].append({
                        "category": category,
                        "data": data_json,
                        "distinct_id": distinct_id,
                    })

    # Build versions.json per language
    lang_versions = defaultdict(dict)

    for (iso, vid), testaments in lang_raw.items():
        entry = {}
        distinct_id = None

        # Get metadata from DBS — use first distinct_id found
        for t_infos in testaments.values():
            for t_info in t_infos:
                distinct_id = t_info["distinct_id"]
                break
            if distinct_id:
                break

        full_id = f"{iso.upper()}{vid}" if distinct_id else vid
        dbs = dbs_index.get(full_id)
        if dbs:
            if dbs.get("title"):
                entry["title"] = dbs["title"]
            if dbs.get("title_vernacular"):
                entry["title_v"] = dbs["title_vernacular"]
            if dbs.get("year"):
                entry["year"] = dbs["year"]
            desc = dbs.get("description") or dbs.get("description_vernacular") or ""
            if desc:
                entry["desc"] = desc[:300].rstrip()
            desc_v = dbs.get("description_vernacular") or ""
            if desc_v and desc_v != desc:
                entry["desc_v"] = desc_v[:300].rstrip()
            if dbs.get("copyright_type"):
                entry["license"] = dbs["copyright_type"]

        # Fill gaps from sorted cache
        if distinct_id:
            sorted_meta = get_sorted_meta(iso, distinct_id)
            if sorted_meta:
                bible = sorted_meta.get("bible", {})
                if "title" not in entry and bible.get("name"):
                    entry["title"] = bible["name"]
                if "title_v" not in entry and bible.get("vname"):
                    entry["title_v"] = bible["vname"]
                if bible.get("mark") and "license" not in entry:
                    mark = bible["mark"]
                    if "public domain" in mark.lower():
                        entry["license"] = "OPEN"

        # For multi-direction languages, tag RTL versions
        if iso in multi_dir_langs:
            detail = bible_details.get(full_id)
            if detail and detail.get("direction") == "rtl":
                entry["d"] = "rtl"
                if detail.get("script"):
                    entry["s"] = detail["script"]

        # Add curated notes
        version_notes = notes.get(full_id, {})
        if version_notes.get("note"):
            entry["note"] = version_notes["note"]
        if version_notes.get("same_text_as"):
            same = version_notes["same_text_as"]
            if same.upper().startswith(iso.upper()):
                same = same[len(iso):]
            entry["same_text"] = same

        # Build nt/ot source objects
        xref_versions = xref.get(iso, {})
        xref_entry = xref_versions.get(vid, {})

        for testament in ("nt", "ot"):
            t_infos = testaments.get(testament, [])
            sources = {}

            # Merge all entries for this testament (multiple distinct_ids)
            for t_info in t_infos:
                dbt_code = dbt_source_code(t_info["data"], t_info["category"])
                if dbt_code:
                    # Merge: combine codes (e.g., "a" + "t" = "at")
                    existing = sources.get("dbt", "")
                    merged = existing
                    for c in dbt_code:
                        if c not in merged:
                            merged += c
                    # Sort to canonical order: a, t, w
                    sources["dbt"] = "".join(c for c in "atw" if c in merged)

                # Check for helloAO in data.json (t_alt or t field)
                data = t_info["data"]
                t_val = data.get("t", "")
                t_alt = data.get("t_alt", "")
                if "helloao:" in t_val or "helloao:" in t_alt:
                    sources["helloao"] = "t"
                if "ebible:" in t_val:
                    sources["ebible"] = "t"
                if "contrib:" in t_val or "contrib:" in data.get("a", ""):
                    contrib = sources.get("contrib", "")
                    if "contrib:" in data.get("a", "") and "a" not in contrib:
                        contrib += "a"
                    if "contrib:" in t_val and "t" not in contrib:
                        contrib += "t"
                    sources["contrib"] = contrib

            # Enrich from crossref: check if eBible/helloAO available for this version
            if xref_entry.get("ebible") and "ebible" not in sources:
                # Check if eBible has this testament
                eb_id = xref_entry["ebible"]
                eb_data = ebible_by_iso.get(iso, {}).get(eb_id, {})
                if eb_data.get(testament, False):
                    sources["ebible"] = "t"
                elif not eb_data:
                    # Crossref says it exists but no detail — assume NT at least
                    if testament == "nt":
                        sources["ebible"] = "t"

            if xref_entry.get("helloao") and "helloao" not in sources:
                sources["helloao"] = "t"

            if sources:
                entry[testament] = sources

        if entry:
            lang_versions[iso][vid] = entry

    # Clean up old output
    import shutil
    if VERSIONS_DIR.exists():
        shutil.rmtree(VERSIONS_DIR)

    # Write one versions.json per language
    files_written = 0
    for iso in sorted(lang_versions):
        versions = lang_versions[iso]
        if not versions:
            continue
        out_dir = VERSIONS_DIR / iso
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "versions.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(versions, f, indent=2, ensure_ascii=False, sort_keys=True)
        files_written += 1

    total_versions = sum(len(v) for v in lang_versions.values())
    print(f"[INFO] Written {files_written} versions.json files ({total_versions} versions)")


if __name__ == "__main__":
    main()
