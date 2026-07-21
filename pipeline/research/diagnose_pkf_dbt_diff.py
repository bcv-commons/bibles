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
import difflib
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comparison"))
from batch_compare_pkf_dbt import rclone_env  # noqa: E402
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

CHAR_RESULTS_PATH = PKF_DBT_COMPARISON_FILE
WORD_RESULTS_PATH = PKF_DBT_COMPARISON_WORDS_FILE
OUT_PATH = PKF_DBT_COMPARISON_DIAGNOSIS_FILE
BOOK, CHAPTER = "REV", 15

_SELF_DUP_MIN_LEN = 30   # normalized chars — calibrated against the 82-language run: the two
                          # confirmed genuine cases (des, mpx) both had 60-char repeats, while
                          # a first pass at 15 chars also flagged 10 more languages with only
                          # 15-19 char repeats — almost certainly coincidental short-sequence
                          # recurrence in short, morphologically repetitive texts (agglutinative
                          # languages reusing common morphemes), not real duplication. 30 sits
                          # clearly between the two clusters.
_ORTHO_MAX_PAIRS = 5     # <= this many distinct pairs covering 80% of hunks => orthography convention
_DIALECT_SCORE_FLOOR = 0.85
_WORD_GAP_THRESHOLD = 0.15

# Pairs already manually confirmed (via linguistic cross-check, not a
# substitution test alone) to be genuine phonemic distinctions rather than
# encoding bugs — see CLAUDE.local.md. Checked here so re-encountering the
# exact same pair in a new language doesn't need re-litigating.
_KNOWN_PHONEMIC_PAIRS = {frozenset({"ʉ", "u"})}


def candidates_to_diagnose() -> dict:
    """iso -> pkf filename, for every language whose best-match score in the
    char-level pass is < 1.0. Single best-match only, per the scoping rule.
    Reuses the exact "pkf_file" the char-level pass already recorded, rather
    than re-deriving it — for niy (multiple collections), the char-level
    pass already disambiguated empirically; re-deriving independently could
    silently pick a different collection and diagnose the wrong text."""
    char_results = json.loads(CHAR_RESULTS_PATH.read_text())
    return {
        iso: r["pkf_file"] for iso, r in char_results.items()
        if r.get("status") == "compared" and r.get("best_score", 1.0) < 1.0 and r.get("pkf_file")
    }


def diff_opcodes(pkf_chars: str, dbt_chars: str):
    sm = difflib.SequenceMatcher(a=pkf_chars, b=dbt_chars, autojunk=False)
    return [op for op in sm.get_opcodes() if op[0] != "equal"]


def pair_counter(pkf_chars: str, dbt_chars: str, opcodes) -> Counter:
    return Counter((pkf_chars[i1:i2], dbt_chars[j1:j2]) for _, i1, i2, j1, j2 in opcodes)


def distinct_pairs_for_80pct(pairs: Counter, total_hunks: int) -> int:
    if not total_hunks:
        return 0
    covered = 0
    for i, (_, count) in enumerate(pairs.most_common(), start=1):
        covered += count
        if covered / total_hunks >= 0.8:
            return i
    return len(pairs)


def substitution_test(pkf_chars: str, dbt_chars: str, pair: tuple) -> float:
    """Force the dominant (pkf_fragment, dbt_fragment) pair to be treated as
    equivalent by rewriting the PKF side's occurrences of pkf_fragment to
    dbt_fragment, then re-score. A near-1.0 result means that one pair fully
    explains the gap (homoglyph bug); anything short of that means it
    doesn't (phonemic distinction) — mechanical, not a guess, mirrors the
    manual substitution tests done throughout the pilot."""
    pkf_frag, dbt_frag = pair
    if not pkf_frag and not dbt_frag:
        return compare(pkf_chars, dbt_chars)
    forced = pkf_chars.replace(pkf_frag, dbt_frag) if pkf_frag else pkf_chars
    return compare(forced, dbt_chars)


_SELF_DUP_MAX_HUNKS = 5   # calibrated against the 82-language run: the two confirmed genuine
                          # cases (des, mpx) are both single-hunk diffs where the duplication
                          # explains nearly the whole gap. A first pass with no hunk-count gate
                          # also flagged gdr/ntp/xav (147/234/177 hunks) — texts that are simply
                          # very different overall, where a 30-40 char coincidental repeat
                          # somewhere in a large diff is noise, not the actual explanation.


