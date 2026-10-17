"""Content fingerprint v1: for diagnosis only. Two texts with the same content fingerprint
differ at most in spacing, word joins, punctuation, case, apostrophe form or Unicode
normalization. The text fingerprint (bcv_tokenize.fingerprints) is what identifies an
edition's text. This one tells you *how* two texts differ when their text fingerprints
don't match. Mirrors ../js/content_fingerprint.mjs; both give the same result for every
verse we publish (see the README).

Per verse (`content(text)`):
1. NFC.
2. Lowercase (Unicode default lowercase: str.lower(), JS toLowerCase()), then final sigma
   ς -> σ. Not str.casefold(): JavaScript has no equivalent, and both languages must agree.
   Lowercasing comes before step 3, so capital forms (Ꞌ) are caught too.
3. Apostrophe-like characters (APOSTROPHES) -> ʼ (U+02BC, a letter), so a glottal stop or
   elision counts as content whatever character the digitization used.
4. NFC again; keep only letters and marks (Unicode categories L*, M*). Digits, punctuation,
   symbols and whitespace are dropped.

Then the same shape as the text fingerprint: per verse the line "{verse}:{content}" (a
verse with no content left out), chapter = SHA-256 of its lines joined by \\n, book =
SHA-256 of "{chapter}:{chapter fp}" lines.

    content(text) -> str
    content_fingerprints({(chapter, verse): text}) -> (book_hex, {chapter: chapter_hex})
"""
import hashlib
import unicodedata

CONTENT_FP_VERSION = 1

# ' ’ ʼ ʻ ꞌ ´ ` ′ ＇ (U+0027 2019 02BC 02BB A78C 00B4 0060 2032 FF07). Not ‘ (U+2018): almost
# always an opening quote.
APOSTROPHES = "'’ʼʻꞌ´`′＇"
_TO_ONE = str.maketrans({c: "ʼ" for c in APOSTROPHES})


def content(text: str) -> str:
    s = unicodedata.normalize("NFC", text).lower().replace("ς", "σ").translate(_TO_ONE)
    return "".join(c for c in unicodedata.normalize("NFC", s) if unicodedata.category(c)[0] in "LM")


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def content_fingerprints(verses: dict[tuple[int, int], str]) -> tuple[str, dict[int, str]]:
    lines: dict[int, list[str]] = {}
    for (c, v) in sorted(verses):
        t = content(verses[(c, v)])
        if t:
            lines.setdefault(c, []).append(f"{v}:{t}")
    chapters = {c: _sha("\n".join(ls)) for c, ls in lines.items()}
    return _sha("\n".join(f"{c}:{chapters[c]}" for c in sorted(chapters))), chapters
