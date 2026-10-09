"""Convert helloAO's real per-chapter JSON (bible.helloao.org/api/<id>/<BOOK>/<N>.json)
into USJ (Unified Scripture JSON) — the only one of the 4 sources with no
USFM available at all (checked directly 2026-09-17: all 1,256 real
translations report `availableFormats: ["json"]` only), so this is a
bespoke JSON->JSON mapping, not a USFM-parse like the other 3 sources use.

Real schema (confirmed directly against live chapters — BSB/PSA/23 for
poem/hebrew_subtitle/lineBreak/notes, BSB/MAT/5 for headings — cross-checked
against the documented schema at
bible.helloao.org/docs/reference/translations/standard.html, not trusted
from docs alone):

  chapter.content[] items:
    {"type": "heading", "content": [str, ...]}
    {"type": "hebrew_subtitle", "content": [str, ...]}
    {"type": "line_break"}
    {"type": "verse", "number": int, "content": [
        str
        | {"text": str, "poem": int}       # poetry indent level -> \\q1/\\q2/...
        | {"text": str, "wordsOfJesus": true}
        | {"heading": str}                  # rare: inline heading mid-verse
        | {"lineBreak": true}               # end of a line (between poetry lines)
        | {"noteId": int}                   # footnote reference, see below
    ]}
  chapter.footnotes[]:
    {"noteId": int, "text": str, "caller": str|null, "reference": {...}}

Mapping decisions:
  - "heading"/"hebrew_subtitle" -> top-level USJ para (marker "s1"/"d") —
    matches real USFM section-heading/descriptive-title conventions.
  - top-level "line_break" -> a "b" (blank line) para, closing whatever
    paragraph was open — real USFM's own blank-line marker, the closest real
    equivalent to a stanza break.
  - inline {"lineBreak": true} -> the end of a line only: the open paragraph
    is closed, so the next fragment opens a new one, even at the same poem
    level (a plain-string fragment continues at that level). helloAO puts one
    between every pair of poetry lines (BSB MAT 1:2, all of Psalms), so a
    "b" here gave a blank line between every line (fixed 2026-10-09).
  - a verse's number goes into the paragraph its first content opens, so a
    verse starting with poetry doesn't leave its number alone in a "p".
  - "poem": N -> a "q1"/"q2"/... para (real USFM poetry indent markers).
    Tracked as ongoing STATE across verses (a poem level begun in one
    verse continues until the level changes or a heading/line_break
    interrupts it) — poetry lines routinely span verse boundaries in real
    content, confirmed directly (Psalm 23 alternates poem 1/2 within and
    across verses).
  - "wordsOfJesus": true -> inline USJ char node, marker "wj" (real USFM
    red-letter-text marker). Not yet seen in a live sample this session
    (checked BSB/JHN 3, no hit) but kept per the documented schema — a
    real, standard USFM concept, not a guess.
  - {"noteId": N} -> resolved against chapter.footnotes[] (by noteId, not
    position — confirmed real footnotes aren't always in content order)
    into a USJ "note" node, marker "f" (helloAO's schema has no
    footnote/xref type distinction we've found, so all notes are treated
    as plain footnotes — a documented simplification, not silently
    dropped data).
  - No table/figure equivalent found in the real schema — nothing to map,
    consistent with the other 3 sources' own known table/figure gaps.

Output: a real USJ 3.0 document, one per chapter (matching this source's
natural per-chapter API granularity) — NOT a whole-book tree like the
other 3 sources produce internally, since helloAO's own API never exposes
more than one chapter at a time. A book-level USJ (if ever needed) would
require a separate merge step concatenating chapters, not something this
module does.
"""
from __future__ import annotations


_POEM_MARKER = {1: "q1", 2: "q2", 3: "q3", 4: "q4"}

