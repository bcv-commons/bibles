#!/usr/bin/env python3
"""Word-level companion to compare_pkf_dbt.py — a second, independent
comparison signal using robust Unicode word segmentation (ICU) instead of
raw character streams.

compare_pkf_dbt.py (unchanged here, kept exactly as validated across the
8-bug pilot) concatenates all characters with no word boundaries at all,
which is what made it robust to word-spacing convention differences between
independent digitizations. This script deliberately tests the opposite
design: preserve single-space-delimited words, using ICU's word-break
algorithm (UAX #29) rather than a hand-rolled `\\W`-splitting regex to decide
where word boundaries actually are — including known-hard cases like
apostrophe-internal words ("tsa'be" must stay one word, not split on the
apostrophe) across many scripts, which is exactly the class of bug that
made the pilot's first naive word-tokenized attempt give a wrong verdict
for `vmy` (see compare_pkf_dbt.py's module docstring).

Only meant to run on languages compare_pkf_dbt.py did NOT already score
1.0 on — nothing to learn re-checking an exact match with a second method.

Reuses (imports, does not modify) compare_pkf_dbt.py's already-validated
building blocks: _DROP_BLOCK_RE/_TAG_RE (footnote/xref/reference-marker
stripping), _HOMOGLYPH_TRANSLATION (confirmed same-phoneme Unicode variant
fixes — 8 of them, each verified by a substitution test before being
added), _SECTION_HEADING_RE (heading-skip), SAMPLE_DIR. Only the final
tokenization step differs: instead of stripping all whitespace/punctuation
into one continuous character stream, words are kept whole and re-joined
with a single space, filtered to ICU's LETTER/KANA/IDEOGRAPHIC word-break
categories ("real sounding word letters or pictograms" — numbers and
punctuation/whitespace are dropped, same stance the character-level method
already takes on digits).

Requires PyICU (`pip install pyicu`; needs icu4c + pkg-config on the
system — on macOS: `brew install icu4c pkg-config`, then
`PKG_CONFIG_PATH="$(brew --prefix icu4c)/lib/pkgconfig" pip install pyicu`).

Usage:
    python3 scripts/compare_pkf_dbt_words.py <iso> <pkf_usfm_path> [--book REV] [--chapter 15]
"""
import difflib
import sys
import unicodedata
from pathlib import Path

try:
    import icu
except ImportError:
    sys.exit(
        "PyICU not installed. Run: PKG_CONFIG_PATH=\"$(brew --prefix icu4c)/lib/pkgconfig\" "
        ".venv/bin/pip install pyicu"
    )

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_pkf_dbt import (  # noqa: E402
    _DROP_BLOCK_RE,
    _HOMOGLYPH_TRANSLATION,
    _SECTION_HEADING_RE,
    _TAG_RE,
    SAMPLE_DIR,
)

# UAX #29 word-break status ranges (ICU's UWordBreak enum):
#   0        = none (punctuation, whitespace, symbols — not word content)
#   100-199  = number
#   200-299  = letter
#   300-399  = kana
#   400-499  = ideographic (pictograms)
# Keep letter/kana/ideographic; drop numbers (matches the character-level
# method's existing digit-stripping stance) and punctuation/whitespace.
_WORD_STATUS_MIN, _WORD_STATUS_MAX = 200, 500
_WORD_BREAK_ITER = icu.BreakIterator.createWordInstance(icu.Locale("root"))


def normalize_words(text: str) -> str:
    """Single-space-joined words, boundaries decided by ICU's UAX #29 word
    segmentation — not a hand-rolled regex — per the explicit ask to trust
    a real Unicode text-segmentation library over a guess. Reuses the
    already-validated drop/tag/homoglyph/diacritic steps unchanged."""
    text = _DROP_BLOCK_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    # Lowercase before translating — same order-of-operations reasoning as
    # compare_pkf_dbt.py (a `viv`-class bug otherwise: capitalized variants
    # of homoglyph characters would slip through the translation table).
    text = text.lower()
    text = text.translate(_HOMOGLYPH_TRANSLATION)
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))

    _WORD_BREAK_ITER.setText(text)
    words = []
    start = _WORD_BREAK_ITER.first()
    for end in _WORD_BREAK_ITER:
        status = _WORD_BREAK_ITER.getRuleStatus()
        if _WORD_STATUS_MIN <= status < _WORD_STATUS_MAX:
            words.append(text[start:end])
        start = end
    return " ".join(words)


