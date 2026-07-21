#!/usr/bin/env python3
"""Merge all three comparison legs (PKF-vs-DBT, helloAO-vs-DBT, PKF-vs-
helloAO) into the unified publish artifact: one row per (iso, canon, source)
that actually has content, self-contained (no cross-row joins needed), never
collapsing duplicates away — every source that exists gets a row, even when
it's a perfect duplicate of another.

Row shape:
    [iso, canon, source, version_id, comparisons?, source_ref?]
  comparisons = [[ref, likely, score], ...]  (one entry per OTHER source this
    row was actually compared against; ref is "dbt:<id>", "pkf:<id>", or
    "helloao:<id>")

version_id resolution (per the stated client priority pkf > helloao > dbt):
  - dbt rows: always their own native distinct_id (DBT never borrows an id).
  - pkf rows: DBT's id if PKF is identical (score==1.0) to some DBT native
    version; otherwise a minted "<ISO>PKF" id.
  - helloao rows: DBT's id if identical to a DBT native version (checked
    first, since DBT already has a stable id); else PKF's resolved id if
    identical to PKF (score==1.0); else its own native helloAO id (the
    string a client would actually use against helloAO's API).
  This never hides a row — it only picks which id is displayed for it. The
  comparisons list carries the actual verified evidence regardless of which
  id was chosen for display.

"likely" values:
  - PKF-vs-DBT comparisons use the full taxonomy from diagnose_pkf_dbt_diff.py
    (orthography/phonemic/dialect_variant/source_duplication/distinct/
    identical) where available.
  - All other comparisons (helloAO-vs-DBT, PKF-vs-helloAO) use the coarser
    4-tier score bucket (identical/near_identical/uncertain/distinct) — the
    deeper taxonomy hasn't been run for those legs yet, and this script
    doesn't guess at categories it hasn't verified.

Usage:
    python3 scripts/generate_catalog_overlap.py [--out PATH]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, COMPARISON_RESULTS_DIR, EXPORT  # noqa: E402


def load(path, default=None):
    p = COMPARISON_RESULTS_DIR / path
    return json.loads(p.read_text()) if p.exists() else (default if default is not None else {})


def tier(score):
    if score is None:
        return None
    if score == 1.0:
        return "identical"
    if score >= 0.98:
        return "near_identical"
    if score >= 0.5:
        return "uncertain"
    return "distinct"


def merge_helloao_dbt():
    """(iso, canon, helloao_id) -> {"scores": {dbt_id: score}}"""
    out = {}
    for row in load("helloao-dbt-phase1.json").values():
        if row.get("status") != "compared":
            continue
        out[(row["iso"], row["canon"], row["helloao_id"])] = row["all_scores"]
    for row in load("helloao-dbt-phase2.json").values():
        if row.get("status") != "compared":
            continue
        out[(row["iso"], row["canon"], row["helloao_id"])] = row["all_scores"]
    for row in load("helloao-dbt-phase3.json", []):
        if row.get("best_score") is None:
            continue
        out[(row["iso"], row["canon"], row["helloao_id"])] = row["scores"]
    return out


def main():
    args = sys.argv[1:]
    out_path = Path(args[args.index("--out") + 1]) if "--out" in args else EXPORT / "dbt" / "_app" / "catalog-overlap.json"

    catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())
    dbt_native_by_iso_canon = {}
    for row in catalog["versions"]:
        iso, distinct_id, canon = row[0], row[1], row[2]
        canon_plain = canon.rstrip("p")
        if any(f.startswith(("t:helloao:", "t:ebible:")) for f in row[3:]):
            continue
        if not any(f.split(":", 1)[0] in ("t", "T") for f in row[3:]):
            continue
        dbt_native_by_iso_canon.setdefault((iso, canon_plain), set()).add(distinct_id)

    pkf_manifest = json.loads((API_CACHE / "pkf-manifest.json").read_text())["languages"]

    pkf_dbt_nt = load("pkf-dbt-comparison.json")
    pkf_dbt_ot = load("pkf-dbt-comparison-ot.json")
    pkf_dbt_ot_psa51 = load("pkf-dbt-comparison-ot-psa51.json")
    diag_nt = load("pkf-dbt-comparison-diagnosis.json")
    diag_ot = load("pkf-dbt-comparison-ot-diagnosis.json")

    pkf_hao_nt = load("pkf-helloao-comparison.json")
    pkf_hao_ot = load("pkf-helloao-comparison-ot.json")

    hao_dbt = merge_helloao_dbt()

    def pkf_likely(iso, canon, score):
        if score == 1.0:
            return "identical"
        d = diag_nt if canon == "nt" else diag_ot
        entry = d.get(iso)
        if entry and entry.get("category"):
            return entry["category"].replace("likely_", "")
        return tier(score)

    def pkf_dbt_entry(iso, canon):
        if canon == "nt":
            return pkf_dbt_nt.get(iso)
        # OT: use the PSA51 escalation result when available (more reliable
        # probe), otherwise the PSA117 pass.
        base = dict(pkf_dbt_ot.get(iso) or {})
        if iso in pkf_dbt_ot_psa51:
            base.update(pkf_dbt_ot_psa51[iso])
            base["_escalated"] = True
        return base or None

    def pkf_hao_entry(iso, canon):
        d = pkf_hao_nt if canon == "nt" else pkf_hao_ot
        return d.get(iso)

    entries = []
    all_isos = set(pkf_manifest.keys()) | {k[0] for k in dbt_native_by_iso_canon} | {k[0] for k in hao_dbt}
    helloao_translations = json.loads((API_CACHE / "helloao" / "available_translations.json").read_text())["translations"]
    helloao_by_iso = {}
    for e in helloao_translations:
        helloao_by_iso.setdefault(e["language"], []).append(e["id"])
    all_isos |= set(helloao_by_iso.keys())

    for iso in sorted(all_isos):
        for canon in ("nt", "ot"):
            dbt_ids = sorted(dbt_native_by_iso_canon.get((iso, canon), []))
            for did in dbt_ids:
                entries.append([iso, canon, "dbt", did])

            pkf_version_id = None
            pd = pkf_dbt_entry(iso, canon)
            ph = pkf_hao_entry(iso, canon)
            has_pkf_collection = bool(pkf_manifest.get(iso, {}).get("collections"))

            pkf_comparisons = []
            if pd and pd.get("status") == "compared":
                best_score = pd["best_score"]
                if best_score == 1.0:
                    pkf_version_id = pd["best_match"]
                for did2, s in pd.get("all_scores", {}).items():
                    pkf_comparisons.append([f"dbt:{did2}", pkf_likely(iso, canon, s), s])
            if ph and ph.get("status") == "compared":
                for hid, s in ph.get("all_scores", {}).items():
                    if s is not None:
                        pkf_comparisons.append([f"helloao:{hid}", tier(s), s])

            if pkf_version_id is None and (pkf_comparisons or (has_pkf_collection and (canon == "nt" or
                    (pkf_manifest.get(iso, {}).get("collections") and any((c.get("coverage") or {}).get("o") for c in pkf_manifest[iso]["collections"]))))):
                pkf_version_id = f"{iso.upper()}PKF"

            if pkf_version_id:
                pkf_source_ref = (pd or {}).get("pkf_file") or (ph or {}).get("pkf_file")
                row = [iso, canon, "pkf", pkf_version_id]
                if pkf_comparisons:
                    row.append(pkf_comparisons)
                else:
                    row.append([])
                if pkf_source_ref:
                    row.append(pkf_source_ref.rsplit(".", 2)[0] if pkf_source_ref.count(".") >= 2 else pkf_source_ref)
                entries.append(row)

            for hid in helloao_by_iso.get(iso, []):
                hao_scores = hao_dbt.get((iso, canon, hid))
                pkf_score_for_this_hid = None
                if ph and ph.get("status") == "compared":
                    pkf_score_for_this_hid = ph.get("all_scores", {}).get(hid)

                if hao_scores is None and pkf_score_for_this_hid is None:
                    continue  # no data at all for this helloAO id in this canon

                hao_comparisons = []
                hao_version_id = None
                if hao_scores:
                    for did2, s in hao_scores.items():
                        if s is not None:
                            hao_comparisons.append([f"dbt:{did2}", tier(s), s])
                            if s == 1.0 and hao_version_id is None:
                                hao_version_id = did2
                if pkf_score_for_this_hid is not None:
                    hao_comparisons.append([f"pkf:{pkf_version_id}", tier(pkf_score_for_this_hid), pkf_score_for_this_hid])
                    if pkf_score_for_this_hid == 1.0 and hao_version_id is None:
                        hao_version_id = pkf_version_id

                if hao_version_id is None:
                    hao_version_id = hid  # its own native helloAO id

                row = [iso, canon, "helloao", hao_version_id]
                row.append(hao_comparisons)
                # Always record the real, queryable helloAO id as source_ref
                # when the display version_id was borrowed from DBT/PKF
                # (identical case) — otherwise a client has the right
                # display id but no way to actually fetch the content from
                # helloAO's own API. Found via cak: cak_smj/cak_swy/cak_wes
                # all resolve their version_id to a borrowed DBT id, and
                # without this field their real helloAO id would be lost.
                if hao_version_id != hid:
                    row.append(hid)
                entries.append(row)

    defaults = {}
    for row in entries:
        iso, canon, source = row[0], row[1], row[2]
        key = f"{iso}:{canon}"
        rank = {"pkf": 0, "helloao": 1, "dbt": 2}[source]
        if key not in defaults or rank < defaults[key][1]:
            defaults[key] = (source, rank)
    defaults = {k: v[0] for k, v in defaults.items()}

    output = {
        "generated_at": None,  # stamped at publish time, not by this generator
        "probes": {"nt": ["REV15"], "ot": ["PSA117", "PSA51"]},
        "priority": ["pkf", "helloao", "dbt"],
        "audio_source": "dbt",
        "defaults": defaults,
        "entries": entries,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"[generate-catalog-overlap] {len(entries)} entries across {len(defaults)} (iso,canon) pairs -> {out_path}")


if __name__ == "__main__":
    main()
