#!/usr/bin/env python3
"""Taxonomy diagnosis for PKF-vs-helloAO comparisons — the third leg,
completing the same taxonomy mechanization now applied to all three
pairwise comparisons (PKF-vs-DBT, helloAO-vs-DBT, and this one).

Per the same scoping rule as the other two diagnosis scripts: only the
single BEST-MATCH helloAO translation per (iso, canon) is diagnosed.

Reuses the exact "pkf_file" the char-level pass already recorded (not
re-derived) — for niy-like multi-collection languages, re-deriving
independently could silently pick a different collection than the one the
recorded score is actually based on.

Uses diagnose_taxonomy.py (see its module docstring / diagnose_pkf_dbt_diff.py's
for the full taxonomy). No text is retained.

Resumable: writes incrementally, skips (iso, canon) keys already recorded.

Usage:
    python3 diagnose_pkf_helloao_diff.py [--book B] [--chapter N] [--limit N]
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comparison"))
from batch_compare_pkf_helloao import fetch_pkf_chapter, fetch_helloao_chapter, rclone_env  # noqa: E402
from compare_pkf_dbt import compare  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import COMPARISON_RESULTS_DIR, PKF_HELLOAO_DIAGNOSIS_FILE  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnose_taxonomy import classify  # noqa: E402

OUT_PATH = PKF_HELLOAO_DIAGNOSIS_FILE


def candidates_to_diagnose(canon: str) -> dict:
    """iso -> {pkf_file, best_match (helloao_id), best_score} for every
    language whose best-match score is < 1.0, for the given canon."""
    fname = "pkf-helloao-comparison.json" if canon == "nt" else "pkf-helloao-comparison-ot.json"
    p = COMPARISON_RESULTS_DIR / fname
    if not p.exists():
        return {}
    d = json.loads(p.read_text())
    return {
        iso: r for iso, r in d.items()
        if r.get("status") == "compared" and r.get("best_score", 1.0) < 1.0 and r.get("pkf_file")
    }


def process_one(iso: str, pkf_file: str, best_match: str, recorded_score: float,
                 env: dict, bucket: str, tmpdir: Path, book: str, chapter: int) -> dict:
    pkf_chars, _ = fetch_pkf_chapter(iso, [pkf_file], env, bucket, tmpdir, book, chapter)
    if not pkf_chars:
        return {"status": "no_pkf_text"}

    hao_chars = fetch_helloao_chapter(best_match, book, chapter)
    if not hao_chars:
        return {"status": "helloao_no_text"}

    live_score = compare(pkf_chars, hao_chars)
    entry = classify(live_score, pkf_chars, hao_chars, compare)
    entry["status"] = "diagnosed"
    entry["best_match"] = best_match
    entry["recorded_score"] = recorded_score
    if abs(live_score - recorded_score) > 0.001:
        entry["score_drift_warning"] = True
    return entry


def main():
    args = sys.argv[1:]
    book, chapter = "REV", 15
    if "--book" in args:
        book = args[args.index("--book") + 1]
    if "--chapter" in args:
        chapter = int(args[args.index("--chapter") + 1])
    canon = "nt" if book == "REV" else "ot"
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    env, bucket = rclone_env()
    candidates = candidates_to_diagnose(canon)
    results = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}

    def key(iso):
        return f"{iso}:{canon}"

    todo = [iso for iso in candidates if key(iso) not in results]
    if limit:
        todo = todo[:limit]

    print(f"[diagnose-pkf-helloao] {len(candidates)} candidates ({canon}, best_score<1.0), "
          f"{len(results)} already done, {len(todo)} to process this run")

    tmpdir = Path(tempfile.mkdtemp(prefix="pkf_helloao_diag_"))
    try:
        for i, iso in enumerate(todo, 1):
            c = candidates[iso]
            try:
                entry = process_one(iso, c["pkf_file"], c["best_match"], c["best_score"],
                                     env, bucket, tmpdir, book, chapter)
            except Exception as e:
                entry = {"status": "error", "error": str(e)[:200]}
            entry.update({"iso": iso, "canon": canon})
            results[key(iso)] = entry
            tag = entry.get("category", entry["status"])
            print(f"  [{i}/{len(todo)}] {key(iso)}: {tag} (score={entry.get('best_score', '-')})")
            for p in tmpdir.iterdir():
                if p.name.startswith(f"{iso}_"):
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
            if i % 10 == 0:
                OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    from collections import Counter
    tally = Counter(r.get("category", r["status"]) for r in results.values())
    print(f"\n[diagnose-pkf-helloao] done. {len(results)} total recorded.")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
