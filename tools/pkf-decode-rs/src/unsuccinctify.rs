//! Port of tools/pkf-decode-py/unsuccinctify.py — see its docstring for why
//! this is a single unconditional full walk (no filtering options needed for
//! decode.mjs's actual GraphQL query shape).

use crate::byte_array::ByteArray;
use crate::defs;
use crate::item::Item;
use crate::succinct::{header_bytes, succinct_graft_name, succinct_graft_seq_id, succinct_scope_label, succinct_token_chars, Enums, EnumIndexes};

pub fn unsuccinctify_item(enums: &Enums, idx: &EnumIndexes, s: &ByteArray, pos: usize) -> (Item, usize) {
    let (item_length, item_type, item_subtype) = header_bytes(s, pos);
    let item = match item_type {
        defs::ITEM_TOKEN => {
            let label = defs::TOKEN_ENUM_LABELS[item_subtype as usize].to_string();
            let chars = succinct_token_chars(enums, idx, s, item_subtype, pos);
            Item::Token { sub: label, payload: chars }
        }
        defs::ITEM_START_SCOPE => {
            let label = succinct_scope_label(enums, idx, s, item_subtype, pos);
            Item::ScopeStart { payload: label }
        }
        defs::ITEM_END_SCOPE => {
            let label = succinct_scope_label(enums, idx, s, item_subtype, pos);
            Item::ScopeEnd { payload: label }
        }
        defs::ITEM_GRAFT => {
            let name = succinct_graft_name(enums, idx, item_subtype);
            let seq_id = succinct_graft_seq_id(enums, idx, s, pos);
            Item::Graft { sub: name, payload: seq_id }
        }
        _ => panic!("Unknown item type {}", item_type),
    };
    (item, item_length)
}

pub fn unsuccinctify_items(enums: &Enums, idx: &EnumIndexes, s: &ByteArray) -> Vec<Item> {
    let mut ret = Vec::new();
    let mut pos = 0;
    while pos < s.length() {
        let (item, item_length) = unsuccinctify_item(enums, idx, s, pos);
        ret.push(item);
        pos += item_length;
    }
    ret
}

pub fn unsuccinctify_grafts(enums: &Enums, idx: &EnumIndexes, s: &ByteArray) -> Vec<(String, String)> {
    let mut ret = Vec::new();
    let mut pos = 0;
    while pos < s.length() {
        let (item_length, _item_type, item_subtype) = header_bytes(s, pos);
        let name = succinct_graft_name(enums, idx, item_subtype);
        let seq_id = succinct_graft_seq_id(enums, idx, s, pos);
        ret.push((name, seq_id));
        pos += item_length;
    }
    ret
}

/// For 'bs' (block scope) — a single scope item at position 0. Returns the label.
pub fn unsuccinctify_block_scope(enums: &Enums, idx: &EnumIndexes, bs: &ByteArray) -> String {
    let (_len, _item_type, item_subtype) = header_bytes(bs, 0);
    succinct_scope_label(enums, idx, bs, item_subtype, 0)
}
