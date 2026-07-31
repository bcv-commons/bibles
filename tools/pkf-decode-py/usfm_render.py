"""Port of the two action sets the ACTUALLY-INSTALLED proskomma-core@0.11.3's
document.usfm() runs (verified against the real minified bundle — see
succinct_renderer.py's docstring): calculateUsfmChapterPositionsActions$1
(report of which output block each chapter number attaches to) and
perf2UsfmActions (the USFM text itself), both driven directly by
SuccinctRenderer against the succinct docSet — NOT via an intermediate PERF
JSON tree walked by PerfRenderFromJson, despite that being what the older
proskomma-core/proskomma-json-tools source (and even proskomma-core's own
still-bundled-but-unused transforms/*.js) would suggest.
"""
import re

from succinct_renderer import SuccinctRenderer, _JS_WS_CHARS

_ONEIFY = {"toc", "toca", "mt", "imt", "s", "ms", "mte", "sd"}
_NO_END_TAG_WRAPPERS = {"fr", "fq", "fqa", "fk", "fl", "fw", "fp", "ft", "xo", "xk", "xq", "xt", "xta"}
_TRIM_NL_RE = re.compile("[" + re.escape(_JS_WS_CHARS) + "]*\n[" + re.escape(_JS_WS_CHARS) + "]*", re.MULTILINE)


def _oneify_tag(t):
    return t + "1" if t in _ONEIFY else t


def _subtype_tag(sub_type):
    # JS does `subType.split(':')[1]` and lets an out-of-range index return
    # `undefined` (no crash) rather than throw — happens for real for 'cell'
    # wrapper elements, whose subType is the bare string "cell" (no "usfm:"
    # prefix; see succinct_renderer.py's cell handling). `undefined` then
    # gets template-literal-coerced to the literal string "undefined" at the
    # point of use — reproduced verbatim here, not "fixed", to match
    # decode.mjs's real (odd) output byte-for-byte.
    parts = sub_type.split(":")
    return parts[1] if len(parts) > 1 else "undefined"


def _atts_str(value):
    # JS builds these with string concatenation, coercing an array value via
    # Array.prototype.toString() (== elements.join(',')) — matches for both
    # the x-morph-specific `.join(',')` call and every other key's implicit
    # coercion (atts values are always arrays here; see succinct_renderer.py).
    return ",".join(value) if isinstance(value, list) else str(value)


def _build_milestone(atts, type_):
    parts = [f"\\{type_}-s |"]
    for key, value in atts.items():
        parts.append(f'{_oneify_tag(key)}="{_atts_str(value)}" ')
    return "".join(parts) + "\\*"


def _build_end_wrapper(atts, type_, is_nested=False):
    parts = ["|"]
    for key, value in atts.items():
        parts.append(f'{_oneify_tag(key)}="{_atts_str(value)}" ')
    parts.append("\\")
    if is_nested:
        parts.append("+")
    parts.append(f"{type_}*")
    return "".join(parts)


# ---- calculateUsfmChapterPositions ----

def _initial_block_record(ctx, block_n):
    block = ctx["sequences"][0]["block"]
    return {"type": block["type"], "subType": block["subType"], "pos": block_n, "perfChapter": None}


def _report_actions():
    def start_paragraph(env):
        env["workspace"]["blockRecords"].append(
            _initial_block_record(env["context"], env["context"]["sequences"][0]["block"]["blockN"]))

    def block_graft(env):
        env["workspace"]["blockRecords"].append(
            _initial_block_record(env["context"], env["context"]["sequences"][0]["block"]["blockN"]))

    def mark(env):
        env["workspace"]["blockRecords"][-1]["perfChapter"] = env["context"]["sequences"][0]["element"]["atts"]["number"]

    def start_document(env):
        env["workspace"]["blockRecords"] = []
        env["output"]["report"] = {}

    def end_document(env):
        records = env["workspace"]["blockRecords"]
        report = env["output"]["report"]
        for record_n, record in enumerate(records):
            if record["perfChapter"] is None:
                continue
            usfm_chapter_pos = record_n
            found = False
            while usfm_chapter_pos > 0 and not found:
                prev = records[usfm_chapter_pos - 1]
                if prev["type"] == "paragraph" or prev["subType"] == "title":
                    found = True
                else:
                    usfm_chapter_pos -= 1
            report[str(usfm_chapter_pos)] = record["perfChapter"]

    return {
        "startDocument": [{"test": lambda env: True, "action": start_document}],
        "startParagraph": [{"test": lambda env: True, "action": start_paragraph}],
        "blockGraft": [{"test": lambda env: True, "action": block_graft}],
        "mark": [{"test": lambda env: env["context"]["sequences"][0]["element"].get("subType") == "chapter",
                   "action": mark}],
        "endDocument": [{"test": lambda env: True, "action": end_document}],
    }


