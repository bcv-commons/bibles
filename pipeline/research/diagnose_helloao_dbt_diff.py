#!/usr/bin/env python3
"""Taxonomy diagnosis for helloAO-vs-DBT comparisons — the same
mechanization built for PKF-vs-DBT (diagnose_pkf_dbt_diff.py), applied to
the helloAO legs for the first time. Triggered by a real client question
about a flat "uncertain" score with no explanation (spa_onbv vs 6 DBT
Spanish OT versions, all landing 0.5-0.77 with no clear winner flagged).

Per the same scoping rule as the PKF diagnosis: only the single BEST-MATCH
DBT version per (iso, canon, helloao_id) is diagnosed — not every DBT
version that was compared, only the one a client would actually be shown
as the closest match.

Uses diagnose_taxonomy.py (extracted from diagnose_pkf_dbt_diff.py, see
its module docstring) — the exact same classification logic, applied here
to helloAO/DBT character streams instead of PKF/DBT ones. Calibration was
done against the PKF pilot; applying it here is a starting assumption, not
independently re-validated.

No text is retained: helloAO chapter JSON is fetched fresh, classified,
and discarded — same verdict-only discipline as every other script here.

Resumable: writes incrementally, skips (iso, canon, helloao_id) keys
already recorded on rerun.

Usage:
    python3 diagnose_helloao_dbt_diff.py [--limit N]
"""
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comparison"))
from batch_compare_helloao_dbt import extract_helloao_chapter, dbt_native_chars, HELLOAO_API  # noqa: E402
from compare_pkf_dbt import compare  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import COMPARISON_RESULTS_DIR, HELLOAO_DBT_DIAGNOSIS_FILE  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnose_taxonomy import classify  # noqa: E402

OUT_PATH = HELLOAO_DBT_DIAGNOSIS_FILE


def load(name, default=None):
    p = COMPARISON_RESULTS_DIR / name
    return json.loads(p.read_text()) if p.exists() else (default if default is not None else {})


def candidates_to_diagnose() -> dict:
    """(iso, canon, helloao_id) -> {"best_match": dbt_id, "best_score": float}
    for every entry across phase1/phase2/phase3 whose best score is < 1.0.
    Single best-match only, per the scoping rule — the DBT id a client
    would actually be shown, not every version compared."""
    merged = {}
    for row in load("helloao-dbt-phase1.json").values():
        if row.get("status") == "compared":
            merged[(row["iso"], row["canon"], row["helloao_id"])] = row
    for row in load("helloao-dbt-phase2.json").values():
        if row.get("status") == "compared":
            merged[(row["iso"], row["canon"], row["helloao_id"])] = row
    for row in load("helloao-dbt-phase3.json", []):
        if row.get("best_score") is not None:
            merged[(row["iso"], row["canon"], row["helloao_id"])] = {
                "best_match": max(row["scores"], key=row["scores"].get),
                "best_score": max(row["scores"].values()),
            }
    return {k: v for k, v in merged.items() if v.get("best_score", 1.0) < 1.0}


def process_one(iso: str, canon: str, helloao_id: str, best_match: str, recorded_score: float) -> dict:
    book, chapter = ("REV", 15) if canon == "nt" else ("PSA", 117)
    try:
        r = requests.get(f"{HELLOAO_API}/{helloao_id}/{book}/{chapter}.json", timeout=15)
    except requests.RequestException as e:
        return {"status": "helloao_fetch_failed", "error": str(e)[:200]}
    if r.status_code != 200:
        return {"status": "helloao_fetch_failed", "error": f"http_{r.status_code}"}
    try:
        payload = r.json()
    except ValueError:
        return {"status": "helloao_no_text"}
    hao_chars = extract_helloao_chapter(payload.get("chapter", {}))
    if not hao_chars:
        return {"status": "helloao_no_text"}

    dbt_chars = dbt_native_chars(iso, canon, best_match, book, chapter)
    if not dbt_chars:
        return {"status": "dbt_sample_missing"}

    # Sanity check against the recorded score — re-derive, don't trust
    # blindly (same discipline as diagnose_pkf_dbt_diff.py).
    live_score = compare(hao_chars, dbt_chars)

    entry = classify(live_score, hao_chars, dbt_chars, compare)
    entry["status"] = "diagnosed"
    entry["best_match"] = best_match
    entry["recorded_score"] = recorded_score
    if abs(live_score - recorded_score) > 0.001:
        entry["score_drift_warning"] = True
    return entry


def main():
    args = sys.argv[1:]
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    candidates = candidates_to_diagnose()
    results = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}

    def key(iso, canon, hid):
        return f"{iso}:{canon}:{hid}"

    todo = [k for k in candidates if key(*k) not in results]
    if limit:
        todo = todo[:limit]

    print(f"[diagnose-helloao-dbt] {len(candidates)} candidates (best_score<1.0, single best-match each), "
          f"{len(results)} already done, {len(todo)} to process this run")

    for i, (iso, canon, hid) in enumerate(todo, 1):
        c = candidates[(iso, canon, hid)]
        entry = process_one(iso, canon, hid, c["best_match"], c["best_score"])
        entry.update({"iso": iso, "canon": canon, "helloao_id": hid})
        results[key(iso, canon, hid)] = entry
        tag = entry.get("category", entry["status"])
        print(f"  [{i}/{len(todo)}] {key(iso, canon, hid)}: {tag} (score={entry.get('best_score', '-')})")
        if i % 10 == 0:
            OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    from collections import Counter
    tally = Counter(r.get("category", r["status"]) for r in results.values())
    print(f"\n[diagnose-helloao-dbt] done. {len(results)} total recorded.")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
