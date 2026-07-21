#!/usr/bin/env python3
"""Word-level second-opinion pass over scripts/batch_compare_pkf_dbt.py's
results — only re-checks languages that did NOT already score a perfect
1.0 under the character-level method (nothing to learn re-verifying an
exact match with a second method).

Uses scripts/compare_pkf_dbt_words.py (ICU word segmentation, single-space
word delimiter) as a second, independent signal alongside the char-level
score already on record, to help decide how to classify/publish the
`near_identical`/`uncertain`/`distinct` tiers.

Same fetch/decode/cleanup/resumable shape as batch_compare_pkf_dbt.py
(imports its rclone/candidate-fetch plumbing directly — that infrastructure
isn't "the method," so reusing it doesn't touch the validated comparison
logic in either script).

Usage:
    python3 scripts/batch_compare_pkf_dbt_words.py [--limit N]
"""
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from batch_compare_pkf_dbt import rclone_env  # noqa: E402
from compare_pkf_dbt_words import (  # noqa: E402
    compare_words,
    dbt_samples_words,
    extract_pkf_chapter_words,
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import PKF_DBT_COMPARISON_FILE, PKF_DBT_COMPARISON_WORDS_FILE  # noqa: E402

CHAR_RESULTS_PATH = PKF_DBT_COMPARISON_FILE
OUT_PATH = PKF_DBT_COMPARISON_WORDS_FILE
BOOK, CHAPTER = "REV", 15


def candidates_to_recheck() -> dict:
    """iso -> pkf filename, for every language that scored < 1.0 in the
    char-level pass. Reuses the exact "pkf_file" the char-level pass already
    determined (recorded per-entry there) rather than re-deriving it from
    the manifest — when a language has multiple collections (niy), the
    char-level pass already disambiguated empirically; re-deriving here
    independently could silently pick a different one and compare against
    the wrong text again."""
    char_results = json.loads(CHAR_RESULTS_PATH.read_text())
    out = {}
    for iso, r in char_results.items():
        if r.get("best_score", 1.0) < 1.0 and r.get("pkf_file"):
            out[iso] = r["pkf_file"]
    return out


def process_one(iso: str, pkf_file: str, env: dict, bucket: str, tmpdir: Path) -> dict:
    pkf_path = tmpdir / f"{iso}.pkf"
    result = subprocess.run(
        ["rclone", "copyto", f"R2:{bucket}/pkf/{iso}/{pkf_file}", str(pkf_path)],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0 or not pkf_path.exists():
        return {"status": "fetch_failed", "error": result.stderr.strip()[:200]}

    out_dir = tmpdir / f"{iso}_out"
    result = subprocess.run(
        ["node", "tools/pkf-decode/decode.mjs", str(pkf_path), "--out", str(out_dir), "--book", BOOK],
        capture_output=True, text=True,
    )
    usfm_path = out_dir / f"67-{BOOK}.usfm"
    if not usfm_path.exists():
        status = "decode_failed" if result.returncode != 0 else "no_pkf_text"
        return {"status": status, "error": result.stderr.strip()[:200]}

    pkf_words = extract_pkf_chapter_words(usfm_path, CHAPTER)
    if not pkf_words:
        return {"status": "no_pkf_text"}

    dbt = dbt_samples_words(iso, BOOK, CHAPTER)
    if not dbt:
        return {"status": "no_dbt_sample"}

    best_id, best_score = None, -1.0
    scores = {}
    for distinct_id, dbt_words in dbt.items():
        s = compare_words(pkf_words, dbt_words)
        scores[distinct_id] = round(s, 4)
        if s > best_score:
            best_id, best_score = distinct_id, s

    return {
        "status": "compared",
        "best_match": best_id,
        "best_score": round(best_score, 4),
        "pkf_word_count": len(pkf_words.split()),
        "dbt_versions_compared": len(dbt),
        "all_scores": scores,
    }


def main():
    args = sys.argv[1:]
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    env, bucket = rclone_env()
    candidates = candidates_to_recheck()

    results = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}
    todo = [iso for iso in candidates if iso not in results]
    if limit:
        todo = todo[:limit]

    print(f"[batch-words] {len(candidates)} candidates (score<1.0 in char-level pass), "
          f"{len(results)} already done, {len(todo)} to process this run")

    tmpdir = Path(tempfile.mkdtemp(prefix="pkf_batch_words_"))
    try:
        for i, iso in enumerate(todo, 1):
            entry = process_one(iso, candidates[iso], env, bucket, tmpdir)
            results[iso] = entry
            print(f"  [{i}/{len(todo)}] {iso}: {entry['status']} (score={entry.get('best_score', '-')})")
            for p in tmpdir.iterdir():
                if p.name.startswith(iso):
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
            if i % 10 == 0:
                OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    tally = Counter(r["status"] for r in results.values())
    print(f"\n[batch-words] done. {len(results)} total languages recorded.")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
