"""Builds the block/sequence structure (matching ../pkf-decode-py's Item
shape exactly) from usfm_lexer's token stream.

Key design choices driven by round-trip correctness against the real
succinct_renderer.py quirks already validated in pkf-decode-py:

- Text runs are NOT split into word/punctuation/space tokens — the decoder
  concatenates every token's payload uniformly regardless of subtype (see
  succinct_renderer.py's `_render_item`), so one 'wordLike' token per
  contiguous text run round-trips identically to a "properly" tokenized
  one, and is far simpler to get right. This means our own enum tables
  don't distinguish real words for search/alignment purposes the way a
  real proskomma-core-produced .pkf would — acceptable for this package's
  stated scope (publishing readable text, not powering alignment tooling).
  One real, narrow, purely cosmetic consequence (confirmed against real
  corpus round-trip testing, 3 cases out of 1000+): the decoder's
  whitespace normalization (ws_normalize) collapses any run of whitespace
  *within one token* to a single space. A genuine double-space in source
  content that happens to fall exactly at a marker boundary — where a
  "properly" multi-token-split encoding would have split it across two
  separate tokens, each independently normalizing to one space and so
  preserving both — instead collapses to a single space here, since it's
  one token's internal whitespace. No word or content is ever lost, only
  a redundant space at a marker boundary — accepted as a v1 trade-off
  rather than reintroducing real word/punctuation/space tokenization.
- Bare \\w (no attributes) is encoded as a plain 'span' scope (symmetric
  open/close, no quirks). \\w with attributes and \\zaln-s/\\zaln-e
  milestones both need 'spanWithAtts'/'milestone' + 'attribute' scopes,
  which is real-library-load-bearing but has two real quirks, both
  confirmed by direct testing against pkf-decode-py's already-validated
  renderer (not assumed from reading):
  (a) the spanWithAtts/milestone *end* scope is itself a structural no-op
      (see succinct_renderer.py's docstring) — the wrapper/milestone only
      closes when a later *attribute*-end item arrives with no open
      container, which itself only flushes on the *next* item after that.
      `_close_attributed_wrapper()` emits that synthetic trigger right
      after the tagged content, so closing "just works" as long as
      something follows in the same block — the one case that can't
      round-trip is an attributed \\w or milestone as the literal last
      thing in a paragraph, matching the real library's own limitation,
      not a regression here.
  (b) attribute values attached to a wrapper's OPENING side are silently
      discarded no matter what (startWrapper never reads atts at all) —
      only the CLOSING side's atts ever render, and the closing side's
      "attribute-end-with-no-container" trick only populates ONE
      key/value pair (later ones no-op since the container already
      exists by then). So \\w keeps only its FIRST attribute for v1.
      Milestones don't share this problem — their OPENING side DOES
      render atts, and multiple attribute-start items on an
      already-open container all accumulate correctly — so a real
      multi-attribute \\zaln-s (x-content/x-lemma/x-strong/...) round-trips
      in full; see `start_milestone`.
- \\fr/\\fq/\\fk/\\fl/\\fw/\\fp/\\ft (and the \\x equivalents) have no
  explicit closing marker in real USFM — each runs until the next such
  marker or the note's end. Modeled as 'span' scopes that this builder
  auto-closes, matching decode's own `_NO_END_TAG_WRAPPERS` set (which
  never emits a *visible* closing tag for these, but still requires a
  properly balanced open/close pair structurally).
"""
from usfm_lexer import tokenize, NOTE_MARKERS

_MILESTONE_NAME = {"zaln": "zaln"}

_MAX_COUNTED_STRING_BYTES = 255


