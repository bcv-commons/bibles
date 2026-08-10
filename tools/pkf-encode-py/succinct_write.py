"""Write-side counterpart to ../pkf-decode-py/succinct.py — port of
proskomma-core's util/succinct.js push* functions (pushSuccinctTokenBytes,
pushSuccinctScopeBytes, pushSuccinctGraftBytes). The header-byte patching
pattern (write a placeholder length byte, append the item body, then patch
the placeholder once the final length is known) is load-bearing — the
6-bit length field means a single item's total encoding is capped at 63
bytes.
"""
import defs


def push_token(c: "ByteArray", enums, sub_type, chars):
    length_pos = c.length
    c.push_byte(0)  # placeholder
    c.push_byte(defs.TOKEN_ENUM[sub_type])
    category = defs.TOKEN_CATEGORY[sub_type]
    char_index = enums.by_category(category).get_index(chars)
    c.push_n_byte(char_index)
    item_length = c.length - length_pos
    if item_length > 63:
        raise ValueError(f"Token item exceeds 63-byte succinct length limit ({item_length} bytes)")
    c.set_byte(length_pos, item_length | (defs.ITEM_ENUM["token"] << 6))


def push_scope(c: "ByteArray", enums, is_start, scope_type, components):
    """components: the scope label's fields after the type itself, e.g. for
    payload 'chapter/5' -> scope_type='chapter', components=['5']."""
    n_components = defs.n_components_for_scope(scope_type)
    if len(components) != n_components - 1:
        raise ValueError(f"Scope '{scope_type}' expects {n_components - 1} component(s), got {len(components)}")
    length_pos = c.length
    c.push_byte(0)
    c.push_byte(defs.SCOPE_ENUM[scope_type])
    for component in components:
        idx = enums.scope_bits.get_index(component)
        c.push_n_byte(idx)
    item_length = c.length - length_pos
    if item_length > 63:
        raise ValueError(f"Scope item exceeds 63-byte succinct length limit ({item_length} bytes)")
    item_type = defs.ITEM_ENUM["startScope"] if is_start else defs.ITEM_ENUM["endScope"]
    c.set_byte(length_pos, item_length | (item_type << 6))


def push_graft(c: "ByteArray", enums, graft_type, target_seq_id):
    length_pos = c.length
    c.push_byte(0)
    graft_type_index = enums.graft_types.get_index(graft_type)
    if graft_type_index > 255:
        raise ValueError("More than 256 distinct graft type names in one document")
    c.push_byte(graft_type_index)
    seq_index = enums.ids.get_index(target_seq_id)
    c.push_n_byte(seq_index)
    item_length = c.length - length_pos
    if item_length > 63:
        raise ValueError(f"Graft item exceeds 63-byte succinct length limit ({item_length} bytes)")
    c.set_byte(length_pos, item_length | (defs.ITEM_ENUM["graft"] << 6))
