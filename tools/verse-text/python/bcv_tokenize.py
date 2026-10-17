"""bcv tokenizer v2 + text fingerprint v1 — reference implementation (Python, standard library only).

Handed over by bcv-commons/lexeme-aligner to bcv-commons/bibles on 2026-10-17, CC0 1.0. Copied VERBATIM from lexeme-aligner
(pipeline/lexeme_aligner/usj_source.py: tokenize, strip_marks and their helpers; text_fingerprint.py: the fingerprint), so its
output is the token sequence every published compact-alignments position refers to.

Verse text is NOT part of this file: it comes from bibles' own extraction rule (tools/verse-text, extract_usj / extract_sofria).
    tokenize(text) -> [token, ...]                         tokenizer v2
    fingerprints({(chapter, verse): text}) -> (book_hex, {chapter: chapter_hex})     text fingerprint v1, full SHA-256
    file_hash(book_hex) -> the 8 hex used in file names
"""
import hashlib
import re
import unicodedata

TOKENIZER_VERSION = 2
TEXT_FP_VERSION = 1
NAME_HEX = 8

_MYANMAR_KEEP = {4153, 4154}

_MYA_ASAT = 4154

_MYA_EVOWEL = 4145

_MYA_VIRAMA = 4153


def _is_variation_selector(o: int) -> bool:
    """Variation selectors (U+FE00-FE0F, U+E0100-E01EF) choose a GLYPH form and carry no linguistic
    content, but their combining class is 0 so `strip_marks` kept them and `tokenize` kept them (category
    Mn), splitting one word into two vocabulary entries. Measured on kht (Tai Khamti): 93.3% of its stored
    surfaces and 85.6% of its live tokens carried one, and the SAME base letter appeared as both 'က' and
    'က︀' — so a gloss prior never matched the text and its gloss coverage sat at 4.9% while eflomal held
    84.9%. Every other Myanmar-script language here has none (rki 0%, pll 0%), which is why they were
    unaffected (gloss 69.2% / 39.4%)."""
    return 0xFE00 <= o <= 0xFE0F or 0xE0100 <= o <= 0xE01EF


def strip_marks(text: str) -> str:
    """NFC, then drop combining marks (non-zero combining class) — Arabic harakat, Hebrew points, etc.
    Otherwise the word regex shatters a diacritized word at every mark (فِي → ف, ي). Precomposed Latin
    accents (é, å) survive NFC as single code points, so French/Swedish are unaffected.

    Myanmar virama/asat are EXEMPT. They share the virama combining class (9) with the Indic marks this
    is meant to drop, but they are not optional diacritics: the virama stacks a consonant and the asat
    marks a syllable-final one, so dropping them destroys the syllable structure `_mya_syllables` reads
    (အနွယ် 'lineage' → အနွယ, whose final ယ then looks like the start of a third syllable). Affects only
    text containing those two code points, i.e. Myanmar-script languages."""
    return "".join(c for c in unicodedata.normalize("NFC", text)
                   if (not unicodedata.combining(c) or ord(c) in _MYANMAR_KEEP)
                   and not _is_variation_selector(ord(c)))


def tokenize(text: str) -> list[str]:
    """Generic unicode word tokens, order preserved (normalization happens later). A token is a run of
    letters + their combining marks (a grapheme cluster), so Indic/diacritized scripts tokenize by WORD,
    not shatter at every vowel sign — दाऊद stays one token, not द+ऊद (the old `[^\\W\\d_]+` regex broke at
    spacing marks like the Mc matra ा). `strip_marks` still drops nonspacing marks (Arabic harakat, Hebrew
    points, Indic viramas) for match-normalisation; spacing marks stay inside the cluster. Latin/Cyrillic
    unaffected (no combining marks after NFC)."""
    toks: list[str] = []
    cur: list[str] = []
    for ch in strip_marks(text):
        if unicodedata.category(ch)[0] in ("L", "M"):        # letter or combining mark → part of the word
            cur.append(ch)
        elif cur:
            toks.extend(_split_unspaced("".join(cur)))
            cur = []
    if cur:
        toks.extend(_split_unspaced("".join(cur)))
    return toks


def _cjk_class(ch: str) -> str | None:
    """Han / Hiragana / Katakana, else None. These scripts write NO space between words, so whitespace
    tokenization silently returns one token per whole verse (measured: a 22-char Chinese verse → a single
    20-char token, i.e. the aligner saw one target 'word' per verse and could never align it)."""
    o = ord(ch)
    if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0xF900 <= o <= 0xFAFF:
        return "han"
    if 0x3040 <= o <= 0x309F:
        return "hira"
    if 0x30A0 <= o <= 0x30FF:
        return "kata"
    return None


def _is_mya_consonant(o: int) -> bool:
    """Myanmar consonant/independent-vowel letters, including the Extended-A/B blocks the minority
    languages here actually use (Shan, Khamti, Palaung, Rakhine — not just Burmese)."""
    return (0x1000 <= o <= 0x102A or o == 0x103F or 0x1050 <= o <= 0x1055
            or 0x105A <= o <= 0x105D or o == 0x1061 or 0x1065 <= o <= 0x1066
            or 0x106E <= o <= 0x1070 or 0x1075 <= o <= 0x1081 or o == 0x108E
            or 0xA9E0 <= o <= 0xA9E4 or 0xA9E7 <= o <= 0xA9EF or 0xA9FA <= o <= 0xA9FE
            or 0xAA60 <= o <= 0xAA6F or 0xAA71 <= o <= 0xAA76 or o == 0xAA7A
            or 0xAA7E <= o <= 0xAA7F)


