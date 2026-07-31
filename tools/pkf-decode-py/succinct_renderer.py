"""Port of the ACTUALLY-INSTALLED proskomma-core@0.11.3's PerfRenderFromProskomma
(bundled inline in its dist, verified by reading the real minified bundle —
it differs from the readable proskomma-core@0.10.6/proskomma-json-tools@0.8.22-beta
checkout available locally, which is a stale, unrelated version).

Critically, `document.usfm()` in the installed version does NOT build a PERF
JSON tree and then walk it (unlike `document.perf()`, which still does, via
identityActions below). It runs THIS renderer directly against the succinct
docSet TWICE, with two different action sets (report-computation, then
usfm-text-generation) — see usfm_render.py. That matters for byte-for-byte
correctness: a pending word-attribute-wrapper "container" that never gets an
explicit close (because `renderItem`'s spanWithAtts-end branch is a no-op —
see below, ported faithfully) is silently dropped when driven this way,
whereas going via an intermediate PERF-JSON tree would have structurally
forced a close. Confirmed by direct experiment against the real installed
package (dumping and diffing intermediate state) before writing this port —
do not "fix" this dropped-close behavior; it must match byte-for-byte.

The walker mechanics (renderSequenceId/renderContent/renderItem/
maybeRenderText/renderContainer) are NOT pluggable — same as the real
PerfRenderFromProskomma, only the renderEvent()-dispatched actions are.
"""
import re

# JS's regex `\s` is NOT the same set as Python's Unicode-aware `\s` — most
# notably it includes U+FEFF (BOM/zero-width no-break space, per ECMA-262's
# WhiteSpace production) which Python's `\s` does not match at all, and
# excludes U+0085 (NEL) which Python's does match. Spelled out explicitly
# (ECMA-262 WhiteSpace + LineTerminator) rather than relying on either
# language's built-in `\s` — confirmed needed against real data: a token in a real corpus file (apb) carries a leading U+FEFF
# that JS's token-normalization collapses to a space but Python's silently
# passed through, byte-diffing the output.
_JS_WS_CODEPOINTS = [
    0x09, 0x0B, 0x0C, 0x20, 0xA0, 0x1680,
    *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF,
    0x0A, 0x0D,
]
_JS_WS_CHARS = "".join(chr(c) for c in _JS_WS_CODEPOINTS)
_WS_RE = re.compile("[" + re.escape(_JS_WS_CHARS) + "]+")


def _camel_to_snake(s):
    out = []
    for c in s:
        if c.isupper():
            out.append("_" + c.lower())
        else:
            out.append(c)
    return "".join(out)


