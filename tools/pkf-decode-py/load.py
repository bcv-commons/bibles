"""Port of the succinct-loading slice of proskomma-core's index.js
(loadSuccinctDocSet/newDocumentFromSuccinct) + model/doc_set.js
(fromSuccinct) — only the fields decode.mjs's actual GraphQL query shape
reads (see unsuccinctify.py's docstring): per block, only `bs`/`bg`/`c`;
`nt`/`os`/`is` are decoded by proskomma-core too but never queried by
PerfRenderFromProskomma's `blocks(...)` selection, so they're skipped here.
"""
import gzip
import json

from byte_array import ByteArray
import succinct as succ
import unsuccinctify as uns


def _populated_byte_array(b64):
    ba = ByteArray()
    ba.from_base64(b64)
    return ba


def load_pkf(pkf_bytes):
    """pkf_bytes -> {docset_id, selectors, docs: {docId: {headers, mainId, sequences}}}"""
    succinct_ob = json.loads(gzip.decompress(pkf_bytes))

    enums = {
        category: _populated_byte_array(succinct_ob["enums"][category])
        for category in ("ids", "wordLike", "notWordLike", "scopeBits", "graftTypes")
    }
    enum_idx = succ.enum_indexes(enums)

    docs = {}
    for doc_id, succinct_doc in succinct_ob["docs"].items():
        sequences = {}
        for seq_id, seq in succinct_doc["sequences"].items():
            blocks = []
            for succinct_block in seq["blocks"]:
                bs_ba = _populated_byte_array(succinct_block["bs"])
                bg_ba = _populated_byte_array(succinct_block["bg"])
                c_ba = _populated_byte_array(succinct_block["c"])
                blocks.append({
                    "bs": uns.unsuccinctify_block_scope(enums, enum_idx, bs_ba),
                    "bg": uns.unsuccinctify_grafts(enums, enum_idx, bg_ba),
                    "c": uns.unsuccinctify_items(enums, enum_idx, c_ba),
                })
            sequences[seq_id] = {"type": seq["type"], "blocks": blocks}
        docs[doc_id] = {
            "headers": succinct_doc["headers"],
            "mainId": succinct_doc["mainId"],
            "sequences": sequences,
        }

    return {
        "docset_id": succinct_ob["id"],
        "selectors": succinct_ob["metadata"]["selectors"],
        "docs": docs,
    }
