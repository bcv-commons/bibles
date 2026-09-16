"""A second SuccinctRenderer action set (alongside ../pkf-decode-py's
usfm_render.py `_usfm_actions()`) that builds a USJ (Unified Scripture
JSON, https://github.com/usfm-bible/usj) tree instead of raw USFM text —
final text generation is then handed off to `usfmtc` (usjtousx + usx2usfm)
in decode.py, rather than this package's own hand-rolled string-building.

Reuses ../pkf-decode-py's SuccinctRenderer walking engine and
calculate_usfm_chapter_positions() UNCHANGED (imported, not copied) — only
the *actions* (what happens on each render event) differ. See that
package's succinct_renderer.py for the real-library quirks this walk
already reproduces (spanWithAtts/milestone close semantics, \\w's
single-attribute limit, etc.) — none of that changes here, since this
module never touches the succinct bytes directly, only the same
higher-level render events usfm_render.py already consumes.

Structural notes specific to USJ output (things that don't matter for
flat-text rendering but do matter for a tree):

- A footnote/cross-reference (\\f ... \\f* / \\x ... \\x*) is, in this
  succinct model, a SINGLE block (subType "usfm:f"/"usfm:x") — \\fr/\\fq/
  \\ft etc are NOT separate blocks, they're character-style WRAPPERS
  nested inside that one block (confirmed directly: they're in
  _NO_END_TAG_WRAPPERS, the same set usfm_render.py uses for
  startWrapper/endWrapper). So the USJ "note" node is created once, at
  inlineGraft time (before recursing into the footnote's own
  sub-sequence), and the wrapper events for fr/ft etc simply append "char"
  children to it — no separate note-block handling needed beyond
  capturing the leading caller text (e.g. "+") before the first wrapper
  opens.
- Milestones (\\zaln-s/\\zaln-e) are flat siblings in USJ (type "ms"), not
  containers — matches this succinct model already (start/end scopes with
  no intervening content-list push), see _render_item's 'milestone' head.
- Table rows/cells fall through to the generic paragraph/wrapper handling
  below (marker "tr"/"cell") — same as this repo's other USFM tooling,
  tables are out of scope for v1 (see ../pkf-encode-py/README.md).
"""

_ONEIFY = {"toc", "toca", "mt", "imt", "s", "ms", "mte", "sd"}

# A graft item's own subType is "footnote"/"xref" (see encode's usfm_lexer.py
# NOTE_MARKERS = {"f": "footnote", "x": "xref"}) — NOT colon-prefixed like a
# wrapper/paragraph subType ("usfm:f"), so _subtype_tag() doesn't apply here.
_GRAFT_MARKER = {"footnote": "f", "xref": "x"}


def _oneify_tag(t):
    return t + "1" if t in _ONEIFY else t


def _subtype_tag(sub_type):
    parts = sub_type.split(":")
    return parts[1] if len(parts) > 1 else "undefined"


def _atts_flat(atts):
    """{key: [values...]} -> {key: joined-value} — mirrors usfm_render.py's
    _atts_str's array-join behavior (real atts values are always lists,
    from repeated attribute-start scope entries)."""
    return {k: (",".join(v) if isinstance(v, list) else str(v)) for k, v in atts.items()}


