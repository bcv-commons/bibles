//! Port of tools/pkf-decode-py/succinct.py.

use crate::byte_array::ByteArray;
use crate::defs;
use std::collections::HashMap;

pub struct Enums {
    pub ids: ByteArray,
    pub word_like: ByteArray,
    pub not_word_like: ByteArray,
    pub scope_bits: ByteArray,
    pub graft_types: ByteArray,
}

impl Enums {
    pub fn by_category(&self, category: &str) -> &ByteArray {
        match category {
            "ids" => &self.ids,
            "wordLike" => &self.word_like,
            "notWordLike" => &self.not_word_like,
            "scopeBits" => &self.scope_bits,
            "graftTypes" => &self.graft_types,
            _ => panic!("Unknown enum category '{}'", category),
        }
    }
}

pub struct EnumIndexes {
    pub map: HashMap<&'static str, Vec<usize>>,
}

impl EnumIndexes {
    pub fn build(enums: &Enums) -> Self {
        let mut map = HashMap::new();
        for category in ["ids", "wordLike", "notWordLike", "scopeBits", "graftTypes"] {
            map.insert(category, enum_index(enums.by_category(category)));
        }
        EnumIndexes { map }
    }

    pub fn get(&self, category: &str) -> &Vec<usize> {
        self.map.get(category).unwrap()
    }
}

pub fn enum_index(enum_succinct: &ByteArray) -> Vec<usize> {
    let mut index = Vec::new();
    let mut pos = 0;
    while pos < enum_succinct.length() {
        index.push(pos);
        let string_length = enum_succinct.byte(pos) as usize;
        pos += string_length + 1;
    }
    index
}

/// (item_length, item_type, item_subtype)
pub fn header_bytes(succinct: &ByteArray, pos: usize) -> (usize, u8, u8) {
    let header_byte = succinct.byte(pos);
    let item_type = header_byte >> 6;
    let item_length = (header_byte & 0x3F) as usize;
    let item_subtype = succinct.byte(pos + 1);
    (item_length, item_type, item_subtype)
}

pub fn succinct_token_chars(enums: &Enums, idx: &EnumIndexes, s: &ByteArray, item_subtype: u8, pos: usize) -> String {
    let token_label = defs::TOKEN_ENUM_LABELS[item_subtype as usize];
    let category = defs::token_category(token_label);
    let item_index = idx.get(category)[s.n_byte(pos + 2) as usize];
    enums.by_category(category).counted_string(item_index)
}

pub fn succinct_scope_label(enums: &Enums, idx: &EnumIndexes, s: &ByteArray, item_subtype: u8, pos: usize) -> String {
    let scope_type = defs::SCOPE_ENUM_LABELS[item_subtype as usize];
    let mut n_scope_bits = defs::n_components_for_scope(scope_type);
    let mut offset = 2usize;
    let mut scope_bits = String::new();
    while n_scope_bits > 1 {
        let item_index_index = s.n_byte(pos + offset) as usize;
        let item_index = idx.get("scopeBits")[item_index_index];
        let scope_bit_string = enums.scope_bits.counted_string(item_index);
        scope_bits.push('/');
        scope_bits.push_str(&scope_bit_string);
        offset += s.n_byte_length(item_index_index as u32);
        n_scope_bits -= 1;
    }
    format!("{}{}", scope_type, scope_bits)
}

pub fn succinct_graft_name(enums: &Enums, idx: &EnumIndexes, item_subtype: u8) -> String {
    let graft_index = idx.get("graftTypes")[item_subtype as usize];
    enums.graft_types.counted_string(graft_index)
}

pub fn succinct_graft_seq_id(enums: &Enums, idx: &EnumIndexes, s: &ByteArray, pos: usize) -> String {
    let seq_index = idx.get("ids")[s.n_byte(pos + 2) as usize];
    enums.ids.counted_string(seq_index)
}