def find_self_duplication(pkf_chars: str, dbt_chars: str, opcodes) -> dict | None:
    """A large hunk whose content also reappears elsewhere in its OWN source
    (excluding the hunk's own span) — the des pattern (a duplicated sentence
    inside PKF's own digitized text). Only meaningful when the whole diff is
    simple (few hunks) — see _SELF_DUP_MAX_HUNKS."""
    if len(opcodes) > _SELF_DUP_MAX_HUNKS:
        return None
    for tag, i1, i2, j1, j2 in opcodes:
        if tag in ("delete", "replace") and (i2 - i1) >= _SELF_DUP_MIN_LEN:
            chunk = pkf_chars[i1:i2]
            rest = pkf_chars[:i1] + pkf_chars[i2:]
            if chunk in rest:
                return {"side": "pkf", "chunk": chunk[:60]}
        if tag in ("insert", "replace") and (j2 - j1) >= _SELF_DUP_MIN_LEN:
            chunk = dbt_chars[j1:j2]
            rest = dbt_chars[:j1] + dbt_chars[j2:]
            if chunk in rest:
                return {"side": "dbt", "chunk": chunk[:60]}
    return None


def sample_hunks(pkf_chars: str, dbt_chars: str, opcodes, n: int = 3) -> list:
    ranked = sorted(opcodes, key=lambda op: max(op[2] - op[1], op[4] - op[3]), reverse=True)
    out = []
    for tag, i1, i2, j1, j2 in ranked[:n]:
        out.append({
            "tag": tag,
            "pkf_fragment": pkf_chars[i1:i2][:40],
            "dbt_fragment": dbt_chars[j1:j2][:40],
        })
    return out


def classify(iso: str, score: float, pkf_chars: str, dbt_chars: str, word_results: dict) -> dict:
    opcodes = diff_opcodes(pkf_chars, dbt_chars)
    n_hunks = len(opcodes)
    pairs = pair_counter(pkf_chars, dbt_chars, opcodes)
    top_pair, top_count = (pairs.most_common(1)[0] if pairs else ((None, None), 0))
    dominant_fraction = (top_count / n_hunks) if n_hunks else 0.0
    n_pairs_80 = distinct_pairs_for_80pct(pairs, n_hunks)

    result = {
        "best_score": round(score, 4),
        "diff_hunks": n_hunks,
        "dominant_pair_fraction": round(dominant_fraction, 3),
        "distinct_pairs_for_80pct": n_pairs_80,
        "sample_diffs": sample_hunks(pkf_chars, dbt_chars, opcodes),
    }

    dup = find_self_duplication(pkf_chars, dbt_chars, opcodes)
    if dup:
        result["category"] = "likely_source_duplication"
        result["self_duplication"] = dup
        _add_word_gap_note(iso, result, word_results)
        return result

    if dominant_fraction >= 0.8 and n_hunks >= 3:
        test_score = substitution_test(pkf_chars, dbt_chars, top_pair)
        result["substitution_test_pair"] = list(top_pair)
        result["substitution_test_score"] = round(test_score, 4)
        if frozenset(top_pair) in _KNOWN_PHONEMIC_PAIRS:
            result["category"] = "likely_phonemic_distinction"
            result["note"] = "pair matches an already-confirmed genuine distinction, not re-litigated"
        elif test_score >= 0.999:
            # Reaching ~1.0 is necessary but NOT sufficient evidence of a
            # bug (see module docstring — false positive on bsn/gvc/tue
            # during validation). Flag for human review, don't assert.
            result["category"] = "single_pair_dominant_ambiguous"
        else:
            # Safe automated call: the pair does NOT fully explain the gap,
            # so it can't be a simple encoding swap.
            result["category"] = "likely_phonemic_distinction"
        _add_word_gap_note(iso, result, word_results)
        return result

    if n_pairs_80 <= _ORTHO_MAX_PAIRS and n_pairs_80 > 0:
        result["category"] = "likely_orthography_convention"
    elif score >= _DIALECT_SCORE_FLOOR:
        result["category"] = "likely_dialect_variant"
    elif n_hunks > 0:
        result["category"] = "likely_distinct_translation"
    else:
        result["category"] = "unclassified"

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