def _usj_actions():
    def start_document(env):
        ws = env["workspace"]
        doc_meta = env["context"]["document"]["metadata"]["document"]
        book_code = doc_meta.get("bookCode")
        id_value = doc_meta.get("id", book_code or "")
        rest = id_value[len(book_code):].strip() if book_code and id_value.startswith(book_code) else ""

        usj = {"type": "USJ", "version": "3.0", "content": []}
        usj["content"].append({
            "type": "book", "marker": "id", "code": book_code,
            "content": [rest] if rest else [],
        })
        for key, value in doc_meta.items():
            if key in ("tags", "properties", "bookCode", "cl", "id"):
                continue
            usj["content"].append({"type": "para", "marker": _oneify_tag(key), "content": [value]})

        ws["usj"] = usj
        ws["stack"] = [usj["content"]]
        ws["capturing_caller"] = False
        ws["note_stack"] = []

    def block_graft(env):
        seq0 = env["context"]["sequences"][0]
        sub_type = seq0["block"]["subType"]
        if sub_type not in ("title", "heading", "introduction"):
            return
        ws = env["workspace"]
        chapter_value = env["config"]["report"].get(str(seq0["block"]["blockN"]))
        target = seq0["block"].get("target")
        if chapter_value and seq0["type"] == "main":
            ws["stack"][-1].append({"type": "chapter", "marker": "c", "number": str(chapter_value)})
        if target:
            env["context"]["renderer"].render_sequence_id(env, target)

    def inline_graft(env):
        el = env["context"]["sequences"][0]["element"]
        target = el.get("target")
        if not target:
            return
        ws = env["workspace"]
        subtype = el["subType"]
        if subtype in _GRAFT_MARKER:
            node = {"type": "note", "marker": _GRAFT_MARKER[subtype], "caller": "", "content": []}
            ws["stack"][-1].append(node)
            ws["stack"].append(node["content"])
            ws["note_stack"].append(node)
            env["context"]["renderer"].render_sequence_id(env, target)
            ws["stack"].pop()
            popped = ws["note_stack"].pop()
            popped["caller"] = popped["caller"].strip()
        else:
            # A "noteCaller" graft (real, confirmed against actual content):
            # not a footnote/xref itself, just a nested sub-sequence whose
            # own plain text IS the caller symbol (e.g. "+") for the
            # currently-open note above. That nested sequence's one block
            # shares the same "usfm:f"/"usfm:x" subType as a real note
            # block, so recursing plainly re-fires start_paragraph_note ->
            # text() -> capturing_caller, landing the symbol in the SAME
            # still-open note's "caller" with no new USJ node needed here.
            env["context"]["renderer"].render_sequence_id(env, target)

    def _is_note_block(env):
        return env["context"]["sequences"][0]["block"]["subType"] in ("usfm:f", "usfm:x")

    def start_paragraph_note(env):
        env["workspace"]["capturing_caller"] = True

    def start_paragraph_general(env):
        ctx, ws = env["context"], env["workspace"]
        seq0 = ctx["sequences"][0]
        block = seq0["block"]
        chapter_value = env["config"]["report"].get(str(block["blockN"]))
        if chapter_value and seq0["type"] == "main":
            ws["stack"][-1].append({"type": "chapter", "marker": "c", "number": str(chapter_value)})
        node = {"type": "para", "marker": _oneify_tag(_subtype_tag(block["subType"])), "content": []}
        ws["stack"][-1].append(node)
        ws["stack"].append(node["content"])

    def end_paragraph_note(env):
        env["workspace"]["capturing_caller"] = False

    def end_paragraph_general(env):
        env["workspace"]["stack"].pop()

    def start_milestone(env):
        el = env["context"]["sequences"][0]["element"]
        tag = _oneify_tag(_subtype_tag(el["subType"]))
        node = {"type": "ms", "marker": f"{tag}-s"}
        node.update(_atts_flat(el.get("atts", {})))
        env["workspace"]["stack"][-1].append(node)

    def end_milestone(env):
        el = env["context"]["sequences"][0]["element"]
        tag = _oneify_tag(_subtype_tag(el["subType"]))
        env["workspace"]["stack"][-1].append({"type": "ms", "marker": f"{tag}-e"})

    def text(env):
        ws = env["workspace"]
        value = env["context"]["sequences"][0]["element"]["text"]
        if ws["capturing_caller"]:
            ws["note_stack"][-1]["caller"] += value
            return
        ws["stack"][-1].append(value)

    def mark(env):
        el = env["context"]["sequences"][0]["element"]
        if el.get("subType") == "verses":
            env["workspace"]["stack"][-1].append(
                {"type": "verse", "marker": "v", "number": str(el["atts"]["number"])})

    def end_sequence(env):
        doc_meta = env["context"]["document"]["metadata"]["document"]
        ws = env["workspace"]
        if doc_meta.get("cl") and env["context"]["sequences"][0]["type"] == "title":
            ws["stack"][-1].append({"type": "para", "marker": "cl", "content": [doc_meta["cl"]]})

    def start_wrapper(env):
        ws = env["workspace"]
        el = env["context"]["sequences"][0]["element"]
        tag = _oneify_tag(_subtype_tag(el["subType"]))
        node = {"type": "char", "marker": tag, "content": []}
        node.update(_atts_flat(el.get("atts", {})))
        ws["stack"][-1].append(node)
        ws["stack"].append(node["content"])
        # First wrapper (fr/fq/ft/...) inside a note ends caller-capture,
        # same as end_paragraph_note would — a note's caller text always
        # comes before its first field wrapper.
        ws["capturing_caller"] = False

    def end_wrapper(env):
        env["workspace"]["stack"].pop()

    def end_document(env):
        env["output"]["usj"] = env["workspace"]["usj"]

    return {
        "startDocument": [{"test": lambda env: True, "action": start_document}],
        "blockGraft": [{"test": lambda env: True, "action": block_graft}],
        "inlineGraft": [{"test": lambda env: True, "action": inline_graft}],
        "startParagraph": [
            {"test": _is_note_block, "action": start_paragraph_note},
            {"test": lambda env: True, "action": start_paragraph_general},
        ],
        "endParagraph": [
            {"test": _is_note_block, "action": end_paragraph_note},
            {"test": lambda env: True, "action": end_paragraph_general},
        ],
        "startMilestone": [{"test": lambda env: True, "action": start_milestone}],
        "endMilestone": [{"test": lambda env: True, "action": end_milestone}],
        "text": [{"test": lambda env: True, "action": text}],
        "mark": [{"test": lambda env: True, "action": mark}],
        "endSequence": [{"test": lambda env: env["context"]["document"]["metadata"]["document"].get("cl") is not None
                          and env["context"]["sequences"][0]["type"] == "title", "action": end_sequence}],
        "startWrapper": [{"test": lambda env: True, "action": start_wrapper}],
        "endWrapper": [{"test": lambda env: True, "action": end_wrapper}],
        "endDocument": [{"test": lambda env: True, "action": end_document}],
    }


def perf2usj(doc, docset_id, selectors, report):
    # Local import to avoid a hard import-order dependency at module load
    # time — decode.py puts ../pkf-decode-py on sys.path before importing
    # this module's caller, but importing SuccinctRenderer at *this*
    # module's top level would require that path to already be set up
    # before usj_render itself is ever imported.
    from succinct_renderer import SuccinctRenderer
    renderer = SuccinctRenderer(doc, docset_id, selectors, _usj_actions())
    output = renderer.render_document({"report": report})
    return output["usj"]