def _mya_syllables(tok: str) -> list[str]:
    """Rule-based Myanmar syllable segmentation. Myanmar writes no space between words, so whitespace
    tokenization returned whole phrases (measured: kht averaged 23.2 characters per 'word', rki 8.0).

    A syllable starts at a consonant, or at U+1031 (the vowel sign written BEFORE its consonant but
    pronounced after). It does NOT start when the consonant is stacked under a virama, nor immediately
    after U+1031, nor after an asat — an asat-killed consonant closes the current syllable rather than
    opening the next. Vowel signs, medials and tone marks simply attach to the syllable in progress.

    Syllable-level is the right grain here for the same reason character-level is for Han: these are
    largely monosyllabic Tibeto-Burman/Tai languages, so a syllable is about a morpheme, and eflomal
    recovers longer words as many-to-one alignments. Verified: အာဗြဟံ (Abraham) → အာ/ဗြ/ဟံ, ဒါဝိဒ
    (David) → ဒါ/ဝိ/ဒ."""
    out: list[str] = []
    cur: list[str] = []
    for i, ch in enumerate(tok):
        o = ord(ch)
        prev = ord(tok[i - 1]) if i else 0
        if (_is_mya_consonant(o) or o == _MYA_EVOWEL) and cur \
                and prev not in (_MYA_VIRAMA, _MYA_EVOWEL, _MYA_ASAT):
            out.append("".join(cur))
            cur = []
        cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def _split_unspaced(tok: str) -> list[str]:
    """Segment a whitespace-delimited run that belongs to a space-free script. Dep-free and
    language-independent by construction — no segmenter model, no download, so it works on any such
    language the moment it has a Bible (the same constraint the rest of the tail-facing pipeline holds to).

    Rules: each Han character becomes its own token (a Han char is ~a morpheme, and this is the standard
    model-free baseline — eflomal recovers multi-character words as many-to-one alignments); runs of
    hiragana, of katakana, and of anything else each stay whole, so Japanese splits at script boundaries
    (神の子イエス → 神 / の / 子 / イエス — content kanji, particle, content kanji, katakana name).

    Myanmar-script runs are segmented into syllables instead (see `_mya_syllables`).

    STRICT NO-OP for anything else: returns [tok] unchanged, so Latin/Cyrillic/Indic/Arabic/Thai/Khmer/
    Lao/Tibetan tokenization is bit-identical to before and no other language is perturbed. (Thai, Khmer
    and Lao need nothing here — unlike the standard languages of those scripts, the minority languages
    written in them in this corpus separate words explicitly, with spaces or ZWSP: bzi 29 spaces per 193
    chars, kdt 46 ZWSP, lao 15 ZWSP. Tibetan already breaks at the tsheg.)"""
    if any(_is_mya_consonant(ord(c)) for c in tok):
        return _mya_syllables(tok)
    if not any(_cjk_class(c) for c in tok):
        return [tok]
    out: list[str] = []
    cur: list[str] = []
    cur_cls: str | None = None
    for ch in tok:
        cls = _cjk_class(ch)
        if cls == "han":                       # one token per Han character
            if cur:
                out.append("".join(cur))
                cur, cur_cls = [], None
            out.append(ch)
        elif cls != cur_cls and cur:           # script boundary → break
            out.append("".join(cur))
            cur, cur_cls = [ch], cls
        else:
            cur.append(ch)
            cur_cls = cls
    if cur:
        out.append("".join(cur))
    return out



# --- text fingerprint v1 ---
def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def verse_line(verse: int, text: str) -> str | None:
    """The hashed line for one verse, or None when the verse has no tokens (left out of the fingerprint)."""
    toks = tokenize(text)
    return f"{verse}:{' '.join(toks)}" if toks else None


def chapter_lines(verses: dict[tuple[int, int], str]) -> dict[int, list[str]]:
    """{(chapter, verse): text} -> {chapter: [verse lines in verse order]}; chapters with no tokens are left out."""
    out: dict[int, list[str]] = {}
    for (c, v) in sorted(verses):
        line = verse_line(v, verses[(c, v)])
        if line is not None:
            out.setdefault(c, []).append(line)
    return out


def fingerprints(verses: dict[tuple[int, int], str]) -> tuple[str, dict[int, str]]:
    """(book fingerprint, {chapter: chapter fingerprint}), full 64-hex digests."""
    chapters = {c: _sha("\n".join(lines)) for c, lines in chapter_lines(verses).items()}
    book = _sha("\n".join(f"{c}:{chapters[c]}" for c in sorted(chapters)))
    return book, chapters


def file_hash(book_fp: str) -> str:
    """The hash in a compact file name: <BOOK>_<file_hash>.json."""
    return book_fp[:NAME_HEX]

