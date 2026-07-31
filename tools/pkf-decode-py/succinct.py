"""Port of proskomma-core's util/succinct.js — reading only (no push*/write
helpers, decode.mjs's call path never writes succinct data).

Note: scopeDefs.js's labelForScope()/nComponentsForScope() split matters here
only for nComponentsForScope — labelForScope itself is a *write*-side helper
(splits a label string into components when encoding); on the read side,
succinctScopeLabel() below reconstructs the label directly from the stored
scopeBits enum indices, so labelForScope is never called during decode.
"""
import defs


def header_bytes(succinct, pos):
    header_byte = succinct.byte(pos)
    item_type = header_byte >> 6
    item_length = header_byte & 0x3F
    item_subtype = succinct.byte(pos + 1)
    return item_length, item_type, item_subtype


def enum_index(enum_succinct):
    index = []
    pos = 0
    while pos < enum_succinct.length:
        index.append(pos)
        string_length = enum_succinct.byte(pos)
        pos += string_length + 1
    return index


def enum_indexes(enums):
    return {category: enum_index(succinct) for category, succinct in enums.items()}


def succinct_token_chars(enums, enum_idx, succinct, item_subtype, pos):
    item_category = defs.TOKEN_CATEGORY[defs.TOKEN_ENUM_LABELS[item_subtype]]
    item_index = enum_idx[item_category][succinct.n_byte(pos + 2)]
    return enums[item_category].counted_string(item_index)


def succinct_scope_label(enums, enum_idx, succinct, item_subtype, pos):
    scope_type = defs.SCOPE_ENUM_LABELS[item_subtype]
    n_scope_bits = defs.n_components_for_scope(scope_type)
    offset = 2
    scope_bits = ""
    while n_scope_bits > 1:
        item_index_index = succinct.n_byte(pos + offset)
        item_index = enum_idx["scopeBits"][item_index_index]
        scope_bit_string = enums["scopeBits"].counted_string(item_index)
        scope_bits += f"/{scope_bit_string}"
        offset += succinct.n_byte_length(item_index_index)
        n_scope_bits -= 1
    return f"{scope_type}{scope_bits}"


def succinct_scope_type(item_subtype):
    return defs.SCOPE_ENUM_LABELS[item_subtype]


def succinct_graft_name(enums, enum_idx, item_subtype):
    graft_index = enum_idx["graftTypes"][item_subtype]
    return enums["graftTypes"].counted_string(graft_index)


def succinct_graft_seq_id(enums, enum_idx, succinct, pos):
    seq_index = enum_idx["ids"][succinct.n_byte(pos + 2)]
    return enums["ids"].counted_string(seq_index)
