#!/usr/bin/env python3
"""Merge the unified comparison pipeline's output (compare_all.py's
all-comparisons.json + diagnose_all.py's all-diagnosis.json) into the
published catalog-overlap.json cluster artifact.

This replaces an earlier version of this same file that read from five
separate per-leg comparison files and five separate per-leg diagnosis files
(PKF-vs-DBT, helloAO-vs-DBT, PKF-vs-helloAO, DBT-vs-DBT, helloAO-vs-helloAO)
and needed a bespoke "likely" resolver + candidate branch per source. Since
compare_all.py already fetches every candidate id once and computes one
full pairwise score matrix per (iso,canon) regardless of which sources are
involved, the union-find and closest-relative logic here is now completely
source-agnostic — one generic path instead of five. Full-population
regression-tested against the pre-consolidation published output before
the old five-leg scripts were deleted: every row present in the old output
but not the new one was confirmed to be a strict subset of a row in the
new output (i.e. a merge/expansion, never a loss) — zero unexplained
differences across the whole 3026-(iso,canon) population.

Row shape — see doc/catalog-overlap.md for the full published contract:
    [iso, canon, cluster]
  cluster = {
    "ids": ["dbt:<id>", "helloao:<id>", "pkf:<id>", ...],
    "default": "source:id",   # only when len(ids) > 1
    "likely": "...",          # only for non-identical singletons
    "closest": "source:id",
    "score": 0.0,
    "reachable": False,           # only present (and only ever False) on a
                                   # fetch-failed/confirmed-removed placeholder
    "confirmed_removed": True,    # only alongside reachable:False, for ids
                                   # verify_samples.py positively confirmed gone
  }
`reachable`/`confirmed_removed` were added 2026-07-28 after a client
flagged a real ambiguity: a bare `{"ids": [...]}` row with no likely/closest
could mean "fetched fine, nothing to compare against" OR "failed to fetch
entirely" — indistinguishable without an explicit signal (see the `wlo`
case in doc/catalog-overlap.md).

One narrow piece of legacy behavior IS preserved rather than dropped: a
small (4-language) PKF-vs-DBT OT refinement pass using PSA 51 as a second,
longer probe to re-verify an uncertain PSA 117 result
(pkf-dbt-comparison-ot-psa51.json) predates the unified pipeline and was
never generalized to the other legs — see apply_psa51_refinement() below.
It overrides the specific pkf<->dbt edge for those 4 isos in OT before
clustering, exactly as the original generator did.

Usage:
    python3 generate_catalog_overlap.py [--out PATH]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import ALL_COMPARISONS_FILE, ALL_DIAGNOSIS_FILE, COMPARISON_RESULTS_DIR, EXPORT  # noqa: E402

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


def best_partner_in_group(group_scores: dict, item: str):
    """Given a {"a|b": score} dict for one (iso,canon) group, find item's
    single highest-scoring partner. Returns (partner, score) or (None, None)."""
    best_score, best_partner = -1, None
    for pair, score in group_scores.items():
        a, b = pair.split("|")
        if item not in (a, b) or score is None:
            continue
        other = b if a == item else a
        if score > best_score:
            best_score, best_partner = score, other
    return (best_partner, best_score) if best_partner else (None, None)


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


def apply_psa51_refinement(comparisons: dict):
    """Predates the unified pipeline: a small (4-language) re-check of
    PKF-vs-DBT OT results using PSA 51 (a longer, more statistically
    reliable probe) wherever PSA 117 (2 verses — weak discriminating power)
    gave a non-trivial result. Mutates comparisons in place, overriding just
    the pkf<->dbt edge (and pkf_source_ref) for these isos' "ot" entry."""
    psa51 = load("pkf-dbt-comparison-ot-psa51.json")
    for iso, refined in psa51.items():
        key = f"{iso}:ot"
        entry = comparisons.get(key)
        if not entry or refined.get("status") != "compared":
            continue
        pkf_id = f"pkf:{iso.upper()}PKF"
        dbt_id = f"dbt:{refined['best_match']}"
        if pkf_id not in entry.get("ids_fetched", []) or dbt_id not in entry.get("ids_fetched", []):
            continue
        pair_key = "|".join(sorted([pkf_id, dbt_id]))
        entry["scores"][pair_key] = round(refined["best_score"], 4)
        if refined.get("pkf_file"):
            entry["pkf_source_ref"] = refined["pkf_file"]


