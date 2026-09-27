"""Real per-verse text extraction from raw USFM — uses `usfmtc`
(https://pypi.org/project/usfmtc/, a real, actively maintained USFM
parser), not this repo's own narrower tools/pkf-encode-py tokenizer.

Switched 2026-09-19 after the vendored tokenizer (deliberately scoped to
"core Scripture text + word-level attributes + milestones", not full
USFM per its own docstring) failed on 30+ distinct real marker types
across the cached Biblica corpus (`\\mt`, `\\imt`, `\\po`, `\\fig`, `\\ms`,
etc. — thousands of files). `usfmtc` is the same library used by a real
external USFM-handling example
(https://github.com/BSB-publishing/bsb2usfm/blob/main/bsb2usfm.py) and
parsed the exact file that failed before with zero errors.

Output shape unchanged from the first version: {chapter_int: {verse_str: "text"}}.
"""
import usfmtc

# Heading/title-class paragraph markers that can appear MID-TEXT, between
# two verses with no fresh \v mark in between (e.g. a section heading
# right after v13, before v14 starts) — real, confirmed bug (found via
# tools/verify_pkf_usfmtc_roundtrip.py's full-corpus run, zos/ACT 2:13):
# without this check, _walk() below has no way to know a new top-level
# "para" node isn't still part of the CURRENT verse (state["verse"] only
# changes on an explicit chapter/verse mark), so heading text was being
# silently appended to the preceding verse's text. A plain body-paragraph
# break (\p, \q1, etc. — no marker in this set) is deliberately NOT
# skipped here: that mid-verse paragraph break is common and its text
# genuinely does belong to the current verse.
_NON_VERSE_PARA_MARKERS = {
    "s", "s1", "s2", "s3", "s4",
    "ms", "ms1", "ms2",
    "mr", "sr", "d", "sp", "cl", "r",
    "mte", "mte1", "mte2",
}


def _walk(node, chapters: dict, state: dict):
    """Recursively collect verse text from a USJ content node. `state`
    carries current chapter/verse/buffer across the recursive walk."""
    if isinstance(node, str):
        if state["chapter"] is not None and state["verse"] is not None:
            state["buf"].append(node)
        return

    if not isinstance(node, dict):
        return

    kind = node.get("type")

    if kind == "chapter":
        _flush(chapters, state)
        state["chapter"] = int(node["number"])
        state["verse"] = None
        state["buf"] = []
        return

    if kind == "verse":
        _flush(chapters, state)
        state["verse"] = node.get("number")
        state["buf"] = []
        return

    if kind == "note":
        # Footnotes/cross-refs — not reading text, same principle already
        # applied throughout this repo's comparator work. Don't recurse.
        return

    if kind == "para" and node.get("marker") in _NON_VERSE_PARA_MARKERS:
        return  # heading/title text is not verse content — see module-level comment

    if kind == "para" and state["buf"]:
        # A body-paragraph boundary (e.g. \q1 -> \q2, or \p -> \p) within
        # the SAME still-open verse — real, confirmed bug (found 2026-09-18
        # building the helloAO->USJ converter, whose Psalm 23 test case
        # exposed it, then confirmed it was already affecting real
        # PUBLISHED openbible chapter JSON too, e.g.
        # export/openbible/tgl/OASD/PSA/23.json: every verse missing a
        # space at each poetry line break, "pastol,hindi", "akosa", etc.).
        # _walk() never inserted a separator between two sibling para
        # nodes' text runs — they just concatenated directly. A single
        # space here is always safe: the final `" ".join(text.split())`
        # normalization in _flush() collapses it back down if the
        # surrounding text already had its own whitespace.
        state["buf"].append(" ")

    for child in node.get("content", []) or []:
        _walk(child, chapters, state)


def _flush(chapters: dict, state: dict):
    if state["chapter"] is not None and state["verse"] is not None and state["buf"]:
        text = "".join(state["buf"]).strip()
        text = " ".join(text.split())
        if text:
            chapters.setdefault(state["chapter"], {})[state["verse"]] = text


def extract_verses_from_file(usfm_path: str) -> dict:
    doc = usfmtc.readFile(usfm_path)
    usj = doc.outUsj()
    chapters: dict = {}
    state = {"chapter": None, "verse": None, "buf": []}
    for item in usj.get("content", []):
        _walk(item, chapters, state)
    _flush(chapters, state)
    return chapters


def extract_verses(usfm_text: str, tmp_path: str) -> dict:
    """Convenience wrapper for in-memory USFM text (usfmtc.readFile()
    needs a real file path) — caller supplies a scratch path to write to;
    not deleted here, caller's responsibility."""
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(usfm_text)
    return extract_verses_from_file(tmp_path)
