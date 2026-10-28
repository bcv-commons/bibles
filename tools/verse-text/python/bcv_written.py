"""Written tokens: the tokenizer's tokens with the marks it drops put back (reference implementation, Python, stdlib only).

The tokenizer (`bcv_tokenize.tokenize`) drops every combining mark after NFC, so that Arabic harakat and Hebrew points
don't split words. Where a letter has no precomposed form, the mark is lost: tone on ø, æ, ɨ (Kuni mø̀ndæ -> møndæ),
the rising tone U+1DC4, Yoruba's dot-below-plus-tone, and the like. `tokenize_written` returns the same tokens at the
same positions, each as written in the NFC text: its marks kept. Positions, fingerprints and published alignments
don't change; a client that needs the marks reads the written form at the same position.

    tokenize_written(text) -> [token as written, ...]     len == len(tokenize(text)), always
    strip_marks(written[i]) == tokenize(text)[i]          always (the invariant the conformance test checks)

What is put back: combining marks (non-zero combining class) that follow a token's letters, up to the next letter
kept by the tokenizer. Variation selectors stay dropped (a glyph choice, no linguistic content). A mark with no letter before it
in the same run belongs to no token, as in the tokenizer."""
import unicodedata

from bcv_tokenize import tokenize, strip_marks, _MYANMAR_KEEP, _is_variation_selector

WRITTEN_VERSION = 1


def _kept(c: str) -> bool:
    return (not unicodedata.combining(c) or ord(c) in _MYANMAR_KEEP) and not _is_variation_selector(ord(c))


def tokenize_written(text: str) -> list[str]:
    nfc = unicodedata.normalize("NFC", text)
    stripped, at = [], []                       # the tokenizer's text and, per char, its index in the NFC text
    for i, c in enumerate(nfc):
        if _kept(c):
            stripped.append(c)
            at.append(i)
    s = "".join(stripped)
    at.append(len(nfc))
    out, cur = [], 0
    for t in tokenize(text):
        k = s.index(t, cur)                     # the tokens are substrings of its text, in order
        cur = k + len(t)
        a, b = at[k], at[cur - 1] + 1
        while b < at[cur] and unicodedata.combining(nfc[b]):   # the marks after the token's last letter
            b += 1
        out.append("".join(c for c in nfc[a:b] if not _is_variation_selector(ord(c))))
    return out


if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        print(" ".join(tokenize_written(line)))