# helloAO's raw content lists split running text into separate fragments
# around {"noteId": N} refs (and around poem-level changes) with NO
# whitespace of their own at the split points (confirmed live 2026-09-19:
# 0/many sampled text fragments start or end with a space) — so joining
# fragments always needs an explicit decision, never a bare concatenation.
# But the decision isn't "always insert a space": real English sentence
# punctuation matters (confirmed live: BSB Joshua has a footnote sitting
# INSIDE a parenthetical, "...phrase(\\f ...\\f*)." — a space before the
# following ")." would be wrong) vs. a footnote mid-sentence between two
# whole words (BSB Matthew 1:21, "...name Jesus," + note + "because He...")
# which DOES need a space. These two sets encode standard no-space-before/
# no-space-after English typesetting rules to make that call correctly.
_NO_SPACE_BEFORE = set(",.;:!?)]}’”")
_NO_SPACE_AFTER = set("([{‘“")


def _last_char_of(content):
    """Last VISIBLE character already in `content`, skipping over note
    nodes (a footnote mark renders inline without consuming surrounding
    space, so it must not block finding the real preceding character)."""
    for item in reversed(content):
        if isinstance(item, str):
            if item:
                return item[-1]
            continue
        if isinstance(item, dict) and item.get("type") == "char":
            c = _last_char_of(item.get("content") or [])
            if c is not None:
                return c
            continue
        # "note" and any other node type: skip past, keep looking back
    return None


def _first_char_of(piece):
    if isinstance(piece, str):
        return piece[0] if piece else None
    if isinstance(piece, dict) and piece.get("type") == "char":
        for item in piece.get("content") or []:
            c = _first_char_of(item)
            if c is not None:
                return c
    return None


def _needs_space(prev_char, next_char):
    if prev_char is None or next_char is None:
        return False
    if next_char in _NO_SPACE_BEFORE or prev_char in _NO_SPACE_AFTER:
        return False
    return True


def _prefix_space(piece):
    if isinstance(piece, str):
        return " " + piece
    if isinstance(piece, dict) and piece.get("type") == "char":
        content = list(piece.get("content") or [])
        if content and isinstance(content[0], str):
            content[0] = " " + content[0]
            piece = {**piece, "content": content}
    return piece


def _append_piece(content_list, piece):
    """Append a text-bearing piece (plain str, or a "char" node like
    marker "wj"), inserting a joining space first if the real English
    typesetting rules above call for one. Note nodes bypass this — they
    have no visible leading/trailing character of their own."""
    if _needs_space(_last_char_of(content_list), _first_char_of(piece)):
        piece = _prefix_space(piece)
    content_list.append(piece)


def _flush_para(top_content, state):
    if state["para"] is not None and (state["para"]["content"] or state["para"]["marker"] == "b"):
        top_content.append(state["para"])
    state["para"] = None
    state["para_marker"] = None


def _ensure_para(top_content, state, marker):
    if state["para_marker"] != marker:
        _flush_para(top_content, state)
        state["para"] = {"type": "para", "marker": marker, "content": []}
        state["para_marker"] = marker
    if state["pending_verse"] is not None:
        state["para"]["content"].append(state["pending_verse"])
        state["pending_verse"] = None
    return state["para"]


def _end_line(top_content, state):
    marker = state["para_marker"]
    _flush_para(top_content, state)
    state["line_marker"] = marker


def _current_marker(state):
    return state["para_marker"] or state["line_marker"] or "p"


def _append_heading(top_content, state, marker, items, footnotes_by_id):
    """Build a heading/subtitle paragraph from a real content list — not
    always plain strings: hebrew_subtitle in particular can interleave
    {"noteId": N} footnote refs between text fragments (real, confirmed
    live 2026-09-19 in BSB/PSA, e.g. Psalm 6's "With stringed instruments,
    according to Sheminith." + a noteId + "A Psalm of David.") — a naive
    " ".join() over the raw list crashes on the dict item."""
    _flush_para(top_content, state)
    content = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
            if text:
                _append_piece(content, text)
        elif isinstance(item, dict) and "noteId" in item:
            note = _resolve_note(footnotes_by_id, item["noteId"])
            if note is not None:
                content.append(note)
    if content:
        top_content.append({"type": "para", "marker": marker, "content": content})


def _append_blank(top_content, state):
    _flush_para(top_content, state)
    state["line_marker"] = None
    top_content.append({"type": "para", "marker": "b", "content": []})


