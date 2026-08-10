"""Assembles a Builder's output (usfm_to_items.py) into the full pkf JSON
structure and gzip-compresses it — the write-side counterpart of
../pkf-decode-py/load.py.
"""
import gzip
import json

from byte_array import ByteArray
from enum_builder import Enums
import succinct_write as sw


def _write_item(ba, enums, item):
    kind = item[0]
    if kind == "token":
        sw.push_token(ba, enums, item[1], item[2])
    elif kind == "scope":
        label = item[2]
        scope_type, _, rest = label.partition("/")
        components = rest.split("/") if rest else []
        sw.push_scope(ba, enums, item[1] == "start", scope_type, components)
    elif kind == "graft":
        sw.push_graft(ba, enums, item[1], item[2])
    else:
        raise ValueError(f"Unknown item kind {kind!r}")


def _encode_block(enums, bs_label, bg, c_items):
    bs_ba = ByteArray()
    scope_type, _, rest = bs_label.partition("/")
    sw.push_scope(bs_ba, enums, True, scope_type, rest.split("/") if rest else [])

    bg_ba = ByteArray()
    for graft_type, target_seq_id in bg:
        sw.push_graft(bg_ba, enums, graft_type, target_seq_id)

    c_ba = ByteArray()
    for item in c_items:
        _write_item(c_ba, enums, item)

    nt_ba = ByteArray()
    nt_ba.push_n_byte(0)

    return {
        "bs": bs_ba.base64(),
        "bg": bg_ba.base64(),
        "c": c_ba.base64(),
        "os": ByteArray().base64(),
        "is": ByteArray().base64(),
        "nt": nt_ba.base64(),
    }


def build_pkf_bytes(builder, lang, abbr, docset_id=None):
    """builder: usfm_to_items.Builder (already .finish()ed).
    lang/abbr: the docSet's selectors (e.g. iso 639-3 code, version abbr).
    Returns gzip-compressed bytes ready to write as a .pkf file.
    """
    enums = Enums()

    main_seq_id = "main"
    main_blocks = [_encode_block(enums, b["bs"], b["bg"], b["c"]) for b in builder.main_blocks]

    sequences = {
        main_seq_id: {
            "type": "main",
            "tags": [],
            "blocks": main_blocks,
            # Empty is sufficient — the real library only requires these
            # keys to exist for a 'main' sequence to load; the chapter/verse
            # random-access index they'd normally hold is not needed for
            # document.usfm() rendering (see this package's README).
            "chapters": {},
            "chapterVerses": {},
            # Also required at load time (confirmed directly against the
            # real installed library, which throws "tokensPresent not
            # found in main sequence" otherwise — an older, non-matching
            # proskomma-core checkout had suggested this was optional,
            # same trap as during the decode work). "0x0" (empty bitset)
            # is fine: like chapters/chapterVerses above, this is a
            # random-access index document.usfm() rendering never reads.
            "tokensPresent": "0x0",
        }
    }
    for seq_id, seq in builder.extra_sequences.items():
        blocks = [_encode_block(enums, b["bs"], b["bg"], b["c"]) for b in seq["blocks"]]
        sequences[seq_id] = {"type": seq["type"], "tags": [], "blocks": blocks}

    doc_id = "doc1"
    pkf = {
        "id": docset_id or f"{lang}_{abbr}",
        "metadata": {"selectors": {"lang": lang, "abbr": abbr}},
        "enums": enums.finalize(),
        "docs": {
            doc_id: {
                "headers": builder.headers,
                "mainId": main_seq_id,
                "sequences": sequences,
            }
        },
        "tags": [],
    }

    raw = json.dumps(pkf, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return gzip.compress(raw)
