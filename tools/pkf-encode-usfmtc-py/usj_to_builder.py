"""Walks a `usfmtc`-produced USJ (Unified Scripture JSON) tree and drives
../pkf-encode-py's already-validated `usfm_to_items.Builder` — the
succinct-encoding backend is entirely reused, unchanged; only the USFM
*parsing* frontend differs (usfmtc's real grammar-based parser instead of
../pkf-encode-py's own hand-rolled usfm_lexer.py tokenizer).

Because usfmtc hands back a well-formed, already-closed TREE (not a flat
token stream), several of Builder's real-raw-USFM tolerances turn out to
be unnecessary here, which simplifies this walker versus
../pkf-encode-py/usfm_to_items.py's own `build()`:

- No marker allowlist needed for character styles or paragraph styles.
  usfm_lexer.py has to classify every marker up front (HEADER_MARKERS /
  PARAGRAPH_MARKERS / CHAR_MARKERS / NOTE_CHAR_MARKERS) because it works
  from raw text; usfmtc has already done that classification via its own
  real grammar, and reports it directly as the USJ node's "type"
  ("para"/"char"/"note"/"ms"/"chapter"/"verse"). This walker trusts that
  classification instead of maintaining a second copy of the same tables
  — one exception below (HEADER_MARKERS), which genuinely can't be
  inferred from USJ alone (see _walk_book/_is_header).
- No separate start_note_char/end_note_char path. That pair exists in
  Builder purely to tolerate real USFM's self-closing convention (no
  explicit \\fr*/\\fq* in raw source — see usfm_to_items.py's own
  docstring). Confirmed directly (reading Builder's code): start_char/
  end_char and start_note_char/end_note_char emit byte-IDENTICAL scope
  items for a well-formed open/close pair (both just
  ["scope","start"/"end", f"span/{tag}"]) — the only difference is
  tolerance for a missing close, which a USJ tree never has. So every
  "char" node except \\w (which needs the special spanWithAtts encoding
  for its attributes) goes through the plain start_char/end_char path
  here, regardless of whether it's a real character style or a
  note-internal field like \\fr/\\xt.
- No milestone-name allowlist (usfm_lexer.py's MILESTONE_MARKERS = {"zaln"}
  plus a hardcoded 'ts' exception). Builder.start_milestone/end_milestone
  accept an arbitrary name; this walker just strips a USJ "ms" node's
  "-s"/"-e" marker suffix generically, no matter what the base name is.

HEADER_MARKERS is the one table still imported (from ../pkf-encode-py's
usfm_lexer.py, not duplicated) — USJ conflates "header line" and "regular
paragraph" under the same "para" type (confirmed directly: a real \\h line
parses to {"type":"para","marker":"h",...}, structurally identical to
\\mt1's node), so there's no way to tell them apart from the tree alone;
only the marker name distinguishes them, same as the original tokenizer.

Not handled (raises, same "raise rather than guess" philosophy as
../pkf-encode-py): tables (USJ "table"/"row"/"cell" — already out of scope
for that package too, see its README), \\fig, \\ref, \\optbreak, and
anything else usfmtc's grammar recognizes that this package's Builder
backend has no encoding for.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pkf-encode-py"))
from usfm_lexer import HEADER_MARKERS  # noqa: E402
from usfm_to_items import Builder  # noqa: E402


def _text_of(content):
    """Join a USJ content list's direct string children — used only for
    header paragraphs, which real content never nests further markup
    inside (confirmed against this package's own test corpus)."""
    return "".join(c for c in content if isinstance(c, str)).strip()


def _extra_attrs(node):
    return {k: v for k, v in node.items() if k not in ("type", "marker", "content")}


def _walk_book(node, b):
    code = node.get("code") or ""
    rest = _text_of(node.get("content", []))
    value = f"{code} {rest}".strip() if rest else code
    b.set_header("id", value)


def _walk_inline(node, b):
    if isinstance(node, str):
        b.add_text(node)
        return
    kind = node.get("type")
    marker = node.get("marker")

    if kind == "verse":
        b.add_verse(node.get("number"))
    elif kind == "chapter":
        # A mid-paragraph chapter mark (rare, but structurally legal —
        # e.g. a \\cp/\\ca variant folded to plain "chapter" by usfmtc) —
        # same handling as a top-level one.
        b.add_chapter(node.get("number"))
    elif kind == "ms":
        if marker.endswith("-s"):
            b.start_milestone(marker[:-2], _extra_attrs(node))
        elif marker.endswith("-e"):
            b.end_milestone(marker[:-2])
        elif node.get("content"):
            # A bare, non-standard marker (e.g. real content found using
            # "\P" — not real USFM, but usfmtc still parses it, generically
            # wrapping what follows as an "x-bare" milestone-like container
            # with its own "content"). Found as a REAL bug (not just a
            # missing feature): silently skipping the whole node here
            # dropped the wrapped TEXT too, not just the unrecognized
            # marker — a genuine content-loss round-trip failure (found
            # 2026-09-16 via the full-corpus verification, zos/ACT 2:13).
            # Fixed: still walk the wrapped content — we don't know what
            # the bare marker itself means structurally, but its content
            # is real and must not be dropped.
            for child in node["content"]:
                _walk_inline(child, b)
        # A bare, content-less milestone (not seen in this package's real
        # test corpus) is silently skipped — nothing to lose.
    elif kind == "note":
        # NOTE_MARKERS only has "f"/"x" — a real, rare third case exists:
        # usfmtc's grammar generically accepts some other backslash-tags
        # as "note" type too (e.g. found in real content, marker "fe" —
        # traced to a genuine nested `scope start inline/fe` construct
        # inside a footnote block in the ORIGINAL succinct data, which
        # the real proskomma-style text renderer silently no-ops on since
        # `succinct_renderer.py`'s `_render_item` has no branch for scope
        # head "inline" at the content-item level — not a decode quirk,
        # real (if obscure) source structure this package doesn't yet
        # know how to re-encode). Raise cleanly here (matching the
        # table/figure/optbreak pattern) instead of letting Builder's
        # internal NOTE_MARKERS[tag] KeyError propagate uncaught.
        if marker not in ("f", "x"):
            raise ValueError(f"Unsupported note marker \\{marker} (only \\f/\\x are supported)")
        tag = marker
        b.start_note(tag)
        caller = node.get("caller")
        if caller:
            b.add_text(caller)
        for child in node.get("content", []):
            _walk_inline(child, b)
        b.end_note(tag)
    elif kind == "char":
        if marker == "w":
            b.start_word(_extra_attrs(node))
            for child in node.get("content", []):
                _walk_inline(child, b)
            b.end_word()
        else:
            # Covers both ordinary character styles (\\bd, \\it, ...) and
            # note-internal fields (\\fr, \\fq, \\xt, ...) — see module
            # docstring for why both are byte-identical through this path.
            b.start_char(marker)
            for child in node.get("content", []):
                _walk_inline(child, b)
            b.end_char(marker)
    else:
        raise ValueError(f"Unsupported inline USJ node type {kind!r} (marker={marker!r})")


def build_from_usj(usj):
    """usj (usfmtc's outUsj() dict) -> a finished usfm_to_items.Builder,
    ready for build_pkf.build_pkf_bytes()."""
    b = Builder()
    for node in usj.get("content", []):
        if isinstance(node, str):
            if node.strip():
                raise ValueError(f"Unexpected top-level text content: {node!r}")
            continue
        kind = node.get("type")
        marker = node.get("marker")
        if kind == "book":
            _walk_book(node, b)
        elif kind == "chapter":
            b.add_chapter(node.get("number"))
        elif kind == "para":
            if marker in HEADER_MARKERS:
                b.set_header(marker, _text_of(node.get("content", [])))
            else:
                b.start_para(marker)
                for child in node.get("content", []):
                    _walk_inline(child, b)
        else:
            raise ValueError(f"Unsupported top-level USJ node type {kind!r} (marker={marker!r})")
    b.finish()
    return b
