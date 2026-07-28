#!/usr/bin/env python3
"""Generate version cross-reference file.

Scans DBS cache, DBT sorted cache, eBible catalog, and helloAO catalog
to build a minimal routing table for Bible versions across sources.

Output: data/version-crossref.json

Standard conventions (implicit, not stored):
  DBT:     {ISO}{ID}       e.g., ENGKJV, SOMB13
  eBible:  {iso}-{id}      e.g., eng-kjv (dash separator, lowercase)
  helloAO: {iso}_{id}      e.g., eng_kjv (underscore separator, lowercase)

Only deviations from these conventions are stored.
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

DBS_DIR = Path("api-cache/dbs/bibles")
SORTED_DIR = Path("sorted")
EBIBLE_CATALOG = Path("api-cache/ebible/translations.csv")
HELLOAO_CATALOG = Path("api-cache/helloao/available_translations.json")
NOTES_FILE = Path("data/version-notes.toml")
OUTPUT = Path("data/version-crossref.json")
UNMATCHED_OUTPUT = Path("data/version-crossref-unmatched.json")


def load_dbt_ids():
    """Load all DBT distinct_ids grouped by ISO."""
    dbt = defaultdict(set)
    if not SORTED_DIR.is_dir():
        return dbt

    # Suffixes to strip, ordered longest first to avoid partial matches
    SUFFIXES = sorted([
        "N1DA16", "N2DA16", "O1DA16", "O2DA16",
        "-opus16",
        "N1DA", "N2DA", "O1DA", "O2DA",
        "N1SA", "N2SA", "O1SA", "O2SA",
        "P1DA", "P2DA", "S1DA", "S2DA",
        "N_ET", "O_ET", "_ET",
        "-json", "-usx",
    ], key=len, reverse=True)

    for iso_dir in SORTED_DIR.glob("BB/*"):
        if not iso_dir.is_dir():
            continue
        iso = iso_dir.name
        for m in iso_dir.glob("*/metadata.json"):
            try:
                d = json.load(open(m))
                fid = d["fileset"]["id"]
                base = fid
                # Strip suffixes repeatedly (handles compound like -opus16)
                changed = True
                while changed:
                    changed = False
                    for s in SUFFIXES:
                        if base.endswith(s):
                            base = base[:-len(s)]
                            changed = True
                            break
                if base:
                    dbt[iso].add(base)
            except Exception:
                pass
    return dbt


def load_ebible_ids():
    """Load eBible translation IDs grouped by ISO."""
    ebible = defaultdict(list)
    if not EBIBLE_CATALOG.exists():
        return ebible
    with open(EBIBLE_CATALOG, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            iso = r["languageCode"]
            tid = r["translationId"]
            ebible[iso].append(tid)
    return ebible


def load_helloao_ids():
    """Load helloAO translation IDs grouped by ISO."""
    helloao = defaultdict(list)
    if not HELLOAO_CATALOG.exists():
        return helloao
    with open(HELLOAO_CATALOG) as f:
        data = json.load(f)
    for t in data.get("translations", []):
        if isinstance(t, dict):
            iso = t.get("language", "") or t.get("iso_639_3", "")
            tid = t.get("id", "")
            if iso and tid:
                helloao[iso].append(tid)
    return helloao


def load_notes():
    """Load curated version notes."""
    if not NOTES_FILE.exists():
        return {}
    import tomllib
    with open(NOTES_FILE, "rb") as f:
        return tomllib.load(f)


def extract_version_id(iso, abbr):
    """Extract version ID by stripping ISO prefix from DBS abbr."""
    iso_upper = iso.upper()
    if abbr.upper().startswith(iso_upper):
        return abbr[len(iso_upper):]
    return abbr


def ebible_standard(iso, version_id):
    """Return the standard eBible ID: {iso}-{id_lower}."""
    return f"{iso}-{version_id.lower()}"


def helloao_standard(iso, version_id):
    """Return the standard helloAO ID: {iso}_{id_lower} (lowercase, underscore)."""
    return f"{iso}_{version_id.lower()}"


def dbt_standard(iso, version_id):
    """Return the standard DBT distinct_id: {ISO}{ID}."""
    return f"{iso.upper()}{version_id.upper()}"


def main():
    print("[INFO] Loading sources...")
    dbt_ids = load_dbt_ids()
    ebible_ids = load_ebible_ids()
    helloao_ids = load_helloao_ids()
    notes = load_notes()

    print(f"  DBT: {sum(len(v) for v in dbt_ids.values())} distinct_ids across {len(dbt_ids)} languages")
    print(f"  eBible: {sum(len(v) for v in ebible_ids.values())} translations across {len(ebible_ids)} languages")
    print(f"  helloAO: {sum(len(v) for v in helloao_ids.values())} translations across {len(helloao_ids)} languages")

    # Build crossref from DBS as the hub
    crossref = {}
    unmatched = {"ebible": [], "helloao": [], "dbt": []}

    print("[INFO] Scanning DBS catalog...")
    dbs_count = 0
    if DBS_DIR.is_dir():
        for f in sorted(DBS_DIR.glob("*.json")):
            try:
                d = json.load(open(f))
                if not isinstance(d, dict):
                    continue
                iso = d.get("iso", "")
                abbr = d.get("abbr", "")
                if not iso or not abbr:
                    continue

                version_id = extract_version_id(iso, abbr)
                if not version_id:
                    continue

                dbs_count += 1
                entry = {}

                # Check DBT
                dbt_expected = dbt_standard(iso, version_id)
                has_dbt = dbt_expected in dbt_ids.get(iso, set())
                if not has_dbt:
                    # Try matching via DBS equivalents
                    for eq in d.get("bible_equivalents", []):
                        site = eq.get("site", "") or eq.get("type", "")
                        eid = eq.get("equivalent_id", "")
                        if ("bible.is" in site or site == "api") and eid:
                            # Check if this equivalent matches any DBT id
                            for did in dbt_ids.get(iso, set()):
                                if eid.startswith(did) or did == eid:
                                    has_dbt = True
                                    if did != dbt_expected:
                                        entry["dbt"] = did
                                    break
                        if has_dbt:
                            break
                    if not has_dbt:
                        entry["dbt"] = False

                # Check eBible
                eb_expected = ebible_standard(iso, version_id)
                eb_tids = ebible_ids.get(iso, [])
                eb_match = None
                if eb_expected in eb_tids:
                    eb_match = eb_expected  # standard pattern matches
                else:
                    # Try via DBS equivalents
                    for eq in d.get("bible_equivalents", []):
                        if "ebible" in (eq.get("site", "") or "").lower():
                            eid = eq.get("equivalent_id", "")
                            if eid in eb_tids:
                                eb_match = eid
                            break
                    # Try without dash: {iso}{id_lower}
                    if not eb_match:
                        no_dash = f"{iso}{version_id.lower()}"
                        if no_dash in eb_tids:
                            eb_match = no_dash
                    # Try bare ISO (eBible uses just the ISO as tid)
                    if not eb_match and iso in eb_tids:
                        eb_match = iso
                    # Try {iso}NT or {iso}NTpo patterns
                    if not eb_match:
                        for suffix in ["NT", "NTpo", "NT2", "2009", "2010"]:
                            variant = f"{iso}{suffix}"
                            if variant in eb_tids:
                                eb_match = variant
                                break

                if eb_match:
                    if eb_match != eb_expected:
                        entry["ebible"] = eb_match  # nonstandard ID
                    # else: standard, don't store
                # Don't store ebible: false (too many would have it)

                # Check helloAO
                hao_expected = helloao_standard(iso, version_id)
                hao_tids = helloao_ids.get(iso, [])
                hao_match = None
                if hao_expected in hao_tids:
                    hao_match = hao_expected
                else:
                    # Try uppercase no-separator: {ISO}{ID}
                    hao_upper = f"{iso.upper()}{version_id.upper()}"
                    if hao_upper in hao_tids:
                        hao_match = hao_upper
                    else:
                        # Try case-insensitive match
                        for tid in hao_tids:
                            tid_norm = tid.lower().replace("_", "").replace("-", "")
                            expected_norm = f"{iso}{version_id}".lower()
                            if tid_norm == expected_norm:
                                hao_match = tid
                                break
                    # Try bare ISO: {iso}_wbt, {iso}_tbl etc (common helloAO patterns)
                    if not hao_match:
                        for tid in hao_tids:
                            # Match if the version_id part matches after stripping iso prefix
                            tid_lower = tid.lower()
                            if tid_lower.startswith(f"{iso}_"):
                                hao_vid = tid_lower[len(iso)+1:].upper()
                                if hao_vid == version_id.upper():
                                    hao_match = tid
                                    break

                if hao_match:
                    if hao_match != hao_expected:
                        entry["helloao"] = hao_match

                # Add curated notes
                full_id = f"{iso.upper()}{version_id}"
                version_notes = notes.get(full_id, {})
                if version_notes.get("same_text_as"):
                    same = version_notes["same_text_as"]
                    # Strip ISO prefix if present
                    if same.upper().startswith(iso.upper()):
                        same = same[len(iso):]
                    entry["same_text"] = same
                if version_notes.get("note"):
                    entry["note"] = version_notes["note"]

                # Add to crossref
                if iso not in crossref:
                    crossref[iso] = {}
                crossref[iso][version_id] = entry

            except Exception:
                pass

    print(f"  DBS versions processed: {dbs_count}")

    # Find unmatched resources in other sources
    # eBible IDs not matched to any DBS entry
    all_matched_ebible = set()
    for iso, versions in crossref.items():
        for vid, entry in versions.items():
            eb = entry.get("ebible")
            if eb:
                all_matched_ebible.add(eb)
            elif eb is None:
                # Standard pattern was matched
                all_matched_ebible.add(ebible_standard(iso, vid))

    for iso, tids in ebible_ids.items():
        for tid in tids:
            if tid not in all_matched_ebible:
                unmatched["ebible"].append({"iso": iso, "id": tid})

    # helloAO IDs not matched
    all_matched_helloao = set()
    for iso, versions in crossref.items():
        for vid, entry in versions.items():
            hao = entry.get("helloao")
            if hao:
                all_matched_helloao.add(hao)
            elif hao is None:
                all_matched_helloao.add(helloao_standard(iso, vid))

    for iso, tids in helloao_ids.items():
        for tid in tids:
            if tid not in all_matched_helloao:
                unmatched["helloao"].append({"iso": iso, "id": tid})

    # DBT IDs not matched
    all_matched_dbt = set()
    for iso, versions in crossref.items():
        for vid, entry in versions.items():
            dbt_val = entry.get("dbt")
            if dbt_val and dbt_val is not False:
                all_matched_dbt.add(dbt_val)
            elif dbt_val is None:
                all_matched_dbt.add(dbt_standard(iso, vid))

    for iso, ids in dbt_ids.items():
        for did in ids:
            if did not in all_matched_dbt:
                unmatched["dbt"].append({"iso": iso, "id": did})

    # Write outputs
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(crossref, f, indent=2, ensure_ascii=False, sort_keys=True)

    with open(UNMATCHED_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(unmatched, f, indent=2, ensure_ascii=False, sort_keys=True)

    total_versions = sum(len(v) for v in crossref.values())
    print(f"\n[INFO] Written {OUTPUT}: {len(crossref)} languages, {total_versions} versions")
    print(f"[INFO] Written {UNMATCHED_OUTPUT}:")
    print(f"  Unmatched eBible: {len(unmatched['ebible'])}")
    print(f"  Unmatched helloAO: {len(unmatched['helloao'])}")
    print(f"  Unmatched DBT: {len(unmatched['dbt'])}")


if __name__ == "__main__":
    main()
