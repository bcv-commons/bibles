#!/usr/bin/env python3
"""Reference decoder for DBT's "text_json" fileset shape — a real,
confirmed gap flagged by a client (audio-sync, 2026-10-02): a DBT
fileset whose `get_text_content()`-equivalent response is
`{"type": "path", "data": <url>}` (not inline `{"type": "verses", ...}`)
points to a downloadable document that is a raw, UNCOMPRESSED Proskomma
"Sofria" JSON document (`schema.constraints[].name == "sofria"`) — a
structurally different wire format from `tools/pkf-decode/`'s `.pkf`
(a gzip-compressed Proskomma succinct docSet). Same real engine family,
different shape; `.pkf` tooling does not and was never meant to handle
this. Real fileset ids for this shape carry a telltale `-json` suffix
(confirmed live, 2026-10-02: `ADXNVSO_ET-json`, Tibetan Psalm 119).

This file is deliberately minimal — same spirit as `tools/pkf-decode/`:
walk `sequence.blocks`, skip `"graft"` sub-sequences entirely (footnotes,
headings, cross-references — real content, just not verse text), track
verse boundaries via `{"type":"mark","subtype":"verses_label"}`, and
collect plain text. It is NOT a full Sofria renderer — for anything
beyond plain verse text (tables, milestones, `meta_content`, real HTML
rendering), the authoritative reference is `proskomma-json-tools`'s
`render/renderers/SofriaRenderFromJson.js`
(https://github.com/mvahowe/proskomma-json-tools), not this file.

Real, confirmed detail this decoder gets right that a naive walk would
miss: a verse's text can legitimately span MULTIPLE top-level paragraph
blocks (e.g. poetry \\q1/\\q2 lines) — a later block "reopens" a
`"verses"` wrapper for the SAME verse number without a fresh
`verses_label` mark. This decoder's outer block loop inserts a joining
space when a new top-level block continues the SAME still-open verse
(the same real class of bug already found and fixed this session in
`pipeline/core/usfm_to_verses.py` for the unrelated USJ/usfmtc path —
confirmed independently here too: Sofria's own raw text fragments carry
no embedded trailing/leading whitespace at these block boundaries
either).

Usage:
    python3 decode.py <sofria.json>
        Prints {chapter: {verse: text}} as JSON to stdout.

    from decode import extract_verses_from_sofria
    chapters = extract_verses_from_sofria(json.load(open("sofria.json")))
"""
import json
import sys


def _walk(node, state):
    """Recurse into one Sofria node, accumulating plain text into
    state["buf"] for the currently-open verse. Grafts (footnotes,
    headings, cross-references) are real content but not verse text —
    skipped entirely, never recursed into. `"mark"` nodes other than
    `verses_label` (e.g. `chapter_label`) carry no text of their own."""
    if isinstance(node, str):
        state["buf"].append(node)
        return
    if not isinstance(node, dict):
        return

    kind = node.get("type")
    if kind == "graft":
        return
    if kind == "mark":
        if node.get("subtype") == "verses_label":
            _flush(state)
            state["verse"] = node.get("atts", {}).get("number")
            state["buf"] = []
        return

    for child in node.get("content", []) or []:
        _walk(child, state)


def _flush(state):
    if state["verse"] is not None and state["buf"]:
        text = "".join(state["buf"]).strip()
        text = " ".join(text.split())
        if text:
            state["chapters"].setdefault(state["chapter"], {})[state["verse"]] = text
    state["buf"] = []


def extract_verses_from_sofria(doc: dict) -> dict:
    """A real Sofria document (as downloaded from a DBT `text_json`
    fileset's `path` URL) -> {chapter_int: {verse_str: text}}, same
    output shape as `pipeline/core/usfm_to_verses.py`'s
    `extract_verses_from_file()` for the unrelated USFM/USJ path."""
    chapter_str = doc.get("metadata", {}).get("document", {}).get("properties", {}).get("chapters")
    chapter = int(chapter_str) if chapter_str is not None else 0

    state = {"chapter": chapter, "verse": None, "buf": [], "chapters": {}}
    for block in doc.get("sequence", {}).get("blocks", []) or []:
        if block.get("type") == "graft":
            continue  # top-level heading/title grafts — not verse text
        # A still-open verse continuing into a new top-level paragraph
        # block (e.g. a poetry line break) needs a joining space — see
        # module docstring. Only applies when no fresh verses_label is
        # about to fire inside this block (that case flushes on its own).
        if state["verse"] is not None and state["buf"]:
            state["buf"].append(" ")
        _walk(block, state)
    _flush(state)
    return state["chapters"]


def main():
    if len(sys.argv) != 2:
        print("usage: python3 decode.py <sofria.json>", file=sys.stderr)
        sys.exit(2)
    doc = json.loads(open(sys.argv[1], encoding="utf-8").read())
    chapters = extract_verses_from_sofria(doc)
    print(json.dumps(chapters, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
