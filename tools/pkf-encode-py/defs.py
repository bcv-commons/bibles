"""Port of proskomma-core's util/itemDefs.js, util/tokenDefs.js, util/scopeDefs.js
— the enum tables and label-building rules for the succinct item format.
Verbatim field order/values matter (they're the numeric succinct encoding).
"""

ITEM_ENUM = {"token": 0, "graft": 1, "startScope": 2, "endScope": 3}

TOKEN_ENUM = {
    "wordLike": 0,
    "punctuation": 1,
    "lineSpace": 2,
    "eol": 3,
    "softLineBreak": 4,
    "noBreakSpace": 5,
    "bareSlash": 6,
    "unknown": 7,
}
TOKEN_ENUM_LABELS = [k for k, _ in sorted(TOKEN_ENUM.items(), key=lambda kv: kv[1])]

TOKEN_CATEGORY = {
    "wordLike": "wordLike",
    "punctuation": "notWordLike",
    "lineSpace": "notWordLike",
    "eol": "notWordLike",
    "softLineBreak": "notWordLike",
    "noBreakSpace": "notWordLike",
    "bareSlash": "notWordLike",
    "unknown": "notWordLike",
}

SCOPE_ENUM = {
    "blockTag": 0, "inline": 1, "chapter": 2, "pubChapter": 3, "altChapter": 4,
    "verses": 5, "verse": 6, "pubVerse": 7, "altVerse": 8, "esbCat": 9,
    "span": 10, "table": 11, "cell": 12, "milestone": 13, "spanWithAtts": 14,
    "attribute": 15, "hangingGraft": 16, "orphanTokens": 17, "tTableRow": 18,
    "tTableCol": 19, "tTreeNode": 20, "tTreeParent": 21, "tTreeChild": 22,
    "tTreeContent": 23, "kvPrimary": 24, "kvSecondary": 25, "kvField": 26,
}
SCOPE_ENUM_LABELS = [k for k, _ in sorted(SCOPE_ENUM.items(), key=lambda kv: kv[1])]


def _split_tag_number(full_tag_name):
    # scopeDefs.js splitTagNumber: xre(/([^1-9]+)(.*)/)
    i = 0
    while i < len(full_tag_name) and full_tag_name[i] not in "123456789":
        i += 1
    tag_name = full_tag_name[:i]
    tag_no = full_tag_name[i:]
    return tag_name, (tag_no if tag_no else "1")


def _cell_scope(full_tag_name):
    tag_props = {
        "th": {"type": "colHeading", "align": "left"},
        "thr": {"type": "colHeading", "align": "right"},
        "tc": {"type": "body", "align": "left"},
        "tcr": {"type": "body", "align": "right"},
    }
    tag_name, tag_no = _split_tag_number(full_tag_name)
    tag_field = "1"
    if "-" in tag_no:
        from_n, to_n = tag_no.split("-")
        tag_field = str(int(to_n) - int(from_n) + 1)
    props = tag_props[tag_name]
    return f"cell/{props['type']}/{props['align']}/{tag_field}"


def label_for_scope(scope_type, scope_fields):
    if scope_type == "blockTag":
        return f"blockTag/{scope_fields[0]}"
    if scope_type == "inline":
        return f"inline/{scope_fields[0]}"
    if scope_type == "chapter":
        return f"chapter/{scope_fields[0]}"
    if scope_type == "verses":
        return f"verses/{scope_fields[0]}"
    if scope_type == "verse":
        return f"verse/{scope_fields[0]}"
    if scope_type == "span":
        return f"span/{scope_fields[0]}"
    if scope_type == "table":
        return "table"
    if scope_type == "cell":
        return _cell_scope(scope_fields[0])
    if scope_type == "milestone":
        return f"milestone/{scope_fields[0]}"
    if scope_type == "spanWithAtts":
        return f"spanWithAtts/{scope_fields[0]}"
    if scope_type == "attribute":
        return f"attribute/{scope_fields[0]}/{scope_fields[1]}/{scope_fields[2]}/{scope_fields[3]}"
    if scope_type == "orphanTokens":
        return "orphanTokens"
    if scope_type == "hangingGraft":
        return "hangingGraft"
    if scope_type == "pubChapter":
        return f"pubChapter/{scope_fields[0]}"
    if scope_type == "pubVerse":
        return f"pubVerse/{scope_fields[0]}"
    if scope_type == "altChapter":
        return f"altChapter/{scope_fields[0]}"
    if scope_type == "altVerse":
        return f"altVerse/{scope_fields[0]}"
    if scope_type == "esbCat":
        return f"esbCat/{scope_fields[0]}"
    if scope_type == "tTableRow":
        return f"tTableRow/{scope_fields[0]}"
    if scope_type == "tTableCol":
        return f"tTableCol/{scope_fields[0]}"
    if scope_type == "tTreeNode":
        return f"tTreeNode/{scope_fields[0]}"
    if scope_type == "tTreeParent":
        return f"tTreeParent/{scope_fields[0]}"
    if scope_type == "tTreeChild":
        return f"tTreeChild/{scope_fields[0]}/{scope_fields[1]}"
    if scope_type == "tTreeContent":
        return f"tTreeContent/{scope_fields[0]}"
    if scope_type == "kvPrimary":
        return f"kvPrimary/{scope_fields[0]}"
    if scope_type == "kvSecondary":
        return f"kvSecondary/{scope_fields[0]}/{scope_fields[1]}"
    if scope_type == "kvField":
        return f"kvField/{scope_fields[0]}"
    raise ValueError(f"Unknown scope type '{scope_type}' in labelForScope")


def n_components_for_scope(scope_type):
    if scope_type in ("orphanTokens", "hangingGraft", "table"):
        return 1
    if scope_type in (
        "blockTag", "inline", "chapter", "verses", "verse", "span", "milestone",
        "spanWithAtts", "pubChapter", "altChapter", "pubVerse", "altVerse",
        "esbCat", "tTableRow", "tTableCol", "tTreeNode", "tTreeParent",
        "tTreeContent", "kvPrimary", "kvField",
    ):
        return 2
    if scope_type in ("tTreeChild", "kvSecondary"):
        return 3
    if scope_type == "cell":
        return 4
    if scope_type == "attribute":
        return 6
    raise ValueError(f"Unknown scope type '{scope_type}' in nComponentsForScope")