class SuccinctRenderer:
    def __init__(self, doc, docset_id, selectors, actions):
        self.doc = doc
        self.docset_id = docset_id
        self.selectors = selectors
        self.actions = actions
        self._tokens = []
        self._container = None

    def render_document(self, config):
        context = {"renderer": self}
        workspace = {}
        output = {}
        context["document"] = {
            "id": None,
            "schema": {
                "structure": "flat",
                "structure_version": "0.2.1",
                "constraints": [{"name": "perf", "version": "0.2.1"}],
            },
            "metadata": {
                "translation": {
                    "id": self.docset_id,
                    "selectors": self.selectors,
                    "properties": {},
                    "tags": [],
                },
                "document": {**self.doc["headers"], "properties": {}, "tags": []},
            },
            "mainSequenceId": self.doc["mainId"],
        }
        context["sequences"] = []
        env = {"config": config, "context": context, "workspace": workspace, "output": output}
        self._render_event("startDocument", env)
        self.render_sequence_id(env, self.doc["mainId"])
        self._render_event("endDocument", env)
        return output

    def render_sequence_id(self, env, sequence_id):
        context = env["context"]
        sequence = self.doc["sequences"][sequence_id]
        seq_ctx = {"id": sequence_id, "type": sequence["type"]}
        context["sequences"].insert(0, seq_ctx)
        self._render_event("startSequence", env)

        output_block_n = 0
        for block in sequence["blocks"]:
            for block_graft in block["bg"]:
                seq_ctx["block"] = {
                    "type": "graft",
                    "subType": _camel_to_snake(block_graft[1]),
                    "blockN": output_block_n,
                    "target": block_graft[2],
                    "isNew": False,
                }
                self._render_event("blockGraft", env)
                output_block_n += 1

            bs_label = block["bs"][2]
            sub_type_values = bs_label.split("/")
            if len(sub_type_values) > 1 and sub_type_values[1] in ("tr", "zrow"):
                sub_type_value = "usfm:tr" if sub_type_values[1] == "tr" else "pk"
            elif len(sub_type_values) > 1:
                sub_type_value = f"usfm:{sub_type_values[1]}"
            else:
                sub_type_value = sub_type_values[0]

            seq_ctx["block"] = {
                "type": "row" if sub_type_value in ("usfm:tr", "pk") else "paragraph",
                "subType": sub_type_value,
                "blockN": output_block_n,
                "wrappers": [],
            }
            # The real engine compares `sub_type_value === "row"` here — but
            # sub_type_value is never actually "row" (it's "usfm:tr"/"pk"/
            # "usfm:X"; only block["type"] above gets set to "row"). That
            # comparison is therefore always false, so startRow/endRow never
            # fire in practice — row blocks silently go through
            # startParagraph/endParagraph instead (confirmed against real
            # output: a `blockTag/tr` block's boundary literally renders as
            # "\tr" via the generic startParagraph fallback). Replicated
            # verbatim, not fixed.
            self._render_event("startParagraph", env)
            self._tokens = []
            self._render_content(block["c"], env)
            self._tokens = []
            self._render_event("endParagraph", env)
            del seq_ctx["block"]
            output_block_n += 1

        self._render_event("endSequence", env)
        context["sequences"].pop(0)

    def _render_content(self, items, env):
        for item in items:
            self._render_item(item, env)
        self._maybe_render_text(env)

    def _render_item(self, item, env):
        item_type, item_sub, payload = item[0], item[1], item[2]
        context = env["context"]
        seq0 = context["sequences"][0]

        if item_type == "scope" and payload.startswith("attribute"):
            scope_bits = payload.split("/")
            if item_sub == "start":
                if self._container is None:
                    self._container = {"direction": "start", "subType": "usfm:w", "type": "wrapper", "atts": {}}
                self._container["atts"].setdefault(scope_bits[3], []).append(scope_bits[5])
            else:
                if self._container is None:
                    self._container = {"direction": "end", "subType": f"usfm:{_camel_to_snake(scope_bits[2])}", "atts": {}}
                    if scope_bits[1] == "milestone":
                        self._container["type"] = "end_milestone"
                    else:
                        self._container["type"] = "wrapper"
                        self._container["atts"].setdefault(scope_bits[3], []).append(scope_bits[5])
            return

        if self._container is not None:
            self._maybe_render_text(env)
            self._render_container(env)

        if item_type == "token":
            self._tokens.append(_WS_RE.sub(" ", payload))
            return

        if item_type == "graft":
            self._maybe_render_text(env)
            graft = {"type": "graft", "subType": _camel_to_snake(item_sub), "target": payload, "isNew": False}
            seq0["element"] = graft
            self._render_event("inlineGraft", env)
            del seq0["element"]
            return

        # scope
        self._maybe_render_text(env)
        scope_bits = payload.split("/")
        head = scope_bits[0]
        if head in ("chapter", "verses", "pubChapter", "pubVerse", "altChapter", "altVerse"):
            if item_sub == "start":
                mark = {"type": "mark", "subType": _camel_to_snake(head), "atts": {"number": scope_bits[1]}}
                seq0["element"] = mark
                self._render_event("mark", env)
                del seq0["element"]
        elif head == "span":
            wrapper = {"type": "wrapper", "subType": f"usfm:{scope_bits[1]}", "atts": {}}
            seq0["element"] = wrapper
            if item_sub == "start":
                seq0["block"]["wrappers"].insert(0, wrapper["subType"])
                self._render_event("startWrapper", env)
            else:
                self._render_event("endWrapper", env)
                seq0["block"]["wrappers"].pop(0)
            del seq0["element"]
        elif head == "spanWithAtts":
            if item_sub == "start":
                self._container = {"direction": "start", "type": "wrapper", "subType": f"usfm:{scope_bits[1]}", "atts": {}}
            # No 'else' branch for 'end' — matches the real engine exactly:
            # spanWithAtts' end scope is silently a no-op here.
        elif head == "cell":
            wrapper = {
                "direction": "start", "type": "wrapper", "subType": head,
                "atts": {"role": scope_bits[1], "alignment": scope_bits[2], "nCols": int(scope_bits[3])},
            }
            seq0["element"] = wrapper
            if item_sub == "start":
                seq0["block"]["wrappers"].insert(0, wrapper["subType"])
                self._render_event("startWrapper", env)
            else:
                self._render_event("endWrapper", env)
                seq0["block"]["wrappers"].pop(0)
            del seq0["element"]
        elif head == "milestone" and item_sub == "start":
            if scope_bits[1] == "ts":
                mark = {"type": "mark", "subType": f"usfm:{_camel_to_snake(scope_bits[1])}", "atts": {}}
                seq0["element"] = mark
                self._render_event("mark", env)
                del seq0["element"]
            else:
                self._container = {"type": "start_milestone", "subType": f"usfm:{_camel_to_snake(scope_bits[1])}", "atts": {}}

    def _maybe_render_text(self, env):
        if not self._tokens:
            return
        el_ctx = {"type": "text", "text": "".join(self._tokens)}
        self._tokens = []
        env["context"]["sequences"][0]["element"] = el_ctx
        self._render_event("text", env)
        del env["context"]["sequences"][0]["element"]

    def _render_container(self, env):
        c = self._container
        seq0 = env["context"]["sequences"][0]
        if c["type"] == "wrapper":
            direction = c.pop("direction")
            seq0["element"] = c
            if direction == "start":
                seq0["block"]["wrappers"].insert(0, c["subType"])
                self._render_event("startWrapper", env)
            else:
                self._render_event("endWrapper", env)
                seq0["block"]["wrappers"].pop(0)
            del seq0["element"]
        elif c["type"] == "start_milestone":
            seq0["element"] = c
            self._render_event("startMilestone", env)
            del seq0["element"]
        elif c["type"] == "end_milestone":
            seq0["element"] = c
            self._render_event("endMilestone", env)
            del seq0["element"]
        self._container = None

    def _render_event(self, event, env):
        for handler in self.actions.get(event, []):
            if handler["test"](env):
                handler["action"](env)
                break
