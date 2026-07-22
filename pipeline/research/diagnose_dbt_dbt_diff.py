#!/usr/bin/env python3
"""Taxonomy diagnosis for DBT-vs-DBT (same-source) comparisons — the same
mechanization already applied to the other four legs, now covering the
fifth: DBT's own multiple native versions against each other.

Per the same scoping rule as every other diagnosis script: only each
item's single BEST-MATCH partner is diagnosed, not every pair it was
compared against. Computed here as: for every DBT version fetched in
batch_compare_dbt_dbt.py's run, find its single highest-scoring partner
within its (iso, canon) group; if that best score is < 1.0, diagnose that
one pair. Pairs are deduplicated (a mutual best-match only gets diagnosed
once).

Uses diagnose_taxonomy.py (see its module docstring / diagnose_pkf_dbt_diff.py's
for the full taxonomy). No text is retained — re-fetched fresh, classified,
discarded.

Resumable: writes incrementally, skips pairs already recorded on rerun.

Usage:
    python3 diagnose_dbt_dbt_diff.py [--book B] [--chapter N] [--limit N]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import download_language_content as dl  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comparison"))
from compare_pkf_dbt import normalize_chars, compare  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, COMPARISON_RESULTS_DIR  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnose_taxonomy import classify  # noqa: E402
from confirm_text_availability import resolve_fileset  # noqa: E402

IN_PATH = COMPARISON_RESULTS_DIR / "dbt-dbt-comparison.json"
OUT_PATH = COMPARISON_RESULTS_DIR / "dbt-dbt-diagnosis.json"


def best_match_pairs() -> dict:
    """(iso, canon, sorted_pair_tuple) -> recorded_score, for every item's
    single best (max-score) < 1.0 partner within its group. Deduplicated —
    a mutual best-match pair is only diagnosed once."""
    data = json.loads(IN_PATH.read_text())
    out = {}
    for entry in data.values():
        scores = entry.get("scores", {})
        ids = entry.get("versions_fetched", [])
        for x in ids:
            best_score, best_partner = -1, None
            for pair, score in scores.items():
                a, b = pair.split("|")
                if x in (a, b):
                    other = b if a == x else a
                    if score > best_score:
                        best_score, best_partner = score, other
            if best_partner and best_score < 1.0:
                key = (entry["iso"], entry["canon"], tuple(sorted([x, best_partner])))
                out[key] = best_score
    return out


def resolve(iso: str, canon: str, distinct_id: str) -> str | None:
    catalog = resolve._catalog
    for row in catalog["versions"]:
        if row[0] == iso and row[1] == distinct_id and row[2].rstrip("p") == canon:
            spec = next((f for f in row[3:] if f.split(":", 1)[0] in ("t", "T")), None)
            if spec:
                return resolve_fileset(distinct_id, spec)
    return None


resolve._catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())


def process_one(iso: str, canon: str, a: str, b: str, recorded_score: float) -> dict:
    book, chapter = ("REV", 15) if canon == "nt" else ("PSA", 117)
    fileset_a, fileset_b = resolve(iso, canon, a), resolve(iso, canon, b)
    if not fileset_a or not fileset_b:
        return {"status": "fileset_unresolved"}

    result_a = dl.get_text_content(fileset_a, book, chapter)
    time.sleep(0.1)
    result_b = dl.get_text_content(fileset_b, book, chapter)
    time.sleep(0.1)
    if not result_a or result_a.get("type") != "verses" or not result_b or result_b.get("type") != "verses":
        return {"status": "no_text"}

    text_a = normalize_chars(" ".join(item.get("verse_text", "") for item in result_a["data"]))
    text_b = normalize_chars(" ".join(item.get("verse_text", "") for item in result_b["data"]))
    if not text_a or not text_b:
        return {"status": "no_text"}

    live_score = compare(text_a, text_b)
    entry = classify(live_score, text_a, text_b, compare)
    entry["status"] = "diagnosed"
    entry["recorded_score"] = recorded_score
    if abs(live_score - recorded_score) > 0.001:
        entry["score_drift_warning"] = True
    return entry


def main():
    args = sys.argv[1:]
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    candidates = best_match_pairs()
    results = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}

    def key(iso, canon, pair):
        return f"{iso}:{canon}:{pair[0]}|{pair[1]}"

    todo = [k for k in candidates if key(*k) not in results]
    if limit:
        todo = todo[:limit]

    print(f"[diagnose-dbt-dbt] {len(candidates)} candidates, {len(results)} already done, "
          f"{len(todo)} to process this run")

    for i, (iso, canon, pair) in enumerate(todo, 1):
        a, b = pair
        try:
            entry = process_one(iso, canon, a, b, candidates[(iso, canon, pair)])
        except Exception as e:
            entry = {"status": "error", "error": str(e)[:200]}
        entry.update({"iso": iso, "canon": canon, "a": a, "b": b})
        results[key(iso, canon, pair)] = entry
        tag = entry.get("category", entry["status"])
        print(f"  [{i}/{len(todo)}] {key(iso, canon, pair)}: {tag} (score={entry.get('best_score', '-')})")
        if i % 10 == 0:
            OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    from collections import Counter
    tally = Counter(r.get("category", r["status"]) for r in results.values())
    print(f"\n[diagnose-dbt-dbt] done. {len(results)} total recorded.")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
