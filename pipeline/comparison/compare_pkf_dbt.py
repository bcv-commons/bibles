#!/usr/bin/env python3
"""Compare PKF text against every locally-sampled DBT version for a
language, to determine whether PKF's version is a duplicate of a known DBT
version or a genuinely distinct additional translation.

Whole-chapter, CHARACTER-level comparison (not word- or verse-aligned).
Two confounds ruled out a naive word-tokenized approach during the 3-language
pilot (ind/poe/vmy) that this design fixes:

1. DBT's raw per-verse samples don't reliably map line position -> verse
   number (poetic sub-lines can get separate verse_start fragments that
   don't merge — REV 15 canonically has 8 verses but a sampled file can
   have 15 lines) — so verse alignment is unreliable. Whole-chapter
   comparison sidesteps this.
2. Word-level tokenization is unstable across independent digitizations:
   (a) glottal-stop apostrophes (phonemically meaningful in many of these
   languages, e.g. Mazatec) are encoded with different Unicode characters
   per source (plain ASCII U+0027 vs. saltillo U+A78C vs. curly-quote
   variants), splitting/not-splitting the same word depending on source;
   (b) word-SPACING conventions differ between digitizations of
   morphologically complex languages independent of actual content —
   caught concretely: `vmy` DBT versions VMYTBL and VMYWBT looked only
   64% similar under word-tokenization but are 100% IDENTICAL once
   apostrophes are canonicalized; `poe`'s genuine-non-match case jumped
   0.31 -> 0.64 -> 0.69 as apostrophe, then spacing (via char-level
   comparison), then diacritics were normalized away — each was hiding
   real similarity, revealing the true remaining (much smaller) gap.
   Comparing raw character streams (whitespace/punctuation stripped
   entirely, diacritics stripped, apostrophes canonicalized) is robust to
   both — a word can be spelled/spaced differently but the same letter
   sequence still lines up.

No PKF text is retained or published — this script's only durable output is
the comparison verdict per (iso, DBT version), never the underlying text.

Usage:
    python3 scripts/compare_pkf_dbt.py <iso> <pkf_usfm_path> [--book REV] [--chapter 15]

Example (after fetching + decoding a .pkf with tools/pkf-decode/):
    python3 scripts/compare_pkf_dbt.py ind /tmp/pkf_pilot/out/ind/67-REV.usfm
"""
import difflib
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import TEXT_DIR  # noqa: E402

SAMPLE_DIR = TEXT_DIR / "BB" / "nt"

# Cross-references and footnotes carry no translation content of their own
# (verse/chapter citations, editorial notes) — drop them entirely rather
# than just stripping the tag, or their citation text would pollute the
# comparison. \rq...\rq* (quoted-text source reference, e.g. "Buk Song
# 111:2, Amos 3:13") found via wrs — same category as \x/\f, just a
# different USFM marker; caused the same "extra content only on the PKF
# side" symptom as the earlier \s-heading bug.
_DROP_BLOCK_RE = re.compile(r"\\x\b.*?\\x\*|\\f\b.*?\\f\*|\\rq\b.*?\\rq\*", re.DOTALL)
_TAG_RE = re.compile(r"\\[A-Za-z0-9]+\*?")

# See module docstring point 2(a) — canonicalize known Unicode homoglyph
# pairs (different code points used for the same phonemically-meaningful
# letter, per source) before comparing. Each confirmed by inspecting a real
# diff where it was the ENTIRE difference between two otherwise-identical
# texts — not guessed:
#   apostrophe/glottal-stop lookalikes (curly quotes, saltillo U+A78C, etc.)
#     — found via vmy (Mazatec): DBT uses ASCII ', PKF uses saltillo ꞌ.
#   'ↄ' (U+2184 LATIN SMALL LETTER REVERSED C) vs 'ɔ' (U+0254 LATIN SMALL
#   LETTER OPEN O, the standard IPA/African-orthography character)
#     — found via adj (Adjukru): PKF uses U+2184, DBT uses U+0254 for the
#     same "open o" letter.
#   'ß' (U+00DF LATIN SMALL LETTER SHARP S) as a glottal-stop stand-in
#     — found via tpz: DBT's digitization used the German eszett as a
#     practical substitute character for the glottal stop where PKF uses
#     the standard saltillo. Verified by substitution test (ß -> ' in
#     DBT's raw text) before adding: achieves an exact 1.0 match, not
#     guessed. NOTE: scoped narrowly on purpose — ß is a real German
#     letter, so this mapping isn't universally safe, but Bible text
#     containing genuine German loanwords with ß is rare enough that the
#     risk of a false merge is low relative to the benefit here.
#   'ǥ' (U+01E5 LATIN SMALL LETTER G WITH STROKE) -> 'g'
#     — found via mbb: PKF uses the precomposed ǥ; DBT's raw text spells
#     the same letter as a decomposed sequence, plain "g" + U+0335
#     COMBINING SHORT STROKE OVERLAY. NFKD does NOT decompose the
#     precomposed ǥ (confirmed: it has no defined canonical
#     decomposition), so the two forms don't converge on their own even
#     though the combining-mark-stripping step already reduces DBT's
#     decomposed form to plain "g". Mapping ǥ -> g directly makes both
#     sides consistent with what already happens to DBT's spelling.
#     Verified by substitution test before adding (exact 1.0 match).
#   'ᵾ' (U+1D7E LATIN SMALL CAPITAL LETTER U WITH STROKE) vs 'ʉ' (U+0289
#   LATIN SMALL LETTER U BAR) — found via med: two different Unicode
#     characters both used as "barred u" across these orthographies.
#     NOTE: `bsn`'s `ʉ` vs plain `u` case looks superficially similar but
#     is NOT a homoglyph — confirmed those are genuinely different
#     phonemes in Tucanoan languages, so NOT normalized. This pair (ᵾ/ʉ)
#     is different: both are barred-u variants, verified by substitution
#     test to be a real match, not guessed.
#   U+F21D (Private Use Area — no standard meaning; a leftover custom font
#   glyph code from DBT's source digitization) used as a glottal-stop stand-in
#     — found via coe (Koreguaje): DBT's raw text uses this PUA codepoint
#     wherever PKF uses a normal apostrophe. Invisible to both the
#     char-level (silently dropped, not translated — neither a letter nor
#     the canonical apostrophe) and word-level (ICU treats it as a
#     non-letter, so it splits one word into several) methods. Verified by
#     substitution test: coe's char score rose 0.856 -> 0.907 (a real,
#     partial fix; coe also has other genuine orthography differences,
#     unaffected). Also fully explains cap's diff (3 occurrences,
#     previously flagged "single_pair_dominant_ambiguous" by
#     diagnose_pkf_dbt_diff.py) and iri's small residual gap (1
#     occurrence). Scoped safely: a Private Use Area codepoint has no
#     legitimate meaning outside a font's custom glyph mapping, so there's
#     no risk of a false merge the way ß (a real German letter) had.
_HOMOGLYPH_TRANSLATION = str.maketrans({
    **{c: "'" for c in "’‘ʼʻꞌˈ`ß"},
    "ǥ": "g",
    "ↄ": "ɔ",  # ↄ -> ɔ
    "ᵾ": "ʉ",
    "": "'",  # DBT PUA glottal-stop stand-in — see comment above
})

