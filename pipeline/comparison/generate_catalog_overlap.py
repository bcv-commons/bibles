#!/usr/bin/env python3
"""Merge all three comparison legs (PKF-vs-DBT, helloAO-vs-DBT, PKF-vs-
helloAO) into the unified publish artifact — cluster form. Replaces the
earlier per-source-row design (which forced a client to manually dedupe a
"wall" of raw comparison scores — e.g. spa/nt had 15 rows and ~50 individual
score tuples for one language) with one row per GENUINELY DISTINCT option:
identical items (score==1.0, verified by real text comparison, never
guessed) are grouped into one cluster; everything else stays its own
cluster, carrying a single "closest relative" + taxonomy category instead
of a full comparison matrix.

Row shape:
    [iso, canon, cluster]
  cluster = {
    "ids": ["dbt:<id>", "helloao:<id>", "pkf:<id>", ...],
    "default": "source:id",   # only when len(ids) > 1 — which member to
                               # prefer, strictly pkf > helloao > dbt (never
                               # a separate "which id looks nicer" choice)
    "likely": "...",          # only for non-identical singletons
    "closest": "source:id",   # the single most-informative reference (the
                               # relationship in this cluster's own data
                               # with the HIGHEST score, not just DBT)
    "score": 0.0,
  }
Every id is always source-prefixed ("dbt:X", never bare "X") — verified
there's currently no id collision across DBT/PKF-minted/helloAO id spaces,
but nothing structurally guarantees that stays true forever, so this
script never relies on a bare id being unambiguous.

Clustering: union-find over every score==1.0 relationship found across all
three legs — PKF-vs-DBT, helloAO-vs-DBT (best-match only, one edge per
helloAO id), PKF-vs-helloAO (best-match only). A cluster's "default" is
the highest-priority source PRESENT in that specific cluster, not assumed.

"likely" values: the full taxonomy from diagnose_pkf_dbt_diff.py /
diagnose_helloao_dbt_diff.py / diagnose_pkf_helloao_diff.py where a
diagnosis was run (single best-match only, per language/pair — see those
scripts); falls back to the coarser 4-tier score bucket
(near_identical/uncertain/distinct) for any relationship a diagnosis
pass hasn't covered.

Usage:
    python3 generate_catalog_overlap.py [--out PATH]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, COMPARISON_RESULTS_DIR, EXPORT  # noqa: E402

PRIORITY = {"pkf": 0, "helloao": 1, "dbt": 2}


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


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


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
    helloao_translations = json.loads((API_CACHE / "helloao" / "available_translations.json").read_text())["translations"]
    helloao_by_iso = {}
    for e in helloao_translations:
        helloao_by_iso.setdefault(e["language"], []).append(e["id"])

    pkf_dbt_nt = load("pkf-dbt-comparison.json")
    pkf_dbt_ot = load("pkf-dbt-comparison-ot.json")
    pkf_dbt_ot_psa51 = load("pkf-dbt-comparison-ot-psa51.json")
    diag_pkf_dbt_nt = load("pkf-dbt-comparison-diagnosis.json")
    diag_pkf_dbt_ot = load("pkf-dbt-comparison-ot-diagnosis.json")

    pkf_hao_nt = load("pkf-helloao-comparison.json")
    pkf_hao_ot = load("pkf-helloao-comparison-ot.json")
    diag_pkf_hao = load("pkf-helloao-diagnosis.json")  # keyed "iso:canon"

    hao_dbt = merge_helloao_dbt()
    diag_hao_dbt = load("helloao-dbt-diagnosis.json")  # keyed "iso:canon:helloao_id"

    def pkf_dbt_entry(iso, canon):
        if canon == "nt":
            return pkf_dbt_nt.get(iso)
        base = dict(pkf_dbt_ot.get(iso) or {})
        if iso in pkf_dbt_ot_psa51:
            base.update(pkf_dbt_ot_psa51[iso])
        return base or None

    def pkf_hao_entry(iso, canon):
        d = pkf_hao_nt if canon == "nt" else pkf_hao_ot
        return d.get(iso)

    def pkf_dbt_likely(iso, canon, score):
        if score == 1.0:
            return "identical"
        d = diag_pkf_dbt_nt if canon == "nt" else diag_pkf_dbt_ot
        entry = d.get(iso)
        if entry and entry.get("category"):
            return entry["category"].replace("likely_", "")
        return tier(score)

    def helloao_dbt_likely(iso, canon, hid, score):
        if score == 1.0:
            return "identical"
        entry = diag_hao_dbt.get(f"{iso}:{canon}:{hid}")
        if entry and entry.get("category"):
            return entry["category"].replace("likely_", "")
        return tier(score)

    def pkf_hao_likely(iso, canon, score):
        if score == 1.0:
            return "identical"
        entry = diag_pkf_hao.get(f"{iso}:{canon}")
        if entry and entry.get("category"):
            return entry["category"].replace("likely_", "")
        return tier(score)

    all_isos = set(pkf_manifest.keys()) | {k[0] for k in dbt_native_by_iso_canon} | set(helloao_by_iso.keys())

    rows = []
    for iso in sorted(all_isos):
        for canon in ("nt", "ot"):
            dbt_ids = sorted(dbt_native_by_iso_canon.get((iso, canon), []))
            has_pkf_collection = bool(pkf_manifest.get(iso, {}).get("collections"))
            pkf_has_canon = has_pkf_collection and (canon == "nt" or any(
                (c.get("coverage") or {}).get("o") for c in pkf_manifest.get(iso, {}).get("collections", [])))
            hao_ids_here = [hid for hid in helloao_by_iso.get(iso, [])
                             if (iso, canon, hid) in hao_dbt or
                             (pkf_hao_entry(iso, canon) or {}).get("all_scores", {}).get(hid) is not None]

            if not dbt_ids and not pkf_has_canon and not hao_ids_here:
                continue

            uf = UnionFind()
            nodes = set()
            for did in dbt_ids:
                nodes.add(f"dbt:{did}")
            pkf_node = f"pkf:{iso.upper()}PKF" if pkf_has_canon else None
            if pkf_node:
                nodes.add(pkf_node)
            for hid in hao_ids_here:
                nodes.add(f"helloao:{hid}")
            for n in sorted(nodes):
                uf.find(n)

            # PKF-vs-DBT identical edge
            pd = pkf_dbt_entry(iso, canon)
            if pkf_node and pd and pd.get("status") == "compared" and pd["best_score"] == 1.0:
                uf.union(pkf_node, f"dbt:{pd['best_match']}")

            # helloAO-vs-DBT identical edges (per helloAO id, best match only)
            for hid in hao_ids_here:
                scores = hao_dbt.get((iso, canon, hid))
                if scores:
                    best_did = max(scores, key=lambda k: (scores[k] is not None, scores[k] or -1))
                    if scores[best_did] == 1.0:
                        uf.union(f"helloao:{hid}", f"dbt:{best_did}")

            # PKF-vs-helloAO identical edge (best match only)
            ph = pkf_hao_entry(iso, canon)
            if pkf_node and ph and ph.get("status") == "compared" and ph["best_score"] == 1.0:
                uf.union(pkf_node, f"helloao:{ph['best_match']}")

            clusters = {}
            for n in sorted(nodes):
                clusters.setdefault(uf.find(n), []).append(n)

            pkf_source_ref = None
            if pd and pd.get("pkf_file"):
                pkf_source_ref = pd["pkf_file"]
            elif ph and ph.get("pkf_file"):
                pkf_source_ref = ph["pkf_file"]
            if pkf_source_ref and pkf_source_ref.count(".") >= 2:
                pkf_source_ref = pkf_source_ref.rsplit(".", 2)[0]

            for members in clusters.values():
                ids = sorted(members)
                cluster = {"ids": ids}
                # pkf:<ISO>PKF is always a minted display label, never the
                # real fetchable id (that's the .pkf collection filename) —
                # attach it whenever a pkf member is in this cluster at all,
                # not just when pkf is a singleton. helloAO/DBT ids are
                # already their own real fetchable id (never borrowed), so
                # they need no separate source_ref.
                if pkf_node in ids and pkf_source_ref:
                    cluster["pkf_source_ref"] = pkf_source_ref

                if len(ids) > 1:
                    default = min(ids, key=lambda x: PRIORITY[x.split(":", 1)[0]])
                    cluster["default"] = default
                    rows.append([iso, canon, cluster])
                    continue

                # Singleton — attach the single most-informative "closest
                # relative" this node has, if any, picking whichever
                # candidate relationship scores highest (not always DBT).
                member = ids[0]
                source, mid = member.split(":", 1)
                candidates = []  # (ref, likely, score)

                if source == "pkf":
                    if pd and pd.get("status") == "compared":
                        candidates.append((f"dbt:{pd['best_match']}",
                                            pkf_dbt_likely(iso, canon, pd["best_score"]), pd["best_score"]))
                    if ph and ph.get("status") == "compared":
                        candidates.append((f"helloao:{ph['best_match']}",
                                            pkf_hao_likely(iso, canon, ph["best_score"]), ph["best_score"]))
                elif source == "helloao":
                    scores = hao_dbt.get((iso, canon, mid))
                    if scores:
                        valid = {k: v for k, v in scores.items() if v is not None}
                        if valid:
                            best_did = max(valid, key=valid.get)
                            candidates.append((f"dbt:{best_did}",
                                                helloao_dbt_likely(iso, canon, mid, valid[best_did]), valid[best_did]))
                    if ph and ph.get("status") == "compared":
                        hscore = (ph.get("all_scores") or {}).get(mid)
                        if hscore is not None:
                            likely = pkf_hao_likely(iso, canon, hscore) if ph.get("best_match") == mid else tier(hscore)
                            candidates.append((f"pkf:{iso.upper()}PKF", likely, hscore))
                # dbt singletons: no "closest" — see module docstring.

                if candidates:
                    ref, likely, score = max(candidates, key=lambda c: c[2])
                    cluster["likely"] = likely
                    cluster["closest"] = ref
                    cluster["score"] = round(score, 4)

                rows.append([iso, canon, cluster])

    # Deterministic output — nodes/clusters were built from Python sets
    # along the way, whose iteration order isn't stable across processes
    # (hash randomization). Sort explicitly so regenerating with unchanged
    # underlying data always produces byte-identical output, not just
    # equivalent-content-different-order.
    rows.sort(key=lambda r: (r[0], r[1], sorted(r[2]["ids"])))

    output = {
        "generated_at": None,  # stamped at publish time, not by this generator
        "probes": {"nt": ["REV15"], "ot": ["PSA117", "PSA51"]},
        "priority": ["pkf", "helloao", "dbt"],
        "audio_source": "dbt",
        "entries": rows,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    n_langs = len({(r[0], r[1]) for r in rows})
    print(f"[generate-catalog-overlap] {len(rows)} clusters across {n_langs} (iso,canon) pairs -> {out_path}")


if __name__ == "__main__":
    main()