def calculate_usfm_chapter_positions(doc, docset_id, selectors):
    renderer = SuccinctRenderer(doc, docset_id, selectors, _report_actions())
    output = renderer.render_document({})
    return output["report"]


# ---- perf2usfm ----

def _usfm_actions():
    def start_document(env):
        env["workspace"]["usfmBits"] = [""]
        env["workspace"]["nestedWrapper"] = 0
        doc_meta = env["context"]["document"]["metadata"]["document"]
        for key, value in doc_meta.items():
            if key in ("tags", "properties", "bookCode", "cl"):
                continue
            env["workspace"]["usfmBits"].append(f"\\{_oneify_tag(key)} {value}\n")

    def block_graft(env):
        seq0 = env["context"]["sequences"][0]
        sub_type = seq0["block"]["subType"]
        if sub_type not in ("title", "heading", "introduction"):
            return
        chapter_value = env["config"]["report"].get(str(seq0["block"]["blockN"]))
        target = seq0["block"].get("target")
        if chapter_value and seq0["type"] == "main":
            env["workspace"]["usfmBits"].append(f"\n\\c {chapter_value}\n")
        if target:
            env["context"]["renderer"].render_sequence_id(env, target)

    def inline_graft(env):
        target = env["context"]["sequences"][0]["element"].get("target")
        if target:
            env["context"]["renderer"].render_sequence_id(env, target)

    def _is_note_para(env):
        seq0 = env["context"]["sequences"][0]
        block = seq0["block"]
        return (block["subType"] == "usfm:f" and seq0["type"] == "footnote") or \
               (block["subType"] == "usfm:x" and seq0["type"] == "xref")

    def _is_note_subtype(env):
        return env["context"]["sequences"][0]["block"]["subType"] in ("usfm:f", "usfm:x")

    def start_paragraph_note(env):
        ws = env["workspace"]
        block = env["context"]["sequences"][0]["block"]
        ws["nestedWrapper"] = 0
        ws["usfmBits"].append(f"\\{_oneify_tag(_subtype_tag(block['subType']))} ")

    def start_paragraph_note_caller(env):
        env["workspace"]["nestedWrapper"] = 0

    def start_paragraph_general(env):
        ctx = env["context"]
        ws = env["workspace"]
        seq0 = ctx["sequences"][0]
        block = seq0["block"]
        ws["nestedWrapper"] = 0
        chapter_value = env["config"]["report"].get(str(block["blockN"]))
        if chapter_value and seq0["type"] == "main":
            ws["usfmBits"].append(f"\n\\c {chapter_value}\n")
        ws["usfmBits"].append(f"\n\\{_oneify_tag(_subtype_tag(block['subType']))}\n")

    def end_paragraph_note(env):
        block = env["context"]["sequences"][0]["block"]
        env["workspace"]["usfmBits"].append(f"\\{_oneify_tag(_subtype_tag(block['subType']))}*")

    def end_paragraph_note_caller(env):
        pass  # TODO in the original JS too — deliberately a no-op

    def end_paragraph_nl(env):
        env["workspace"]["usfmBits"].append("\n")

    def start_milestone(env):
        el = env["context"]["sequences"][0]["element"]
        env["workspace"]["usfmBits"].append(
            _build_milestone(el.get("atts", {}), _oneify_tag(_subtype_tag(el["subType"]))))

    def end_milestone(env):
        el = env["context"]["sequences"][0]["element"]
        env["workspace"]["usfmBits"].append(f"\\{_oneify_tag(_subtype_tag(el['subType']))}-e\\*")

    def text(env):
        env["workspace"]["usfmBits"].append(env["context"]["sequences"][0]["element"]["text"])

    def mark(env):
        el = env["context"]["sequences"][0]["element"]
        if el.get("subType") == "verses":
            env["workspace"]["usfmBits"].append(f"\n\\v {el['atts']['number']}\n")

    def end_sequence(env):
        doc_meta = env["context"]["document"]["metadata"]["document"]
        if doc_meta.get("cl") and env["context"]["sequences"][0]["type"] == "title":
            env["workspace"]["usfmBits"].append(f"\n\\cl {doc_meta['cl']}\n")

    def start_wrapper(env):
        ws = env["workspace"]
        el = env["context"]["sequences"][0]["element"]
        tag = _oneify_tag(_subtype_tag(el["subType"]))
        if ws["nestedWrapper"] > 0:
            ws["usfmBits"].append(f"\\+{tag} ")
        else:
            ws["usfmBits"].append(f"\\{tag} ")
        ws["nestedWrapper"] += 1

    def end_wrapper_tagged(env):
        ws = env["workspace"]
        ws["nestedWrapper"] -= 1
        el = env["context"]["sequences"][0]["element"]
        sub_type = _subtype_tag(el["subType"])
        is_nested = ws["nestedWrapper"] > 0
        if sub_type == "w":
            ws["usfmBits"].append(_build_end_wrapper(el.get("atts", {}), _oneify_tag(sub_type), is_nested))
        else:
            tag = _oneify_tag(sub_type)
            ws["usfmBits"].append(f"\\+{tag}*" if is_nested else f"\\{tag}*")

    def end_wrapper_untagged(env):
        env["workspace"]["nestedWrapper"] -= 1

    def end_wrapper_tag_test(env):
        sub_type = _subtype_tag(env["context"]["sequences"][0]["element"]["subType"])
        return sub_type not in _NO_END_TAG_WRAPPERS

    def end_document(env):
        joined = "".join(env["workspace"]["usfmBits"])
        env["output"]["usfm"] = _TRIM_NL_RE.sub("\n", joined)

    return {
        "startDocument": [{"test": lambda env: True, "action": start_document}],
        "blockGraft": [{"test": lambda env: True, "action": block_graft}],
        "inlineGraft": [{"test": lambda env: True, "action": inline_graft}],
        "startParagraph": [
            {"test": _is_note_para, "action": start_paragraph_note},
            {"test": _is_note_subtype, "action": start_paragraph_note_caller},
            {"test": lambda env: True, "action": start_paragraph_general},
        ],
        "endParagraph": [
            {"test": _is_note_para, "action": end_paragraph_note},
            {"test": _is_note_subtype, "action": end_paragraph_note_caller},
            {"test": lambda env: True, "action": end_paragraph_nl},
        ],
        "startMilestone": [{"test": lambda env: True, "action": start_milestone}],
        "endMilestone": [{"test": lambda env: True, "action": end_milestone}],
        "text": [{"test": lambda env: True, "action": text}],
        "mark": [{"test": lambda env: True, "action": mark}],
        "endSequence": [{"test": lambda env: env["context"]["document"]["metadata"]["document"].get("cl") is not None
                          and env["context"]["sequences"][0]["type"] == "title", "action": end_sequence}],
        "startWrapper": [{"test": lambda env: True, "action": start_wrapper}],
        "endWrapper": [
            {"test": end_wrapper_tag_test, "action": end_wrapper_tagged},
            {"test": lambda env: True, "action": end_wrapper_untagged},
        ],
        "endDocument": [{"test": lambda env: True, "action": end_document}],
    }


def perf2usfm(doc, docset_id, selectors, report):
    renderer = SuccinctRenderer(doc, docset_id, selectors, _usfm_actions())
    output = renderer.render_document({"report": report})
    return output["usfm"]