# Keep letters and the canonical apostrophe (phonemically meaningful in
# several of these languages); drop everything else — punctuation, digits,
# and crucially whitespace — so word-spacing convention differences (point
# 2(b)) can't affect the comparison.
_KEEP_RE = re.compile(r"[^\W\d_]|'", re.UNICODE)


def normalize_chars(text: str) -> str:
    text = _DROP_BLOCK_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    # Lowercase BEFORE translating — _HOMOGLYPH_TRANSLATION's keys are all
    # lowercase, and some sources capitalize these letters at sentence
    # start (e.g. capital saltillo U+A78B vs. the lowercase U+A78C in the
    # table) — translating first then lowercasing last would let the
    # capital variant slip through untranslated, then get silently
    # lowercased into the *target* character, masking the bug entirely
    # (found via `viv`: raw capital 'Ꞌ' U+A78B wasn't in the table, so it
    # passed through untouched and only became indistinguishable from a
    # correctly-translated U+A78C after the final .lower() call).
    text = text.lower()
    text = text.translate(_HOMOGLYPH_TRANSLATION)
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return "".join(_KEEP_RE.findall(text))


_SECTION_HEADING_RE = re.compile(r"\\s\d?\b")


def extract_pkf_chapter(usfm_path: Path, chapter: int) -> str:
    """Verse content only — PKF's USFM includes \\s/\\s1/\\s2 section
    headings inline in the chapter (e.g. "Seven angels bring the final
    judgment"); DBT's per-verse API samples never do, since they're built
    verse-by-verse with no heading concept. Without skipping headings, every
    genuine duplicate showed a spurious ~1-2% gap consisting of exactly one
    diff hunk: the heading text, confirmed by direct inspection (e.g. `knj`'s
    "extra" chunk matched its \\s1 line character-for-character)."""
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
    return normalize_chars("\n".join(buf))


def dbt_samples(iso: str, book: str, chapter: int, sample_dir: Path = SAMPLE_DIR) -> dict[str, str]:
    """distinct_id -> normalized character stream, for every locally-sampled
    DBT fileset for this (iso, book, chapter). sample_dir defaults to the NT
    tree; pass TEXT_DIR / "BB" / "ot" for an OT probe (e.g. PSA 117)."""
    probe = f"{book}_{chapter:03d}_"
    out: dict[str, str] = {}
    base = sample_dir / iso
    if not base.is_dir():
        return out
    for f in base.rglob(f"{probe}*.txt"):
        distinct_id = f.relative_to(base).parts[0]
        out[distinct_id] = out.get(distinct_id, "") + normalize_chars(f.read_text(encoding="utf-8"))
    return out


def compare(a: str, b: str) -> float:
    """Similarity ratio in [0, 1] — 1.0 means identical (after normalization)."""
    return difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio()


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit("usage: compare_pkf_dbt.py <iso> <pkf_usfm_path> [--book REV] [--chapter 15]")
    iso, usfm_path = args[0], Path(args[1])
    book = "REV"
    chapter = 15
    if "--book" in args:
        book = args[args.index("--book") + 1]
    if "--chapter" in args:
        chapter = int(args[args.index("--chapter") + 1])

    pkf_chars = extract_pkf_chapter(usfm_path, chapter)
    print(f"[compare] {iso}: PKF {book} {chapter} -> {len(pkf_chars)} chars")
    if not pkf_chars:
        print(f"[compare] {iso}: no PKF text found for {book} {chapter} in {usfm_path}")
        return

    dbt = dbt_samples(iso, book, chapter)
    if not dbt:
        print(f"[compare] {iso}: no local DBT samples for {book} {chapter} — nothing to compare against")
        return

    print(f"[compare] {iso}: {len(dbt)} DBT version(s) sampled locally")
    best_id, best_score = None, 0.0
    for distinct_id, dbt_chars in sorted(dbt.items()):
        score = compare(pkf_chars, dbt_chars)
        print(f"  vs {distinct_id} ({len(dbt_chars)} chars): similarity={score:.3f}")
        if score > best_score:
            best_id, best_score = distinct_id, score

    print(f"[compare] {iso}: best match = {best_id} (similarity={best_score:.3f})")


if __name__ == "__main__":
    main()
