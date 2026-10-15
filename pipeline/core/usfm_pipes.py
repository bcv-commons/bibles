"""Keep `|` that is text when parsing USFM with usfmtc.

In USFM, `|` separates a character marker's text from its attributes
(`\\w grace|lemma="charis"\\w*`, `\\fig ...|src="..."\\fig*`) and starts a milestone's
attributes (`\\qt-s |who="Jesus"\\*`). usfmtc treats every `|` that way, so a `|` used as
text loses everything after it: Sanskrit editions use it as a danda (sentence end), and
LSV uses it in its own text. Found 2026-10-12 (lexeme-aligner's report; checked: 42 of
44 text passages after a danda missing in SANORI 1CO, all 47 checked in LSV GEN).

protect() swaps a `|` for a placeholder before parsing, and restore() puts it back in
the parsed USJ's text, except where usfmtc's reading is kept:
- inside an attribute span, including nested character markers
  (\\w \\+tl word\\+tl*|lemma\\w*), and a milestone's attributes;
- inside notes (\\f, \\fe, \\x ... *) and \\rem lines: there a `|` is broken markup or a
  link target (OASD 1CH: "talata 14|1CH 15:14"; OML LUK: "|alt = src = ..."), not
  reading text.
"""
import re

PLACEHOLDER = "\ue000"  # private use: never in a source text
# \tag ... | ... \tag*  (also \+tag); a milestone's attributes: \tag-s |...\*
# Text without `|`, or a nested \+tag / \+tag*, up to the span's first `|`. Possessive
# (Python 3.11+): the earlier lazy form could read a nested marker's letters as text too, so
# a failed match backtracked exponentially (spabll MAT, 18,346 nested markers: minutes per
# book). Same matches: checked identical on 1,909 openbible books, 2026-10-15.
_NESTED = r"(?:[^\\|]++|\\\+[a-z]++\d*+\*?)*+"
_KEEP = re.compile(
    r"\\(\+?)([a-z]+\d*)\s" + _NESTED + r"\|[^\\]*?\\\1\2\*"     # \tag ... | ... \tag*
    r"|\\[a-z]+\d*-[se]\s*\|[^\\]*?\\\*"                          # \tag-s |...\*
    r"|\\(f|fe|x)\s.*?\\\3\*"                                     # notes
    r"|\\rem\b[^\n]*",                                              # remarks
    re.S)


def protect(usfm: str) -> str:
    if PLACEHOLDER in usfm:
        raise ValueError("source text contains the pipe placeholder U+E000")
    out, pos = [], 0
    for m in _KEEP.finditer(usfm):
        out.append(usfm[pos:m.start()].replace("|", PLACEHOLDER))
        out.append(m.group(0))
        pos = m.end()
    out.append(usfm[pos:].replace("|", PLACEHOLDER))
    return "".join(out)


def restore(node):
    """Put `|` back in every string of a parsed USJ tree (in place); returns the tree."""
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, str):
                node[k] = v.replace(PLACEHOLDER, "|")
            else:
                restore(v)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, str):
                node[i] = v.replace(PLACEHOLDER, "|")
            else:
                restore(v)
    return node
