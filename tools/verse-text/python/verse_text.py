"""Verse text from a book's USJ or from one Sofria chapter: the Python twin of
../js/rule.js, ../js/extract_usj.js and ../js/extract_sofria.js, giving identical
output (checked over every published openbible and audiobiblia chapter).

    extract_usj(usj)      -> {"<chapter>": [{"verse": v, "text": t}, ...], ...}
    extract_sofria(doc)   -> [{"verse": v, "text": t}, ...]

The rule (agreed with lexeme-aligner, 2026-10-12; see ../js/rule.js):

- Verse text is the text after a verse number, up to the next verse number,
  across paragraphs (poetry lines, table cells included).
- Not verse text: footnotes and cross-references; headings (\\s \\ms \\mr \\r \\sr \\sp
  \\cl \\qa \\mt \\d ...), up to a verse number inside the heading paragraph: text after
  that number is the verse's text; introductions; figures; remarks (\\rem, and
  Paratext's \\restore metadata); \\rq (quotation source); \\qac (acrostic letter); \\fm
  (footnote mark); \\vp and \\va/\\ca (published or alternative numbers).
- Word-level markup (\\w, \\wj, \\nd, ...) contributes its text, never attributes. Inside
  \\w, text from a `|` on is an attribute the source failed to parse (USX
  <char style="w">word|lemma</char>, DBT HLBMSS / YBBCAB): it is dropped.
- `| default="X"` (proskomma's rendering of a `|` in text, found in DBT's own Sofria,
  CARBSS) reads as `|X`, the source text.
- Legacy formatting codes are dropped: `|i` / `|sc` (italic, small caps on) where followed
  by an uppercase letter, a space or opening punctuation, and `|r` / `|d` (back to normal)
  where followed by a space, punctuation or the end ("|iEli, Eli ...?|r"; DBT CARBSS, COEWBT,
  FFMWBT, LAMABT, MDAWBT, MZWNVS, MYKWBT, KABCEB). A Sanskrit danda before a lowercase word
  ("cAvarA|isrAyel") matches neither.
- Any other `|` is text (a Sanskrit danda, LSV).
- A bridged verse 4-5 is one verse, under its first number (4).
- A verse number given twice: both texts, in document order, joined by one space.
- A verse with no text of its own is skipped.
- Whitespace: runs collapsed to one space, trimmed.

The patterns follow JavaScript's semantics on purpose (ASCII \\d, JS whitespace), so
both languages agree on every character.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

Verses = list[dict[str, str]]

HEADING = re.compile(r"(s[0-9]*|ms[0-9]*|mr|r|sr|sp|cl|qa|mt[0-9]*|mte[0-9]*|cd|d)")
SKIP_CHAR = {"rq", "qac", "fm", "vp", "va", "ca", "fig"}
SKIP_PARA = re.compile(r"(rem|restore|cp|ide|h[0-9]*|toc[0-9]*|toca[0-9]*|i[A-Za-z0-9_]+)")

# JavaScript's \s and String.prototype.trim() whitespace
_WS_CHARS = set("\t\n\v\f\r \u00a0\u1680\u2028\u2029\u202f\u205f\u3000\ufeff") | {chr(c) for c in range(0x2000, 0x200b)}
_WS = "\t\n\v\f\r    -     　﻿"
_WS_RUN = re.compile(f"[{_WS}]+")
_TRIM = re.compile(f"^[{_WS}]+|[{_WS}]+$")


def _trim(s: str) -> str:
    return _TRIM.sub("", s)


def first_number(v) -> str:
    return _trim(re.split("[-,‐-―]", _trim(str(v)))[0])


# closing quote optional: proskomma truncates long values at 255 bytes, quote included
PROSKOMMA_PIPE = re.compile(r'\| default="?([^"|]*)"?')


_OPEN_PUNCT = set("«“\"‘'<&¿¡([—-")
_LEGACY_OPEN = re.compile(r"\|(?:sc|i)(?=(.))", re.S)
_LEGACY_CLOSE = re.compile(r"\|[rd](?=(.)|$)", re.S)


def _drop_open(m) -> str:
    c = m.group(1)
    return "" if (c in _WS_CHARS or unicodedata.category(c) == "Lu" or c in _OPEN_PUNCT) else m.group(0)


def _drop_close(m) -> str:
    c = m.group(1)
    return "" if (c is None or c in _WS_CHARS or unicodedata.category(c).startswith("P")) else m.group(0)


def clean(s: str) -> str:
    s = PROSKOMMA_PIPE.sub(r"|\1", s)
    s = _LEGACY_CLOSE.sub(_drop_close, _LEGACY_OPEN.sub(_drop_open, s))
    return _trim(_WS_RUN.sub(" ", s))


def word_before_pipe(items) -> list:
    """A \\w's content up to its first `|` (the rest is an unparsed attribute)."""
    out = []
    for it in items or []:
        if isinstance(it, str) and "|" in it:
            out.append(it[: it.index("|")])
            break
        out.append(it)
    return out


def _first(key: str) -> str:
    # the extractors' own "already seen" key: split on - and , only (as the JS does)
    return _trim(re.split("[-,]", key)[0])


