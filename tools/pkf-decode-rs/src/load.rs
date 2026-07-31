//! Port of tools/pkf-decode-py/load.py.

use std::collections::HashMap;
use std::io::Read;

use flate2::read::GzDecoder;
use serde_json::Value;

use crate::byte_array::ByteArray;
use crate::succinct::{Enums, EnumIndexes};
use crate::unsuccinctify::{unsuccinctify_block_scope, unsuccinctify_grafts, unsuccinctify_items};
use crate::item::Item;

pub struct Block {
    pub bs: String,
    pub bg: Vec<(String, String)>,
    pub c: Vec<Item>,
}

pub struct Sequence {
    pub type_: String,
    pub blocks: Vec<Block>,
}

pub struct Doc {
    /// Preserves original JSON key order — matters for startDocument's
    /// header-dumping loop, which must match decode.mjs's output order
    /// (JS objects and Python dicts both preserve insertion order; a
    /// HashMap here would not).
    pub headers: Vec<(String, String)>,
    pub main_id: String,
    pub sequences: HashMap<String, Sequence>,
}

impl Doc {
    pub fn header(&self, key: &str) -> Option<&str> {
        self.headers.iter().find(|(k, _)| k == key).map(|(_, v)| v.as_str())
    }
}

pub struct Loaded {
    pub docset_id: String,
    pub selectors: HashMap<String, String>,
    pub docs: Vec<(String, Doc)>, // preserves insertion order, unlike a HashMap
}

fn as_str_map(v: &Value) -> HashMap<String, String> {
    v.as_object()
        .expect("expected object")
        .iter()
        .map(|(k, v)| (k.clone(), v.as_str().unwrap_or_default().to_string()))
        .collect()
}

fn as_str_pairs(v: &Value) -> Vec<(String, String)> {
    v.as_object()
        .expect("expected object")
        .iter()
        .map(|(k, v)| (k.clone(), v.as_str().unwrap_or_default().to_string()))
        .collect()
}

pub fn load_pkf(pkf_bytes: &[u8]) -> Loaded {
    let mut decoder = GzDecoder::new(pkf_bytes);
    let mut json_str = String::new();
    decoder.read_to_string(&mut json_str).expect("gzip decompress failed");
    let succinct_ob: Value = serde_json::from_str(&json_str).expect("invalid JSON in pkf");

    let enums_ob = &succinct_ob["enums"];
    let enums = Enums {
        ids: ByteArray::from_base64(enums_ob["ids"].as_str().unwrap()),
        word_like: ByteArray::from_base64(enums_ob["wordLike"].as_str().unwrap()),
        not_word_like: ByteArray::from_base64(enums_ob["notWordLike"].as_str().unwrap()),
        scope_bits: ByteArray::from_base64(enums_ob["scopeBits"].as_str().unwrap()),
        graft_types: ByteArray::from_base64(enums_ob["graftTypes"].as_str().unwrap()),
    };
    let idx = EnumIndexes::build(&enums);

    let mut docs = Vec::new();
    let docs_ob = succinct_ob["docs"].as_object().expect("docs must be an object");
    for (doc_id, succinct_doc) in docs_ob.iter() {
        let mut sequences = HashMap::new();
        let seqs_ob = succinct_doc["sequences"].as_object().expect("sequences must be object");
        for (seq_id, seq) in seqs_ob.iter() {
            let type_ = seq["type"].as_str().unwrap().to_string();
            let mut blocks = Vec::new();
            for succinct_block in seq["blocks"].as_array().expect("blocks must be array") {
                let bs_ba = ByteArray::from_base64(succinct_block["bs"].as_str().unwrap());
                let bg_ba = ByteArray::from_base64(succinct_block["bg"].as_str().unwrap());
                let c_ba = ByteArray::from_base64(succinct_block["c"].as_str().unwrap());
                blocks.push(Block {
                    bs: unsuccinctify_block_scope(&enums, &idx, &bs_ba),
                    bg: unsuccinctify_grafts(&enums, &idx, &bg_ba),
                    c: unsuccinctify_items(&enums, &idx, &c_ba),
                });
            }
            sequences.insert(seq_id.clone(), Sequence { type_, blocks });
        }
        docs.push((
            doc_id.clone(),
            Doc {
                headers: as_str_pairs(&succinct_doc["headers"]),
                main_id: succinct_doc["mainId"].as_str().unwrap().to_string(),
                sequences,
            },
        ));
    }

    Loaded {
        docset_id: succinct_ob["id"].as_str().unwrap().to_string(),
        selectors: as_str_map(&succinct_ob["metadata"]["selectors"]),
        docs,
    }
}
