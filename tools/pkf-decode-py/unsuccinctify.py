"""Port of the read path proskomma-core's GraphQL block resolvers actually
exercise for `decode.mjs`'s query shape (`items{type subType payload}`,
`bs{payload}`, `bg{subType payload}`, no `withScopes`/`excludeScopeTypes`/
`includeContext` args).

That query shape resolves through `unsuccinctifyPrunedItems()` ->
`unsuccinctifyItems()` in proskomma-core, but with `requiredScopes: []` and
`anyScope: false` — which makes its scope/chars filtering a no-op (confirmed
by reading both: `allScopesInItem()` with an empty requiredScopes list
returns true unconditionally, and the chars test is skipped when
`withChars` is unset) — and with `tokens`/`scopes`/`grafts` all `true`, its
own type-based skip logic never triggers either. Net effect: every item is
returned, always, for this specific call shape. So this port implements a
single unconditional full walk rather than reproducing the two-layer
filter/prune machinery, which would be dead code for every call site
`decode.mjs` reaches.

Similarly, `unsuccinctifyItems()`'s token-position/open-scopes bookkeeping
(appended as extra tuple elements) is dropped here — the GraphQL query never
requests `position`/`scopes`, so those elements are produced and discarded
in the real pipeline for this call shape.
"""
import defs
import succinct as succ


def unsuccinctify_token(enums, enum_idx, s, item_subtype, pos):
    return ["token", defs.TOKEN_ENUM_LABELS[item_subtype],
            succ.succinct_token_chars(enums, enum_idx, s, item_subtype, pos)]


def unsuccinctify_scope(enums, enum_idx, s, item_type, item_subtype, pos):
    direction = "start" if item_type == defs.ITEM_ENUM["startScope"] else "end"
    return ["scope", direction, succ.succinct_scope_label(enums, enum_idx, s, item_subtype, pos)]


def unsuccinctify_graft(enums, enum_idx, s, item_subtype, pos):
    return ["graft", succ.succinct_graft_name(enums, enum_idx, item_subtype),
            succ.succinct_graft_seq_id(enums, enum_idx, s, pos)]


def unsuccinctify_item(enums, enum_idx, s, pos):
    item_length, item_type, item_subtype = succ.header_bytes(s, pos)
    if item_type == defs.ITEM_ENUM["token"]:
        item = unsuccinctify_token(enums, enum_idx, s, item_subtype, pos)
    elif item_type in (defs.ITEM_ENUM["startScope"], defs.ITEM_ENUM["endScope"]):
        item = unsuccinctify_scope(enums, enum_idx, s, item_type, item_subtype, pos)
    elif item_type == defs.ITEM_ENUM["graft"]:
        item = unsuccinctify_graft(enums, enum_idx, s, item_subtype, pos)
    else:
        raise ValueError(f"Unknown item type {item_type}")
    return item, item_length


def unsuccinctify_items(enums, enum_idx, s):
    """Full, unfiltered item list for a block's 'c' (content) byte array."""
    ret = []
    pos = 0
    while pos < s.length:
        item, item_length = unsuccinctify_item(enums, enum_idx, s, pos)
        ret.append(item)
        pos += item_length
    return ret


def unsuccinctify_scopes(enums, enum_idx, s):
    """For 'os'/'is' (open/included scopes) byte arrays — always scope items."""
    ret = []
    pos = 0
    while pos < s.length:
        item_length, item_type, item_subtype = succ.header_bytes(s, pos)
        ret.append(unsuccinctify_scope(enums, enum_idx, s, item_type, item_subtype, pos))
        pos += item_length
    return ret


def unsuccinctify_grafts(enums, enum_idx, s):
    """For 'bg' (block grafts) byte arrays — always graft items."""
    ret = []
    pos = 0
    while pos < s.length:
        item_length, item_type, item_subtype = succ.header_bytes(s, pos)
        ret.append(unsuccinctify_graft(enums, enum_idx, s, item_subtype, pos))
        pos += item_length
    return ret


def unsuccinctify_block_scope(enums, enum_idx, bs):
    """For 'bs' (block scope) — a single scope item at position 0."""
    item_length, item_type, item_subtype = succ.header_bytes(bs, 0)
    return unsuccinctify_scope(enums, enum_idx, bs, item_type, item_subtype, 0)