def extract_pkf_chapter_words(usfm_path: Path, chapter: int) -> str:
    """Same heading-skip logic as compare_pkf_dbt.extract_pkf_chapter,
    duplicated rather than imported — that function's final step
    (normalize_chars) destroys word boundaries by design, so this needs
    the raw chapter buffer instead, run through normalize_words() here."""
    lines = usfm_path.read_text(encoding="utf-8").splitlines()
    in_chapter = False
    skip_heading = False
    buf = []
    for line in lines:
        if line.startswith("\\c "):
            in_chapter = line.strip() == f"\\c {chapter}"
            skip_heading = False
            continue
        if not in_chapter:
            continue
        if _SECTION_HEADING_RE.match(line):
            skip_heading = True
            continue
        if line.startswith("\\"):
            skip_heading = False
        if skip_heading:
            continue
        if in_chapter:
            buf.append(line)
    return normalize_words("\n".join(buf))


def dbt_samples_words(iso: str, book: str, chapter: int) -> dict[str, str]:
    """distinct_id -> single-space-joined normalized words, for every
    locally-sampled DBT fileset for this (iso, book, chapter)."""
    probe = f"{book}_{chapter:03d}_"
    out: dict[str, str] = {}
    base = SAMPLE_DIR / iso
    if not base.is_dir():
        return out
    for f in base.rglob(f"{probe}*.txt"):
        distinct_id = f.relative_to(base).parts[0]
        piece = normalize_words(f.read_text(encoding="utf-8"))
        out[distinct_id] = (out.get(distinct_id, "") + " " + piece).strip()
    return out


def compare_words(a: str, b: str) -> float:
    """Word-level similarity ratio in [0, 1] — SequenceMatcher over the
    WORD list (not the joined string), so one differing word counts as one
    diff unit instead of splintering into per-character diffs."""
    a_words = a.split(" ") if a else []
    b_words = b.split(" ") if b else []
    return difflib.SequenceMatcher(a=a_words, b=b_words, autojunk=False).ratio()


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit("usage: compare_pkf_dbt_words.py <iso> <pkf_usfm_path> [--book REV] [--chapter 15]")
    iso, usfm_path = args[0], Path(args[1])
    book = "REV"
    chapter = 15
    if "--book" in args:
        book = args[args.index("--book") + 1]
    if "--chapter" in args:
        chapter = int(args[args.index("--chapter") + 1])

    pkf_words = extract_pkf_chapter_words(Path(usfm_path), chapter)
    n_pkf = len(pkf_words.split()) if pkf_words else 0
    print(f"[compare-words] {iso}: PKF {book} {chapter} -> {n_pkf} words")
    if not pkf_words:
        print(f"[compare-words] {iso}: no PKF text found for {book} {chapter} in {usfm_path}")
        return

    dbt = dbt_samples_words(iso, book, chapter)
    if not dbt:
        print(f"[compare-words] {iso}: no local DBT samples for {book} {chapter} — nothing to compare against")
        return

    print(f"[compare-words] {iso}: {len(dbt)} DBT version(s) sampled locally")
    best_id, best_score = None, 0.0
    for distinct_id, dbt_words in sorted(dbt.items()):
        score = compare_words(pkf_words, dbt_words)
        n_dbt = len(dbt_words.split()) if dbt_words else 0
        print(f"  vs {distinct_id} ({n_dbt} words): similarity={score:.3f}")
        if score > best_score:
            best_id, best_score = distinct_id, score

    print(f"[compare-words] {iso}: best match = {best_id} (similarity={best_score:.3f})")


if __name__ == "__main__":
    main()