def _resolve_note(footnotes_by_id, note_id):
    fn = footnotes_by_id.get(note_id)
    if fn is None:
        return None
    caller = fn.get("caller") or "+"
    text = (fn.get("text") or "").strip()
    node = {"type": "note", "marker": "f", "caller": caller, "content": []}
    if text:
        # Deliberately a bare string, NOT {"type":"char","marker":"ft",...} —
        # real Proskomma (proskomma-core@0.11.3) confirmed live 2026-09-19:
        # a "char" node with marker "ft" nested inside a "note" node, when
        # imported via its own USJ importer, corrupts the text with a
        # stray literal `| marker="ft"` prefix in the rendered Sofria
        # (reproduced in isolation, unrelated to anything else in this
        # module — a real Proskomma USJ-import bug, not our data). A bare
        # string imports clean, and is still valid: \ft is USFM's implicit
        # default footnote-text marker right after the caller, so omitting
        # it explicitly loses nothing (confirmed via a real usfmtc
        # usj->usx->usfm round-trip: renders "\\f + text\\f*", correct USFM).
        node["content"].append(text)
    return node


def _walk_verse_content(item, top_content, state, footnotes_by_id):
    """Append one verse-content item into the currently-open paragraph
    (opening/switching paragraphs as needed for poem-level changes)."""
    if isinstance(item, str):
        para = _ensure_para(top_content, state, _current_marker(state))
        _append_piece(para["content"], item)
        return

    if not isinstance(item, dict):
        return

    if "noteId" in item:
        para = _ensure_para(top_content, state, _current_marker(state))
        note = _resolve_note(footnotes_by_id, item["noteId"])
        if note is not None:
            para["content"].append(note)
        return

    if "lineBreak" in item:
        _end_line(top_content, state)
        return

    if "heading" in item:
        _append_heading(top_content, state, "s1", [item["heading"]], footnotes_by_id)
        return

    if "text" in item:
        poem = item.get("poem")
        marker = _POEM_MARKER.get(poem, "p") if poem else _current_marker(state)
        para = _ensure_para(top_content, state, marker)
        text = item["text"]
        if item.get("wordsOfJesus"):
            _append_piece(para["content"], {"type": "char", "marker": "wj", "content": [text]})
        else:
            _append_piece(para["content"], text)
        return


def chapter_to_usj(chapter_json: dict, book_code: str) -> dict:
    """helloAO's real per-chapter API response (the full JSON, with both
    "chapter" and "book"/"translation" keys) -> a real USJ 3.0 document
    for that one chapter, including a real \\id/book node so the result
    is independently valid (not just a content fragment)."""
    chapter = chapter_json["chapter"]
    footnotes_by_id = {fn["noteId"]: fn for fn in chapter.get("footnotes", [])}

    top_content = [
        {"type": "book", "marker": "id", "code": book_code, "content": []},
        {"type": "chapter", "marker": "c", "number": str(chapter["number"])},
    ]
    state = {"para": None, "para_marker": None, "line_marker": None, "pending_verse": None}

    for item in chapter.get("content", []):
        kind = item.get("type") if isinstance(item, dict) else None
        if kind == "heading":
            _append_heading(top_content, state, "s1", item.get("content", []), footnotes_by_id)
        elif kind == "hebrew_subtitle":
            _append_heading(top_content, state, "d", item.get("content", []), footnotes_by_id)
        elif kind == "line_break":
            _append_blank(top_content, state)
        elif kind == "verse":
            state["pending_verse"] = {"type": "verse", "marker": "v", "number": str(item["number"])}
            for sub in item.get("content", []):
                _walk_verse_content(sub, top_content, state, footnotes_by_id)
            if state["pending_verse"] is not None:  # a verse with no content
                _ensure_para(top_content, state, _current_marker(state))
        # Any other/unknown top-level type is skipped, not guessed at —
        # none found in real samples checked so far (heading,
        # hebrew_subtitle, line_break, verse are the only 4 real
        # top-level types confirmed).

    _flush_para(top_content, state)
    return {"type": "USJ", "version": "3.0", "content": top_content}
