"""Shared taxonomy classifier — extracted from diagnose_pkf_dbt_diff.py so
the SAME validated classification logic can be applied to any two-source
comparison, not just PKF-vs-DBT. diagnose_pkf_dbt_diff.py now imports from
here instead of defining its own copy; its behavior is unchanged (verified
byte-identical output before/after this extraction).

Genuinely source-agnostic: every function takes two normalized character
streams (whatever the two sources are — PKF, DBT, or helloAO) and a
`compare()` function, with no assumption about which side is which. The
taxonomy itself describes properties of the TEXT relationship, not of any
particular source pairing:

  single_pair_dominant_ambiguous  one dominant substitution pair, forcing it
                                   reaches ~1.0 — necessary but NOT sufficient
                                   evidence of an encoding bug (see
                                   diagnose_pkf_dbt_diff.py's docstring for
                                   why: false positive on bsn/gvc/tue, a
                                   confirmed genuine phonemic distinction).
                                   Flagged for human review, never asserted.
  likely_phonemic_distinction     forcing the dominant pair does NOT reach
                                   ~1.0, or the pair matches an
                                   already-confirmed genuine distinction
                                   (KNOWN_PHONEMIC_PAIRS).
  likely_source_duplication       a large hunk whose content reappears
                                   elsewhere in its own source text.
  likely_orthography_convention   a small number of distinct substitution
                                   pairs (2-5) together cover most hunks.
  likely_dialect_variant          many distinct, low-frequency substitution
                                   pairs (no concentration) but score >= 0.85.
  likely_distinct_translation     same "no concentration" shape but
                                   score < 0.85.
  unclassified                    none of the above signatures fit cleanly.

Calibrated against the PKF-vs-DBT 82-language pilot (see
diagnose_pkf_dbt_diff.py). Applying the same thresholds to helloAO-involving
comparisons is a starting assumption, not independently re-validated —
worth spot-checking real results before trusting them at the same
confidence level.
"""
import difflib
from collections import Counter

SELF_DUP_MIN_LEN = 30
SELF_DUP_MAX_HUNKS = 5
ORTHO_MAX_PAIRS = 5
DIALECT_SCORE_FLOOR = 0.85

# Pairs already manually confirmed (via linguistic cross-check, not a
# substitution test alone) to be genuine phonemic distinctions rather than
# encoding bugs — see CLAUDE.local.md. Checked here so re-encountering the
# exact same pair doesn't need re-litigating, regardless of which two
# sources are being compared.
KNOWN_PHONEMIC_PAIRS = {frozenset({"ʉ", "u"})}


def diff_opcodes(a_chars: str, b_chars: str):
    sm = difflib.SequenceMatcher(a=a_chars, b=b_chars, autojunk=False)
    return [op for op in sm.get_opcodes() if op[0] != "equal"]


def pair_counter(a_chars: str, b_chars: str, opcodes) -> Counter:
    return Counter((a_chars[i1:i2], b_chars[j1:j2]) for _, i1, i2, j1, j2 in opcodes)


def distinct_pairs_for_80pct(pairs: Counter, total_hunks: int) -> int:
    if not total_hunks:
        return 0
    covered = 0
    for i, (_, count) in enumerate(pairs.most_common(), start=1):
        covered += count
        if covered / total_hunks >= 0.8:
            return i
    return len(pairs)


def substitution_test(a_chars: str, b_chars: str, pair: tuple, compare_fn) -> float:
    """Force the dominant (a_fragment, b_fragment) pair to be treated as
    equivalent by rewriting side A's occurrences of a_fragment to
    b_fragment, then re-score. A near-1.0 result means that one pair fully
    explains the gap; anything short of that means it doesn't."""
    a_frag, b_frag = pair
    if not a_frag and not b_frag:
        return compare_fn(a_chars, b_chars)
    forced = a_chars.replace(a_frag, b_frag) if a_frag else a_chars
    return compare_fn(forced, b_chars)


def find_self_duplication(a_chars: str, b_chars: str, opcodes) -> dict | None:
    """A large hunk whose content also reappears elsewhere in its OWN
    source (excluding the hunk's own span). Only meaningful when the whole
    diff is simple (few hunks) — see SELF_DUP_MAX_HUNKS."""
    if len(opcodes) > SELF_DUP_MAX_HUNKS:
        return None
    for tag, i1, i2, j1, j2 in opcodes:
        if tag in ("delete", "replace") and (i2 - i1) >= SELF_DUP_MIN_LEN:
            chunk = a_chars[i1:i2]
            rest = a_chars[:i1] + a_chars[i2:]
            if chunk in rest:
                return {"side": "a", "chunk": chunk[:60]}
        if tag in ("insert", "replace") and (j2 - j1) >= SELF_DUP_MIN_LEN:
            chunk = b_chars[j1:j2]
            rest = b_chars[:j1] + b_chars[j2:]
            if chunk in rest:
                return {"side": "b", "chunk": chunk[:60]}
    return None


def sample_hunks(a_chars: str, b_chars: str, opcodes, n: int = 3) -> list:
    ranked = sorted(opcodes, key=lambda op: max(op[2] - op[1], op[4] - op[3]), reverse=True)
    out = []
    for tag, i1, i2, j1, j2 in ranked[:n]:
        out.append({
            "tag": tag,
            "a_fragment": a_chars[i1:i2][:40],
            "b_fragment": b_chars[j1:j2][:40],
        })
    return out


def classify(score: float, a_chars: str, b_chars: str, compare_fn) -> dict:
    opcodes = diff_opcodes(a_chars, b_chars)
    n_hunks = len(opcodes)
    pairs = pair_counter(a_chars, b_chars, opcodes)
    top_pair, top_count = (pairs.most_common(1)[0] if pairs else ((None, None), 0))
    dominant_fraction = (top_count / n_hunks) if n_hunks else 0.0
    n_pairs_80 = distinct_pairs_for_80pct(pairs, n_hunks)

    result = {
        "best_score": round(score, 4),
        "diff_hunks": n_hunks,
        "dominant_pair_fraction": round(dominant_fraction, 3),
        "distinct_pairs_for_80pct": n_pairs_80,
        "sample_diffs": sample_hunks(a_chars, b_chars, opcodes),
    }

    dup = find_self_duplication(a_chars, b_chars, opcodes)
    if dup:
        result["category"] = "likely_source_duplication"
        result["self_duplication"] = dup
        return result

    if dominant_fraction >= 0.8 and n_hunks >= 3:
        test_score = substitution_test(a_chars, b_chars, top_pair, compare_fn)
        result["substitution_test_pair"] = list(top_pair)
        result["substitution_test_score"] = round(test_score, 4)
        if frozenset(top_pair) in KNOWN_PHONEMIC_PAIRS:
            result["category"] = "likely_phonemic_distinction"
            result["note"] = "pair matches an already-confirmed genuine distinction, not re-litigated"
        elif test_score >= 0.999:
            result["category"] = "single_pair_dominant_ambiguous"
        else:
            result["category"] = "likely_phonemic_distinction"
        return result

    if n_pairs_80 <= ORTHO_MAX_PAIRS and n_pairs_80 > 0:
        result["category"] = "likely_orthography_convention"
    elif score >= DIALECT_SCORE_FLOOR:
        result["category"] = "likely_dialect_variant"
    elif n_hunks > 0:
        result["category"] = "likely_distinct_translation"
    else:
        result["category"] = "unclassified"

    return result