def likely_for(diagnosis: dict, iso: str, canon: str, a: str, b: str, score: float) -> str:
    if score == 1.0:
        return "identical"
    entry = diagnosis.get(f"{iso}:{canon}:{a}|{b}") or diagnosis.get(f"{iso}:{canon}:{b}|{a}")
    if entry and entry.get("category"):
        return entry["category"].replace("likely_", "")
    return tier(score)


def main():
    args = sys.argv[1:]
    out_path = Path(args[args.index("--out") + 1]) if "--out" in args else EXPORT / "dbt" / "_app" / "catalog-overlap.json"

    comparisons = json.loads(ALL_COMPARISONS_FILE.read_text())
    diagnosis = json.loads(ALL_DIAGNOSIS_FILE.read_text()) if ALL_DIAGNOSIS_FILE.exists() else {}
    apply_psa51_refinement(comparisons)

    rows = []
    for key, entry in sorted(comparisons.items()):
        if entry.get("status") not in ("compared", "no_text", "single_source"):
            continue
        iso, canon = entry["iso"], entry["canon"]
        ids_fetched = sorted(entry.get("ids_fetched", []))
        scores = entry.get("scores", {})
        pkf_source_ref = entry.get("pkf_source_ref")

        # ids_failed and ids_removed both get a placeholder row, EXPLICITLY
        # marked unreachable — a client flagged (2026-07-28, the `wlo`
        # case) that a bare `{"ids": [...]}` row with no explanation is
        # indistinguishable from "successfully fetched, just nothing to
        # compare against" (e.g. wlo's helloao:wlo_wbt, whose only sibling
        # dbt:WLOWTG failed to fetch) — a client has no way to tell "this
        # edition is fine" from "this edition is currently broken" without
        # an honest signal. `reachable: false` is that signal.
        #
        # ids_removed (verify_samples.py's confirmed-permanently-gone
        # bucket, e.g. BENBIB) gets the SAME reachable:false treatment,
        # not silent exclusion as originally designed — a positively
        # confirmed removal is exactly the kind of "the other one is not
        # OK" information a client needs, and silently vanishing it is no
        # more informative than the ambiguous bare-row problem this fixes.
        # `confirmed_removed: true` additionally distinguishes "positively
        # verified gone" (won't come back without a new fetch) from a
        # plain `ids_failed` entry (could be transient; compare_all.py
        # retries these automatically on its next run).
        for fid in sorted(entry.get("ids_failed", [])):
            rows.append([iso, canon, {"ids": [fid], "reachable": False}])
        for fid in sorted(entry.get("ids_removed", [])):
            rows.append([iso, canon, {"ids": [fid], "reachable": False, "confirmed_removed": True}])

        uf = UnionFind()
        for n in ids_fetched:
            uf.find(n)
        for pair, score in scores.items():
            if score == 1.0:
                a, b = pair.split("|")
                uf.union(a, b)

        clusters = {}
        for n in ids_fetched:
            clusters.setdefault(uf.find(n), []).append(n)

        for members in clusters.values():
            ids = sorted(members)
            cluster = {"ids": ids}
            # pkf:<ISO>PKF is always a minted display label, never the real
            # fetchable id (that's the .pkf collection filename) — attach
            # it whenever a pkf member is in this cluster at all, not just
            # when pkf is a singleton. helloAO/DBT ids are already their
            # own real fetchable id (never borrowed), so they need no
            # separate source_ref.
            if any(i.startswith("pkf:") for i in ids) and pkf_source_ref:
                cluster["pkf_source_ref"] = pkf_source_ref

            if len(ids) > 1:
                cluster["default"] = min(ids, key=lambda x: PRIORITY[x.split(":", 1)[0]])
                rows.append([iso, canon, cluster])
                continue

            # Singleton — attach the single most-informative "closest
            # relative" this node has (highest score among EVERY candidate
            # actually compared, across all sources at once — this is the
            # direct benefit of the unified pipeline's one full matrix per
            # (iso,canon), no longer needing a per-source candidate branch).
            member = ids[0]
            partner, score = best_partner_in_group(scores, member)
            if partner:
                cluster["likely"] = likely_for(diagnosis, iso, canon, member, partner, score)
                cluster["closest"] = partner
                cluster["score"] = round(score, 4)

            rows.append([iso, canon, cluster])

    # Deterministic output — see original generator's note: Python set
    # iteration order isn't stable across processes, so sort explicitly.
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
