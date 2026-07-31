//! Port of tools/pkf-decode-py/defs.py (proskomma-core's util/itemDefs.js,
//! tokenDefs.js, scopeDefs.js). Only n_components_for_scope is needed on the
//! read path — see succinct.rs's module docs for why labelForScope itself is
//! write-side-only and skipped.

pub const ITEM_TOKEN: u8 = 0;
pub const ITEM_GRAFT: u8 = 1;
pub const ITEM_START_SCOPE: u8 = 2;
pub const ITEM_END_SCOPE: u8 = 3;

pub const TOKEN_ENUM_LABELS: [&str; 8] = [
    "wordLike", "punctuation", "lineSpace", "eol", "softLineBreak", "noBreakSpace", "bareSlash", "unknown",
];

pub fn token_category(label: &str) -> &'static str {
    if label == "wordLike" {
        "wordLike"
    } else {
        "notWordLike"
    }
}

pub const SCOPE_ENUM_LABELS: [&str; 27] = [
    "blockTag", "inline", "chapter", "pubChapter", "altChapter", "verses", "verse", "pubVerse", "altVerse",
    "esbCat", "span", "table", "cell", "milestone", "spanWithAtts", "attribute", "hangingGraft", "orphanTokens",
    "tTableRow", "tTableCol", "tTreeNode", "tTreeParent", "tTreeChild", "tTreeContent", "kvPrimary",
    "kvSecondary", "kvField",
];

pub fn n_components_for_scope(scope_type: &str) -> u32 {
    match scope_type {
        "orphanTokens" | "hangingGraft" | "table" => 1,
        "blockTag" | "inline" | "chapter" | "verses" | "verse" | "span" | "milestone" | "spanWithAtts"
        | "pubChapter" | "altChapter" | "pubVerse" | "altVerse" | "esbCat" | "tTableRow" | "tTableCol"
        | "tTreeNode" | "tTreeParent" | "tTreeContent" | "kvPrimary" | "kvField" => 2,
        "tTreeChild" | "kvSecondary" => 3,
        "cell" => 4,
        "attribute" => 6,
        _ => panic!("Unknown scope type '{}' in nComponentsForScope", scope_type),
    }
}