def _js_str(v) -> str:
    """String(v) as JavaScript gives it, for the numbers a verse/chapter field can hold."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, list):
        return ",".join(_js_str(x) for x in v)
    return "undefined" if v is None else str(v)


class Collector:
    """Collects text per verse: add(verse, text); result() -> [{verse, text}] in order."""

    def __init__(self):
        self.text: dict[str, list[str]] = {}

    def add(self, verse, s: str):
        if verse is None:
            return
        self.text.setdefault(first_number(verse), []).append(s)

    def restart(self, verse):
        """A verse number seen again later (not continuing): a new piece, joined by a space."""
        key = first_number(verse)
        if key in self.text:
            self.text[key].append(" ")

    def result(self) -> Verses:
        out = [{"verse": v, "text": clean("".join(parts))} for v, parts in self.text.items()]
        return [x for x in out if x["text"] != ""]


def extract_usj(usj: dict[str, Any]) -> dict[str, Verses]:
    chapters: dict[str, Collector] = {}
    st: dict[str, Any] = {"verse": None, "out": None, "seen": None}

    def set_verse(number):
        key = _js_str(number)
        if st["verse"] != key and _first(key) in st["seen"]:
            st["out"].restart(key)
        st["verse"] = key
        st["seen"].add(_first(key))

    def inline(items, ctx):
        for it in items or []:
            if isinstance(it, str):
                if (not ctx["heading"] or ctx["verse_here"]) and st["out"] is not None:
                    st["out"].add(st["verse"], it)
                continue
            if not isinstance(it, dict):
                continue
            t = it.get("type")
            if t == "verse":
                if st["out"] is not None:
                    set_verse(it.get("number"))
                    ctx["verse_here"] = True
            elif t in ("note", "figure", "ms", "optbreak"):
                pass
            elif t == "char":
                if it.get("marker") not in SKIP_CHAR:
                    content = it.get("content")
                    inline(word_before_pipe(content) if it.get("marker") == "w" else content, ctx)
            else:
                inline(it.get("content"), ctx)

    def block(node):
        if not isinstance(node, dict):
            return
        t = node.get("type")
        if t == "chapter":
            st["verse"] = None
            st["out"] = Collector()
            st["seen"] = set()
            chapters[_js_str(node.get("number"))] = st["out"]
            return
        if st["out"] is None:  # before the first chapter: book title, introduction
            return
        if t == "para":
            marker = node.get("marker") or ""
            if SKIP_PARA.fullmatch(marker):
                return
            inline(node.get("content"), {"heading": bool(HEADING.fullmatch(marker)), "verse_here": False})
            st["out"].add(st["verse"], " ")  # a paragraph ends a line
            return
        if t in ("table", "table:row", "row"):
            for c in node.get("content") or []:
                block(c)
            return
        if t in ("table:cell", "cell"):
            inline(node.get("content"), {"heading": False, "verse_here": False})
            st["out"].add(st["verse"], " ")
            return
        if t in ("note", "figure"):
            return
        inline(node.get("content"), {"heading": False, "verse_here": False})

    for node in usj.get("content") or []:
        block(node)
    return {c: col.result() for c, col in chapters.items()}


# block grafts that hold no verse text
SKIP_GRAFT = {"heading", "title", "introduction", "end_title", "remark", "fig", "footnote", "xref", "note_caller"}


def _usfm(subtype) -> str:
    if subtype and subtype.startswith("usfm:"):
        return subtype[5:]
    return subtype or ""


def _one(v):
    return v[0] if isinstance(v, list) else v


def extract_sofria(doc: dict[str, Any]) -> Verses:
    out = Collector()
    st: dict[str, Any] = {"verse": None, "seen": set(), "chapter": None}

    def set_verse(number, label):
        key = _js_str(_one(number))
        first = _first(key)
        if label and st["verse"] != key and first in st["seen"]:
            out.restart(key)
        st["verse"] = key
        st["seen"].add(first)

    def inline(items, ctx):
        for it in items or []:
            if isinstance(it, str):
                if not ctx["heading"] or ctx["verse_here"]:
                    out.add(st["verse"], it)
                continue
            if not isinstance(it, dict):
                continue
            t = it.get("type")
            atts = it.get("atts") or {}
            if t == "mark":
                if it.get("subtype") == "verses_label":
                    set_verse(atts.get("number"), True)
                    ctx["verse_here"] = True
                continue  # other marks (chapter label, \vp, \va, \ca) carry no text
            if t in ("graft", "start_milestone", "end_milestone"):
                continue
            if t == "wrapper":
                sub = it.get("subtype")
                if sub == "chapter":
                    # the next chapter's label (and anything on it) can close this document
                    n = _js_str(_one(atts.get("number")))
                    if st["chapter"] is None:
                        st["chapter"] = n
                    if n != st["chapter"]:
                        continue
                if sub == "verses" and atts.get("number") is not None and st["verse"] is None:
                    set_verse(atts["number"], False)
                if _usfm(sub) in SKIP_CHAR:
                    continue
                # a table cell is a word boundary on both sides
                if sub == "cell":
                    out.add(st["verse"], " ")
                inline(word_before_pipe(it.get("content")) if sub == "usfm:w" else it.get("content"), ctx)
                if sub == "cell":
                    out.add(st["verse"], " ")

    def blocks(items):
        for b in items or []:
            if b.get("type") == "graft":
                kind = (b.get("sequence") or {}).get("type") or b.get("subtype") or ""
                if kind not in SKIP_GRAFT:
                    blocks((b.get("sequence") or {}).get("blocks"))
                continue
            if b.get("type") == "row":
                for cell in b.get("content") or []:
                    inline([cell], {"heading": False, "verse_here": False})
                    out.add(st["verse"], " ")
                continue
            marker = _usfm(b.get("subtype"))
            if SKIP_PARA.fullmatch(marker):
                continue
            inline(b.get("content"), {"heading": bool(HEADING.fullmatch(marker)), "verse_here": False})
            out.add(st["verse"], " ")

    blocks((doc.get("sequence") or {}).get("blocks"))
    return out.result()
