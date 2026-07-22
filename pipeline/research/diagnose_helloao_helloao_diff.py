#!/usr/bin/env python3
"""Taxonomy diagnosis for helloAO-vs-helloAO (same-source) comparisons —
the same mechanization applied to the other four legs, now covering the
sixth relationship type: helloAO's own multiple translations against
each other.

Per the same scoping rule as every other diagnosis script: only each
translation's single BEST-MATCH partner is diagnosed, not every pair.

Uses diagnose_taxonomy.py (see its module docstring / diagnose_pkf_dbt_diff.py's
for the full taxonomy). No text is retained — re-fetched fresh, classified,
discarded.

Resumable: writes incrementally, skips pairs already recorded on rerun.

Usage:
    python3 diagnose_helloao_helloao_diff.py [--book B] [--chapter N] [--limit N]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comparison"))
from batch_compare_helloao_dbt import extract_helloao_chapter, HELLOAO_API  # noqa: E402
from compare_pkf_dbt import compare  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import COMPARISON_RESULTS_DIR  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnose_taxonomy import classify  # noqa: E402

import requests

IN_PATH = COMPARISON_RESULTS_DIR / "helloao-helloao-comparison.json"
OUT_PATH = COMPARISON_RESULTS_DIR / "helloao-helloao-diagnosis.json"


def best_match_pairs() -> dict:
    """(iso, canon, sorted_pair_tuple) -> recorded_score, for every
    translation's single best (max-score) < 1.0 partner in its group."""
    data = json.loads(IN_PATH.read_text())
    out = {}
    for entry in data.values():
        scores = entry.get("scores", {})
        ids = entry.get("translations_fetched", [])
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


def fetch_chapter(translation_id: str, book: str, chapter: int) -> str | None:
    try:
        r = requests.get(f"{HELLOAO_API}/{translation_id}/{book}/{chapter}.json", timeout=15)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        payload = r.json()
    except ValueError:
        return None
    return extract_helloao_chapter(payload.get("chapter", {})) or None


def process_one(canon: str, a: str, b: str, recorded_score: float) -> dict:
    book, chapter = ("REV", 15) if canon == "nt" else ("PSA", 117)
    text_a = fetch_chapter(a, book, chapter)
    text_b = fetch_chapter(b, book, chapter)
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

    print(f"[diagnose-helloao-helloao] {len(candidates)} candidates, {len(results)} already done, "
          f"{len(todo)} to process this run")

    for i, (iso, canon, pair) in enumerate(todo, 1):
        a, b = pair
        try:
            entry = process_one(canon, a, b, candidates[(iso, canon, pair)])
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
    print(f"\n[diagnose-helloao-helloao] done. {len(results)} total recorded.")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
