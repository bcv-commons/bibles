#!/usr/bin/env python3
"""Automated taxonomy classifier for the PKF/DBT comparison pilot's non-1.0
scores — the "why did this language not score 1.0" question, mechanized.

Builds on (does not modify) the two validated signal-extraction scripts:
  - compare_pkf_dbt.py       (character-level score, per language)
  - compare_pkf_dbt_words.py (word-level score, per language, second opinion)

Per user instruction: only the single BEST-MATCH DBT version (already
recorded in data/pkf-dbt-comparison.json) is classified per language — no
need to re-diagnose every DBT version, only the one PKF is actually being
compared against for a verdict. This bounds the pool to the languages that
scored < 1.0 against their best match (82 at last count), not the full
524-language population.

For each candidate: re-fetch + decode PKF (ephemeral, deleted immediately
after scoring — same verdict-only discipline as the other two scripts, no
PKF text is ever retained), recompute the diff against the best-match DBT
text, and classify into the taxonomy built up manually across the pilot:

  single_pair_dominant_ambiguous one dominant substitution pair, and forcing
                                  the substitution (a live test, not a guess)
                                  drives the score to ~1.0. IMPORTANT: this
                                  alone does NOT prove it's a bug — validated
                                  against known cases and found to give a
                                  FALSE POSITIVE for bsn/gvc/tue (confirmed
                                  genuine phonemic distinctions: ʉ vs u are
                                  different vowels in these languages, yet
                                  forcing the substitution also reaches 1.0,
                                  because that's mechanically guaranteed
                                  whenever one pair accounts for the whole
                                  gap, bug or not). So this category is
                                  intentionally NOT auto-labeled "bug" —
                                  flagged for human review (with the
                                  substitution test score as supporting
                                  evidence, not proof) before anything is
                                  ever added to compare_pkf_dbt.py's
                                  _HOMOGLYPH_TRANSLATION table.
  likely_phonemic_distinction    either forcing the dominant pair does NOT
                                  reach ~1.0 (safe automated evidence AGAINST
                                  a bug — the pair alone can't be the whole
                                  story), or the pair matches an
                                  already-confirmed genuine distinction from
                                  earlier manual investigation (_KNOWN_
                                  PHONEMIC_PAIRS, e.g. ʉ/u — see
                                  CLAUDE.local.md).
  likely_source_duplication      a large hunk whose content (or most of it)
                                  reappears elsewhere in its OWN source text
                                  (the des pattern — PKF's own digitization
                                  repeated a sentence).
  likely_orthography_convention  a small number of distinct substitution
                                  pairs (2-5) together cover most hunks (the
                                  cul/tpp/cui pattern — several consistent
                                  spelling-system differences, not one).
  likely_dialect_variant         many distinct, low-frequency substitution
                                  pairs (no concentration) but score still
                                  >= 0.85 (the knj/KNJSBI pattern).
  likely_distinct_translation    same "no concentration" shape but score
                                  < 0.85 — reads as real wording difference.
  unclassified                   none of the above signatures fit cleanly;
                                  left honest rather than forced into a
                                  bucket, for manual review.

Also flags likely_word_spacing_convention as an ADDITIONAL note (not a
replacement classification) when the word-level score (from
data/pkf-dbt-comparison-words.json, already computed — not re-derived here)
is much lower than the char-level score — that gap is the word-level
method's own known blind spot (see the tav case), not evidence the
char-level verdict is wrong.

Every classification keeps up to 3 sample diff hunks (trimmed, with a few
characters of context) so a human can see WHY a category was chosen without
re-running anything — this is the demonstration table the taxonomy write-up
needs.

No PKF text is retained: the sample hunks stored are the diff FRAGMENTS
only (typically a handful of characters), not full verses or chapters.

Resumable: writes incrementally, skips isos already recorded on rerun.

Usage:
    python3 scripts/diagnose_pkf_dbt_diff.py [--limit N]
"""
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comparison"))
from batch_compare_pkf_dbt import rclone_env, candidate_isos  # noqa: E402
from compare_pkf_dbt import (  # noqa: E402
    extract_pkf_chapter,
    dbt_samples,
    compare,
    normalize_chars,
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import (  # noqa: E402
    PKF_DBT_COMPARISON_FILE,
    PKF_DBT_COMPARISON_WORDS_FILE,
    PKF_DBT_COMPARISON_DIAGNOSIS_FILE,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnose_taxonomy import classify as _classify_generic  # noqa: E402

CHAR_RESULTS_PATH = PKF_DBT_COMPARISON_FILE
WORD_RESULTS_PATH = PKF_DBT_COMPARISON_WORDS_FILE
OUT_PATH = PKF_DBT_COMPARISON_DIAGNOSIS_FILE
BOOK, CHAPTER = "REV", 15

_WORD_GAP_THRESHOLD = 0.15


def candidates_to_diagnose() -> dict:
    """iso -> pkf filename, for every language whose best-match score in the
    char-level pass is < 1.0. Single best-match only, per the scoping rule.

    Prefers the exact "pkf_file" the char-level pass already recorded,
    rather than re-deriving it — for niy (multiple collections), the
    char-level pass already disambiguated empirically; re-deriving
    independently could silently pick a different collection and diagnose
    the wrong text. But most of the 80-language population predates that
    field being added to batch_compare_pkf_dbt.py's output (single-
    collection languages only, no ambiguity risk) — for those, fall back
    to re-deriving via candidate_isos(), instead of silently dropping them
    from the candidate set (found via a byte-identical-output check after
    extracting diagnose_taxonomy.py: only 2 of 80 languages were being
    diagnosed, not 80 — this fallback restores the other 78)."""
    char_results = json.loads(CHAR_RESULTS_PATH.read_text())
    todo_isos = {
        iso for iso, r in char_results.items()
        if r.get("status") == "compared" and r.get("best_score", 1.0) < 1.0
    }
    out = {}
    missing_pkf_file = [iso for iso in todo_isos if not char_results[iso].get("pkf_file")]
    fallback = candidate_isos() if missing_pkf_file else {}
    for iso in todo_isos:
        pkf_file = char_results[iso].get("pkf_file")
        if not pkf_file and iso in fallback:
            pkf_file = fallback[iso]["pkf_files"][0]
        if pkf_file:
            out[iso] = pkf_file
    return out


def classify(iso: str, score: float, pkf_chars: str, dbt_chars: str, word_results: dict) -> dict:
    """Thin wrapper around diagnose_taxonomy.classify() — translates the
    shared module's generic a/b field names back to pkf/dbt for exact
    backward compatibility with this file's already-published output shape
    (data/pkf-dbt-comparison-diagnosis.json), then adds the word-gap note
    (PKF-vs-DBT specific: relies on the word-level second-opinion pass,
    which only exists for this comparison, not the helloAO ones)."""
    result = _classify_generic(score, pkf_chars, dbt_chars, compare)
    for d in result.get("sample_diffs", []):
        d["pkf_fragment"] = d.pop("a_fragment")
        d["dbt_fragment"] = d.pop("b_fragment")
    if result.get("self_duplication"):
        result["self_duplication"]["side"] = {"a": "pkf", "b": "dbt"}[result["self_duplication"]["side"]]
    _add_word_gap_note(iso, result, word_results)
    return result


def _add_word_gap_note(iso: str, result: dict, word_results: dict) -> None:
    w = word_results.get(iso)
    if not w or w.get("status") != "compared":
        return
    word_score = w.get("best_score")
    if word_score is None:
        return
    gap = result["best_score"] - word_score
    result["word_score"] = word_score
    result["char_word_gap"] = round(gap, 4)
    if gap >= _WORD_GAP_THRESHOLD:
        result["note_word_spacing_convention"] = True


def process_one(iso: str, pkf_file: str, best_match: str, best_score: float,
                 word_results: dict, env: dict, bucket: str, tmpdir: Path) -> dict:
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

    pkf_chars = extract_pkf_chapter(usfm_path, CHAPTER)
    if not pkf_chars:
        return {"status": "no_pkf_text"}

    dbt = dbt_samples(iso, BOOK, CHAPTER)
    dbt_chars = dbt.get(best_match)
    if dbt_chars is None:
        return {"status": "best_match_missing"}

    # Sanity check against the recorded score — re-derive, don't trust the
    # cached value blindly (normalize_chars/compare are unchanged, so this
    # should match; a mismatch would mean the underlying sample data moved
    # since the char-level pass ran).
    live_score = compare(pkf_chars, dbt_chars)

    entry = classify(iso, live_score, pkf_chars, dbt_chars, word_results)
    entry["status"] = "diagnosed"
    entry["best_match"] = best_match
    entry["recorded_score"] = best_score
    if abs(live_score - best_score) > 0.001:
        entry["score_drift_warning"] = True
    return entry


def main():
    args = sys.argv[1:]
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    env, bucket = rclone_env()
    char_results = json.loads(CHAR_RESULTS_PATH.read_text())
    word_results = json.loads(WORD_RESULTS_PATH.read_text()) if WORD_RESULTS_PATH.exists() else {}
    candidates = candidates_to_diagnose()

    results = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}
    todo = [iso for iso in candidates if iso not in results]
    if limit:
        todo = todo[:limit]

    print(f"[diagnose] {len(candidates)} candidates (best_score<1.0, single best-match each), "
          f"{len(results)} already done, {len(todo)} to process this run")

    tmpdir = Path(tempfile.mkdtemp(prefix="pkf_diagnose_"))
    try:
        for i, iso in enumerate(todo, 1):
            r = char_results[iso]
            entry = process_one(
                iso, candidates[iso], r["best_match"], r["best_score"],
                word_results, env, bucket, tmpdir,
            )
            results[iso] = entry
            tag = entry.get("category", entry["status"])
            print(f"  [{i}/{len(todo)}] {iso}: {tag} (score={entry.get('best_score', '-')})")
            for p in tmpdir.iterdir():
                if p.name.startswith(iso):
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
            if i % 10 == 0:
                OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    tally = Counter(r.get("category", r["status"]) for r in results.values())
    print(f"\n[diagnose] done. {len(results)} total languages recorded.")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")
    drifted = [iso for iso, r in results.items() if r.get("score_drift_warning")]
    if drifted:
        print(f"  score_drift_warning (recorded vs live score mismatch): {drifted}")


if __name__ == "__main__":
    main()