def _chunk_text(text, max_bytes=_MAX_COUNTED_STRING_BYTES):
    """Split text into pieces each <= max_bytes when UTF-8 encoded, never
    splitting a multi-byte character, and never adding/dropping characters
    (concatenating the pieces back together reproduces `text` exactly)."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        yield text
        return
    start = 0
    n = len(text)
    while start < n:
        # Binary-search-free greedy walk: grow the piece one char at a time
        # until it would exceed max_bytes, which is plenty fast for any
        # realistic verse-length text run.
        end = start
        size = 0
        while end < n:
            char_size = len(text[end].encode("utf-8"))
            if size + char_size > max_bytes:
                break
            size += char_size
            end += 1
        if end == start:
            # A single character alone exceeds max_bytes — not realistic for
            # UTF-8 (max 4 bytes/char), but guard against an infinite loop.
            end = start + 1
        yield text[start:end]
        start = end


class SeqIdGen:
    """Generates footnote/xref/etc. target sequence ids.

    Fixed-width, zero-padded — confirmed by direct testing against the
    real installed proskomma-core that a plain incrementing "seq1",
    "seq2", ..., "seq10", "seq11" scheme causes real, silent data
    corruption: any id that is a literal string prefix of another
    (like "seq1" of "seq10"/"seq11"/...) gets resolved by the real
    library's graft-target lookup to the SHORTER id's content instead of
    its own — reproduced in a real multi-footnote document (10+ footnotes
    put 4 of them past the seq1/seq10+ collision point, and all 4
    silently rendered the seq1 footnote's text instead of their own; the
    Python decoder, having no such bug, decoded the SAME bytes correctly,
    which is what surfaced this as a real-library issue rather than an
    encoder bug). Real PKF content's own ids are random-looking hashes
    that essentially never collide this way — fixed-width padding
    reproduces that same never-a-prefix-of-another property deterministically.
    """
    def __init__(self):
        self._n = 0

    def next(self):
        self._n += 1
        return f"seq{self._n:06d}"


class Builder:
    def __init__(self):
        self.headers = {}
        self.book_code = None
        self.main_blocks = []
        self.extra_sequences = {}
        self._seq_ids = SeqIdGen()

        self._block_items = None
        self._block_tag = None

        # When inside a footnote/xref, redirect block output here instead
        # of main_blocks/current block.
        self._note_stack = []  # list of {'seq_id', 'type', 'blocks', 'block_items', 'block_tag'}
        self._char_stack = []  # nesting stack for \bd...\bd* etc: list of tag
        self._open_self_closing = None  # currently-open \fr/\fq/\xt-style self-closing field, if any
        self._open_wrapper_needs_close = None  # ('spanWithAtts'|'milestone', tag) pending synthetic close
        self._pending_chapter = None  # see add_chapter()

    # ---- block management ----

    def _current_items_list(self):
        if self._note_stack:
            return self._note_stack[-1]["block_items"]
        return self._block_items

    def _ensure_block(self, tag):
        if self._note_stack:
            note = self._note_stack[-1]
            if note["block_items"] is None:
                note["block_tag"] = tag
                note["block_items"] = []
            return
        if self._block_items is None:
            self._block_tag = tag
            self._block_items = []
            if self._pending_chapter is not None:
                # See add_chapter(): a chapter mark produces no output of
                # its own (only 'verses' marks do — the usfm mark action
                # ignores 'chapter') — it only steers the chapter-position
                # REPORT, which attaches \c N to the block CONTAINING the
                # mark. That must be the block textually AFTER \c in the
                # source (confirmed against real content: the report
                # algorithm's backward walk stops at the first preceding
                # paragraph block, which is always true here since every
                # block this package produces is type='paragraph' — so
                # wherever the mark's own block is, that's exactly where
                # \c N renders, with zero walk-back). Attaching it to the
                # block that was already open when \c appeared put \c one
                # block too early.
                self._block_items.append(["scope", "start", f"chapter/{self._pending_chapter}"])
                self._pending_chapter = None

    def _flush_block(self):
        if self._note_stack:
            note = self._note_stack[-1]
            if note["block_items"] is not None:
                note["blocks"].append({"bs": f"blockTag/{note['block_tag']}", "bg": [], "c": note["block_items"]})
            note["block_items"] = None
            note["block_tag"] = None
            return
        if self._block_items is not None:
            self.main_blocks.append({"bs": f"blockTag/{self._block_tag}", "bg": [], "c": self._block_items})
        self._block_items = None
        self._block_tag = None

    def start_para(self, tag):
        self._close_pending_note_char()
        self._flush_block()
        self._ensure_block(tag)

    def _append(self, item):
        items = self._current_items_list()
        if items is None:
            # Text/marks appearing before any explicit paragraph marker —
            # implicitly open a default \p block, matching how real USFM
            # content (almost) always starts a book with an explicit \p
            # anyway; this just tolerates the rare bare case.
            self.start_para("p")
            items = self._current_items_list()
        items.append(item)

    # ---- text ----

    def add_text(self, text):
        if not text:
            return
        if not text.strip() and self._current_items_list() is None:
            # Whitespace-only text (typically just the newline between two
            # header/marker lines) shouldn't itself open an implicit
            # paragraph — only real content should. Harmless to drop: the
            # decoder normalizes any whitespace run to a single space
            # anyway, so this text carried no signal even if kept.
            return
        # The succinct format's counted strings are length-prefixed with a
        # single byte, capping any one token's payload at 255 UTF-8 bytes
        # (confirmed for real: a real 389-byte verse-text run from actual
        # PKF content hit this during testing). Splitting one text run into
        # several tokens is lossless — the decoder concatenates every
        # token's payload directly with no separator (see
        # succinct_renderer.py's `_render_item`) — as long as the split
        # points don't add or drop any characters, which `_chunk_text`
        # guarantees by only ever splitting on whole characters.
        for chunk in _chunk_text(text):
            self._append(["token", "wordLike", chunk])

    # ---- chapter / verse ----

    def add_chapter(self, number):
        # Deferred — see _ensure_block(). Flush whatever block is currently
        # open so the mark lands in the NEXT one, matching real USFM layout
        # (\c always starts a fresh line/block) and the report algorithm's
        # actual attachment semantics.
        self._close_pending_note_char()
        self._flush_block()
        self._pending_chapter = number

    def add_verse(self, number):
        self._append(["scope", "start", f"verses/{number}"])

    # ---- character styles (\bd ... \bd*) ----

    def start_char(self, tag):
        self._close_pending_note_char()
        self._char_stack.append(tag)
        self._append(["scope", "start", f"span/{tag}"])

    def end_char(self, tag):
        if not self._char_stack or self._char_stack[-1] != tag:
            raise ValueError(f"Mismatched \\{tag}* — open character styles: {self._char_stack}")
        self._char_stack.pop()
        self._append(["scope", "end", f"span/{tag}"])

    # ---- note-internal fields (\fr \fq ... — no explicit close in USFM) ----
    #
    # Tracked independent of \note_stack (not per-note) because real content
    # decoded from real .pkf files sometimes has these appear with no
    # enclosing \f/\x at all (confirmed directly — a bare \xt citation with
    # no preceding \x, likely a genuine quirk of that source content, not a
    # decode bug). Rather than reject that as invalid, it's treated the same
    # as inside a note: a self-closing inline style, closed by the next
    # marker of any kind.

    def _close_pending_note_char(self):
        if self._open_self_closing:
            tag = self._open_self_closing
            self._append(["scope", "end", f"span/{tag}"])
            self._open_self_closing = None

    def start_note_char(self, tag):
        self._close_pending_note_char()
        self._append(["scope", "start", f"span/{tag}"])
        self._open_self_closing = tag

    def end_note_char(self, tag):
        # An explicit close (e.g. real content's \fv...\fv*) — just do the
        # same close early rather than waiting for the next marker. Not
        # validated against `tag` matching what's open: real content is
        # trusted here the same way unmatched-tag USFM generally is.
        self._close_pending_note_char()

    # ---- footnotes / cross-references ----

    def start_note(self, tag):
        self._close_pending_note_char()
        seq_type = NOTE_MARKERS[tag]
        seq_id = self._seq_ids.next()
        self._append(["graft", seq_type, seq_id])
        self._note_stack.append({
            "seq_id": seq_id, "type": seq_type, "blocks": [],
            "block_items": None, "block_tag": None,
        })
        self._ensure_block(tag)

    def end_note(self, tag):
        if not self._note_stack:
            raise ValueError(f"\\{tag}* with no open \\{tag}")
        self._close_pending_note_char()
        note = self._note_stack.pop()
        if note["block_items"] is not None:
            note["blocks"].append({"bs": f"blockTag/{note['block_tag']}", "bg": [], "c": note["block_items"]})
        self.extra_sequences[note["seq_id"]] = {"type": note["type"], "blocks": note["blocks"]}

    # ---- word-level attributes (\w ... \w*) ----

    def start_word(self, attrs):
        self._close_pending_note_char()
        if not attrs:
            self._char_stack.append("w")
            self._append(["scope", "start", "span/w"])
            return
        # Deliberately no attribute-start scopes here (unlike the milestone
        # case below they'd add nothing): the real renderer's startWrapper
        # action never reads an element's atts at all (confirmed directly —
        # see module docstring), so anything attached to the *opening*
        # container is silently discarded regardless. Only the *closing*
        # side's atts are ever rendered, via `_close_attributed_wrapper`.
        self._append(["scope", "start", "spanWithAtts/w"])
        self._open_wrapper_needs_close = ("spanWithAtts", "w", attrs)

    def end_word(self):
        pending = self._open_wrapper_needs_close
        if pending and pending[0] == "spanWithAtts" and pending[1] == "w":
            self._close_attributed_wrapper("spanWithAtts", "w", pending[2])
            self._open_wrapper_needs_close = None
        elif self._char_stack and self._char_stack[-1] == "w":
            self._char_stack.pop()
            self._append(["scope", "end", "span/w"])
        else:
            raise ValueError("\\w* with no open \\w")

    def _close_attributed_wrapper(self, kind, tag, attrs=None):
        # Synthetic trigger — see module docstring. This is the ONLY way a
        # spanWithAtts/milestone ever gets its closing tag emitted at all
        # (the real end scope is a structural no-op — see
        # succinct_renderer.py). It also happens to be the only place an
        # attribute ever gets rendered, for a real-library reason confirmed
        # by direct testing (not assumed): the renderer's attribute-end
        # handler only populates atts the FIRST time it sees one with no
        # open container; every attribute-start item on the OPENING side
        # gets silently discarded regardless. Net effect: only a single
        # key/value pair can round-trip through a \\w or milestone tag in
        # this pipeline — real content with more than one attribute will
        # keep only the first (documented v1 scope limitation, not a bug).
        if attrs:
            key, value = next(iter(attrs.items()))
            self._append(["scope", "end", f"attribute/{kind}/{tag}/{key}/0/{value}"])
        else:
            self._append(["scope", "end", f"attribute/{kind}/{tag}/_close/0/_close"])

    # ---- milestones (\zaln-s |atts\* ... \zaln-e\*) ----

    def start_milestone(self, tag, attrs):
        # Unlike \\w, a milestone's OPENING side does render atts (verified
        # directly: usfm_render.py's start_milestone action calls
        # _build_milestone(el.get("atts", {}), ...)) — and multiple
        # attribute-start items on an already-open container all
        # accumulate correctly (also verified directly), so real
        # multi-attribute milestones (x-content/x-lemma/x-strong/...)
        # round-trip in full, unlike \\w's single-attribute limit.
        self._close_pending_note_char()
        name = _MILESTONE_NAME.get(tag, tag)
        self._append(["scope", "start", f"milestone/{name}"])
        for key, value in attrs.items():
            self._append(["scope", "start", f"attribute/milestone/{name}/{key}/0/{value}"])
            self._append(["scope", "end", f"attribute/milestone/{name}/{key}/0/{value}"])
        self._open_wrapper_needs_close = ("milestone", name)

    def end_milestone(self, tag):
        name = _MILESTONE_NAME.get(tag, tag)
        if self._open_wrapper_needs_close != ("milestone", name):
            raise ValueError(f"\\{tag}-e with no matching open \\{tag}-s")
        # Bare trigger — end_milestone's own rendering never reads atts, so
        # there's nothing to carry through here (see module docstring).
        self._close_attributed_wrapper("milestone", name)
        self._open_wrapper_needs_close = None

    # ---- headers ----

    def set_header(self, tag, value):
        self.headers[tag] = value
        if tag == "id":
            self.book_code = value.split()[0].upper() if value.split() else None

    def finish(self):
        self._close_pending_note_char()
        self._flush_block()
        if self._note_stack:
            raise ValueError(f"Unclosed \\f or \\x at end of document (seq ids: {[n['seq_id'] for n in self._note_stack]})")
        if self._char_stack:
            raise ValueError(f"Unclosed character style(s) at end of document: {self._char_stack}")
        if self.book_code is None:
            raise ValueError("No \\id marker found — bookCode is required")
        self.headers["bookCode"] = self.book_code


def build(usfm_text):
    """usfm_text -> Builder (headers, book_code, main_blocks, extra_sequences)."""
    b = Builder()
    for tok in tokenize(usfm_text):
        if tok.kind == "header":
            b.set_header(tok.tag, tok.value)
        elif tok.kind == "chapter":
            b.add_chapter(tok.value)
        elif tok.kind == "verse":
            b.add_verse(tok.value)
        elif tok.kind == "para":
            b.start_para(tok.tag)
        elif tok.kind == "char_start":
            b.start_char(tok.tag)
        elif tok.kind == "char_end":
            b.end_char(tok.tag)
        elif tok.kind == "note_start":
            b.start_note(tok.tag)
        elif tok.kind == "note_end":
            b.end_note(tok.tag)
        elif tok.kind == "note_char_start":
            b.start_note_char(tok.tag)
        elif tok.kind == "note_char_end":
            b.end_note_char(tok.tag)
        elif tok.kind == "word_start":
            b.start_word(tok.attrs)
        elif tok.kind == "word_end":
            b.end_word()
        elif tok.kind == "milestone_start":
            b.start_milestone(tok.tag, tok.attrs)
        elif tok.kind == "milestone_end":
            b.end_milestone(tok.tag)
        elif tok.kind == "text":
            b.add_text(tok.value)
        else:
            raise ValueError(f"Unhandled token kind {tok.kind!r}")
    b.finish()
    return b
