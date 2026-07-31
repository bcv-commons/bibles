//! Port of tools/pkf-decode-py/succinct_renderer.py + usfm_render.py.
//!
//! The real installed proskomma-core@0.11.3's document.usfm() runs a
//! succinct-driven renderer (NOT a PERF-JSON tree walker — verified against
//! the actual minified bundle, see the Python port's succinct_renderer.py
//! docstring for the full investigation) TWICE: once with
//! calculateUsfmChapterPositionsActions$1 (a chapter-number "report"), once
//! with perf2UsfmActions (the USFM text itself, using that report).
//! Rust doesn't need a generic pluggable-action-list abstraction here since
//! there are only ever these two fixed action sets — this file inlines both
//! directly as match arms on `Phase`, but every branch corresponds exactly
//! to one JS action, comment-tagged with which.
//!
//! Several behaviors here look like bugs on a read-through. They are real,
//! confirmed against the actual installed library by direct experiment (not
//! guessed), and must NOT be "fixed" — the goal is byte-for-byte output
//! parity with decode.mjs, not "more correct" USFM:
//! - `spanWithAtts`'s end scope is a no-op (render_item) — an opened word
//!   wrapper can be left permanently unclosed if nothing else forces a
//!   flush before the block ends.
//! - Row/table blocks never actually fire startRow/endRow — the real code
//!   compares the wrong variable, so they always go through
//!   startParagraph/endParagraph instead (see `render_sequence_id`).
//! - A 'cell' wrapper's subType is the bare string "cell" (no "usfm:"
//!   prefix); splitting on ':' for the tag name then yields nothing, which
//!   JS's out-of-bounds array access reports as `undefined` and stringifies
//!   as the literal text "undefined" (see `subtype_tag`).
//! - Attribute atts values are coerced to comma-joined strings even for
//!   single-element lists (JS array-to-string coercion) — see `atts_str`.

use std::collections::HashMap;

use crate::item::Item;
use crate::load::Doc;

const ONEIFY: [&str; 8] = ["toc", "toca", "mt", "imt", "s", "ms", "mte", "sd"];
const NO_END_TAG_WRAPPERS: [&str; 13] = [
    "fr", "fq", "fqa", "fk", "fl", "fw", "fp", "ft", "xo", "xk", "xq", "xt", "xta",
];

fn oneify_tag(t: &str) -> String {
    if ONEIFY.contains(&t) {
        format!("{}1", t)
    } else {
        t.to_string()
    }
}

/// JS does `subType.split(':')[1]` and lets an out-of-range index return
/// `undefined` (no crash/panic) rather than throw. Reproduced verbatim.
fn subtype_tag(sub_type: &str) -> String {
    match sub_type.split_once(':') {
        Some((_, rest)) => rest.to_string(),
        None => "undefined".to_string(),
    }
}

fn atts_str(values: &[String]) -> String {
    values.join(",")
}

fn atts_to_string(atts: &[(String, Vec<String>)]) -> String {
    let mut s = String::new();
    for (key, value) in atts {
        s.push_str(&format!("{}=\"{}\" ", oneify_tag(key), atts_str(value)));
    }
    s
}

#[derive(Clone, Copy, PartialEq)]
pub enum Phase {
    Report,
    Usfm,
}

struct BlockCtx {
    block_type: String, // "graft" | "row" | "paragraph"  (kept for report's initial_block_record)
    sub_type: String,
    block_n: usize,
    wrappers: Vec<String>,
    target: Option<String>,
}

struct SeqCtx {
    id: String,
    seq_type: String,
    block: Option<BlockCtx>,
}

enum ContainerKind {
    WrapperStart,
    WrapperEnd,
    StartMilestone,
    EndMilestone,
}

struct Container {
    kind: ContainerKind,
    sub_type: String,
    atts: Vec<(String, Vec<String>)>,
}

/// A block record for the report phase.
struct BlockRecord {
    block_type: String,
    sub_type: String,
    perf_chapter: Option<String>,
}

pub struct RenderOutput {
    pub report: HashMap<String, String>,
    pub usfm: String,
}

pub struct Renderer<'a> {
    doc: &'a Doc,
    phase: Phase,
    report_in: Option<&'a HashMap<String, String>>, // usfm phase's input report
    seq_stack: Vec<SeqCtx>,
    tokens: Vec<String>,
    container: Option<Container>,
    // report phase workspace
    block_records: Vec<BlockRecord>,
    // usfm phase workspace
    usfm_bits: Vec<String>,
    nested_wrapper: i32,
    doc_metadata_document: Vec<(String, String)>,
}

impl<'a> Renderer<'a> {
    pub fn new(doc: &'a Doc, phase: Phase, report_in: Option<&'a HashMap<String, String>>) -> Self {
        Renderer {
            doc,
            phase,
            report_in,
            seq_stack: Vec::new(),
            tokens: Vec::new(),
            container: None,
            block_records: Vec::new(),
            usfm_bits: Vec::new(),
            nested_wrapper: 0,
            doc_metadata_document: doc.headers.clone(),
        }
    }

    pub fn render(mut self) -> RenderOutput {
        // startDocument
        if self.phase == Phase::Usfm {
            self.usfm_bits.push(String::new());
            self.nested_wrapper = 0;
            for (key, value) in &self.doc_metadata_document {
                if matches!(key.as_str(), "tags" | "properties" | "bookCode" | "cl") {
                    continue;
                }
                self.usfm_bits.push(format!("\\{} {}\n", oneify_tag(key), value));
            }
        }
        // (report phase's startDocument just clears state, already default)

        let main_id = self.doc.main_id.clone();
        self.render_sequence_id(&main_id);

        // endDocument
        let report = if self.phase == Phase::Report {
            self.populate_report()
        } else {
            HashMap::new()
        };
        let usfm = if self.phase == Phase::Usfm {
            let joined = self.usfm_bits.join("");
            trim_newlines(&joined)
        } else {
            String::new()
        };
        RenderOutput { report, usfm }
    }

    fn populate_report(&self) -> HashMap<String, String> {
        let mut report = HashMap::new();
        for (record_n, record) in self.block_records.iter().enumerate() {
            let Some(perf_chapter) = &record.perf_chapter else { continue };
            let mut usfm_chapter_pos = record_n;
            let mut found = false;
            while usfm_chapter_pos > 0 && !found {
                let prev = &self.block_records[usfm_chapter_pos - 1];
                if prev.block_type == "paragraph" || prev.sub_type == "title" {
                    found = true;
                } else {
                    usfm_chapter_pos -= 1;
                }
            }
            report.insert(usfm_chapter_pos.to_string(), perf_chapter.clone());
        }
        report
    }

    fn report_for_block(&self, block_n: usize) -> Option<&String> {
        self.report_in.and_then(|r| r.get(&block_n.to_string()))
    }

    fn render_sequence_id(&mut self, sequence_id: &str) {
        let sequence = self.doc.sequences.get(sequence_id).expect("missing sequence");
        self.seq_stack.insert(0, SeqCtx { id: sequence_id.to_string(), seq_type: sequence.seq_type_clone(), block: None });

        let mut output_block_n = 0usize;
        for block in &sequence.blocks {
            for (graft_sub, graft_target) in &block.bg {
                self.seq_stack[0].block = Some(BlockCtx {
                    block_type: "graft".to_string(),
                    sub_type: camel_to_snake(graft_sub),
                    block_n: output_block_n,
                    wrappers: Vec::new(),
                    target: Some(graft_target.clone()),
                });
                self.fire_block_graft();
                output_block_n += 1;
            }

            let sub_type_values: Vec<&str> = block.bs.split('/').collect();
            let sub_type_value = if sub_type_values.len() > 1 && matches!(sub_type_values[1], "tr" | "zrow") {
                if sub_type_values[1] == "tr" { "usfm:tr".to_string() } else { "pk".to_string() }
            } else if sub_type_values.len() > 1 {
                format!("usfm:{}", sub_type_values[1])
            } else {
                sub_type_values[0].to_string()
            };
            let block_type = if sub_type_value == "usfm:tr" || sub_type_value == "pk" { "row" } else { "paragraph" };

            self.seq_stack[0].block = Some(BlockCtx {
                block_type: block_type.to_string(),
                sub_type: sub_type_value.clone(),
                block_n: output_block_n,
                wrappers: Vec::new(),
                target: None,
            });

            // Real bug preserved: the comparison that would pick startRow is
            // against the wrong variable and is always false, so this always
            // fires startParagraph/endParagraph, never startRow/endRow.
            self.fire_start_paragraph();
            self.tokens.clear();
            let items = block.c.clone();
            self.render_content(&items);
            self.tokens.clear();
            self.fire_end_paragraph();

            self.seq_stack[0].block = None;
            output_block_n += 1;
        }

        self.fire_end_sequence();
        self.seq_stack.remove(0);
    }

    fn fire_end_sequence(&mut self) {
        if self.phase != Phase::Usfm {
            return;
        }
        let cl = self.doc_metadata_document.iter().find(|(k, _)| k == "cl").map(|(_, v)| v.clone());
        if let Some(cl) = cl {
            if self.seq_stack[0].seq_type == "title" {
                self.usfm_bits.push(format!("\n\\cl {}\n", cl));
            }
        }
    }

    fn render_content(&mut self, items: &[Item]) {
        for item in items {
            self.render_item(item);
        }
        self.maybe_render_text();
    }

    fn render_item(&mut self, item: &Item) {
        match item {
            Item::ScopeStart { payload } if payload.starts_with("attribute") => {
                let bits: Vec<&str> = payload.split('/').collect();
                if self.container.is_none() {
                    self.container = Some(Container {
                        kind: ContainerKind::WrapperStart,
                        sub_type: "usfm:w".to_string(),
                        atts: Vec::new(),
                    });
                }
                push_att(&mut self.container.as_mut().unwrap().atts, bits[3], bits[5]);
                return;
            }
            Item::ScopeEnd { payload } if payload.starts_with("attribute") => {
                let bits: Vec<&str> = payload.split('/').collect();
                if self.container.is_none() {
                    let mut c = Container {
                        kind: if bits[1] == "milestone" { ContainerKind::EndMilestone } else { ContainerKind::WrapperEnd },
                        sub_type: format!("usfm:{}", camel_to_snake(bits[2])),
                        atts: Vec::new(),
                    };
                    if !matches!(c.kind, ContainerKind::EndMilestone) {
                        push_att(&mut c.atts, bits[3], bits[5]);
                    }
                    self.container = Some(c);
                }
                return;
            }
            _ => {}
        }

        if self.container.is_some() {
            self.maybe_render_text();
            self.render_container();
        }

        match item {
            Item::Token { payload, .. } => {
                self.tokens.push(ws_normalize(payload));
            }
            Item::Graft { sub, payload } => {
                self.maybe_render_text();
                self.fire_inline_graft(sub, payload);
            }
            Item::ScopeStart { payload } | Item::ScopeEnd { payload } => {
                self.maybe_render_text();
                let is_start = matches!(item, Item::ScopeStart { .. });
                let bits: Vec<&str> = payload.split('/').collect();
                match bits[0] {
                    "chapter" | "verses" | "pubChapter" | "pubVerse" | "altChapter" | "altVerse" => {
                        if is_start {
                            self.fire_mark(&camel_to_snake(bits[0]), Some(bits[1].to_string()));
                        }
                    }
                    "span" => {
                        let sub_type = format!("usfm:{}", bits[1]);
                        if is_start {
                            self.seq_stack[0].block.as_mut().unwrap().wrappers.insert(0, sub_type.clone());
                            self.fire_start_wrapper(&sub_type, &[]);
                        } else {
                            self.fire_end_wrapper(&sub_type, &[]);
                            self.seq_stack[0].block.as_mut().unwrap().wrappers.remove(0);
                        }
                    }
                    "spanWithAtts" => {
                        if is_start {
                            self.container = Some(Container {
                                kind: ContainerKind::WrapperStart,
                                sub_type: format!("usfm:{}", bits[1]),
                                atts: Vec::new(),
                            });
                        }
                        // No handling for the end scope — matches the real
                        // engine's no-op exactly (see module docs).
                    }
                    "cell" => {
                        let sub_type = "cell".to_string();
                        if is_start {
                            self.seq_stack[0].block.as_mut().unwrap().wrappers.insert(0, sub_type.clone());
                            self.fire_start_wrapper(&sub_type, &[]);
                        } else {
                            self.fire_end_wrapper(&sub_type, &[]);
                            self.seq_stack[0].block.as_mut().unwrap().wrappers.remove(0);
                        }
                    }
                    "milestone" if is_start => {
                        if bits[1] == "ts" {
                            self.fire_mark(&format!("usfm:{}", camel_to_snake(bits[1])), None);
                        } else {
                            self.container = Some(Container {
                                kind: ContainerKind::StartMilestone,
                                sub_type: format!("usfm:{}", camel_to_snake(bits[1])),
                                atts: Vec::new(),
                            });
                        }
                    }
                    _ => {}
                }
            }
        }
    }

    fn maybe_render_text(&mut self) {
        if self.tokens.is_empty() {
            return;
        }
        let text = self.tokens.join("");
        self.tokens.clear();
        self.fire_text(&text);
    }

    fn render_container(&mut self) {
        let c = self.container.take().unwrap();
        match c.kind {
            ContainerKind::WrapperStart => {
                self.seq_stack[0].block.as_mut().unwrap().wrappers.insert(0, c.sub_type.clone());
                self.fire_start_wrapper(&c.sub_type, &c.atts);
            }
            ContainerKind::WrapperEnd => {
                self.fire_end_wrapper(&c.sub_type, &c.atts);
                self.seq_stack[0].block.as_mut().unwrap().wrappers.remove(0);
            }
            ContainerKind::StartMilestone => {
                self.fire_start_milestone(&c.sub_type, &c.atts);
            }
            ContainerKind::EndMilestone => {
                self.fire_end_milestone(&c.sub_type);
            }
        }
    }

    // ---- event firing: dispatch to the fixed action for the active phase ----

    fn fire_block_graft(&mut self) {
        let block = self.seq_stack[0].block.as_ref().unwrap();
        match self.phase {
            Phase::Report => {
                self.block_records.push(BlockRecord {
                    block_type: block.block_type.clone(),
                    sub_type: block.sub_type.clone(),
                    perf_chapter: None,
                });
            }
            Phase::Usfm => {
                let sub_type = block.sub_type.clone();
                if !matches!(sub_type.as_str(), "title" | "heading" | "introduction") {
                    return;
                }
                let block_n = block.block_n;
                let seq_type = self.seq_stack[0].seq_type.clone();
                let target = self.seq_stack[0].block.as_ref().unwrap().target.clone();
                let chapter_value = self.report_for_block(block_n).cloned();
                if let Some(cv) = &chapter_value {
                    if seq_type == "main" {
                        self.usfm_bits.push(format!("\n\\c {}\n", cv));
                    }
                }
                if let Some(t) = target {
                    self.render_sequence_id(&t);
                }
            }
        }
    }

    fn fire_start_paragraph(&mut self) {
        let block = self.seq_stack[0].block.as_ref().unwrap();
        match self.phase {
            Phase::Report => {
                self.block_records.push(BlockRecord {
                    block_type: block.block_type.clone(),
                    sub_type: block.sub_type.clone(),
                    perf_chapter: None,
                });
            }
            Phase::Usfm => {
                let sub_type = block.sub_type.clone();
                let seq_type = self.seq_stack[0].seq_type.clone();
                let block_n = block.block_n;
                let is_note_para = (sub_type == "usfm:f" && seq_type == "footnote") || (sub_type == "usfm:x" && seq_type == "xref");
                let is_note_subtype = sub_type == "usfm:f" || sub_type == "usfm:x";
                if is_note_para {
                    self.nested_wrapper = 0;
                    self.usfm_bits.push(format!("\\{} ", oneify_tag(&subtype_tag(&sub_type))));
                    return;
                }
                if is_note_subtype {
                    self.nested_wrapper = 0;
                    return;
                }
                self.nested_wrapper = 0;
                let chapter_value = self.report_for_block(block_n).cloned();
                if let Some(cv) = &chapter_value {
                    if seq_type == "main" {
                        self.usfm_bits.push(format!("\n\\c {}\n", cv));
                    }
                }
                self.usfm_bits.push(format!("\n\\{}\n", oneify_tag(&subtype_tag(&sub_type))));
            }
        }
    }

    fn fire_end_paragraph(&mut self) {
        if self.phase == Phase::Report {
            return;
        }
        let block = self.seq_stack[0].block.as_ref().unwrap();
        let sub_type = block.sub_type.clone();
        let seq_type = self.seq_stack[0].seq_type.clone();
        let is_note_para = (sub_type == "usfm:f" && seq_type == "footnote") || (sub_type == "usfm:x" && seq_type == "xref");
        let is_note_subtype = sub_type == "usfm:f" || sub_type == "usfm:x";
        if is_note_para {
            self.usfm_bits.push(format!("\\{}*", oneify_tag(&subtype_tag(&sub_type))));
            return; // note_caller entry is a deliberate no-op in the real JS too
        }
        if is_note_subtype {
            return;
        }
        self.usfm_bits.push("\n".to_string());
    }

    fn fire_mark(&mut self, sub_type: &str, number: Option<String>) {
        match self.phase {
            Phase::Report => {
                if sub_type == "chapter" {
                    if let (Some(rec), Some(n)) = (self.block_records.last_mut(), &number) {
                        rec.perf_chapter = Some(n.clone());
                    }
                }
            }
            Phase::Usfm => {
                if sub_type == "verses" {
                    self.usfm_bits.push(format!("\n\\v {}\n", number.unwrap_or_default()));
                }
            }
        }
    }

    fn fire_inline_graft(&mut self, sub: &str, target: &str) {
        if self.phase != Phase::Usfm {
            return;
        }
        let _ = sub;
        self.render_sequence_id(target);
    }

    fn fire_text(&mut self, text: &str) {
        if self.phase == Phase::Usfm {
            self.usfm_bits.push(text.to_string());
        }
    }

    fn fire_start_wrapper(&mut self, sub_type: &str, _atts: &[(String, Vec<String>)]) {
        if self.phase != Phase::Usfm {
            return;
        }
        let tag = oneify_tag(&subtype_tag(sub_type));
        if self.nested_wrapper > 0 {
            self.usfm_bits.push(format!("\\+{} ", tag));
        } else {
            self.usfm_bits.push(format!("\\{} ", tag));
        }
        self.nested_wrapper += 1;
    }

    fn fire_end_wrapper(&mut self, sub_type: &str, atts: &[(String, Vec<String>)]) {
        if self.phase != Phase::Usfm {
            return;
        }
        let tag = subtype_tag(sub_type);
        if !NO_END_TAG_WRAPPERS.contains(&tag.as_str()) {
            self.nested_wrapper -= 1;
            let is_nested = self.nested_wrapper > 0;
            if tag == "w" {
                let mut s = String::from("|");
                s.push_str(&atts_to_string(atts));
                s.push('\\');
                if is_nested {
                    s.push('+');
                }
                s.push_str("w*");
                self.usfm_bits.push(s);
            } else {
                let t = oneify_tag(&tag);
                self.usfm_bits.push(if is_nested { format!("\\+{}*", t) } else { format!("\\{}*", t) });
            }
        } else {
            self.nested_wrapper -= 1;
        }
    }

    fn fire_start_milestone(&mut self, sub_type: &str, atts: &[(String, Vec<String>)]) {
        if self.phase != Phase::Usfm {
            return;
        }
        let tag = oneify_tag(&subtype_tag(sub_type));
        let mut s = format!("\\{}-s |", tag);
        s.push_str(&atts_to_string(atts));
        s.push_str("\\*");
        self.usfm_bits.push(s);
    }

    fn fire_end_milestone(&mut self, sub_type: &str) {
        if self.phase != Phase::Usfm {
            return;
        }
        self.usfm_bits.push(format!("\\{}-e\\*", oneify_tag(&subtype_tag(sub_type))));
    }
}

fn push_att(atts: &mut Vec<(String, Vec<String>)>, key: &str, value: &str) {
    if let Some(entry) = atts.iter_mut().find(|(k, _)| k == key) {
        entry.1.push(value.to_string());
    } else {
        atts.push((key.to_string(), vec![value.to_string()]));
    }
}

fn camel_to_snake(s: &str) -> String {
    let mut out = String::new();
    for c in s.chars() {
        if c.is_uppercase() {
            out.push('_');
            out.extend(c.to_lowercase());
        } else {
            out.push(c);
        }
    }
    out
}

/// JS's regex `\s` is NOT the same set as Rust's `char::is_whitespace()` —
/// most notably it includes U+FEFF (BOM/zero-width no-break space, per
/// ECMA-262's WhiteSpace production), which Rust's is_whitespace() does not
/// match at all, and excludes U+0085 (NEL), which Rust's does match.
/// Spelled out explicitly (ECMA-262 WhiteSpace + LineTerminator) rather than
/// relying on Rust's built-in notion of whitespace — confirmed needed
/// against real data: a token in a real corpus file (apb) carries a leading
/// U+FEFF that JS's token-normalization collapses to a space but a naive
/// `is_whitespace()`-based version silently passed through, byte-diffing
/// the output.
fn is_js_whitespace(c: char) -> bool {
    matches!(c,
        '\u{09}' | '\u{0B}' | '\u{0C}' | '\u{20}' | '\u{A0}' | '\u{1680}'
        | '\u{2000}'..='\u{200A}' | '\u{2028}' | '\u{2029}' | '\u{202F}' | '\u{205F}' | '\u{3000}' | '\u{FEFF}'
        | '\u{0A}' | '\u{0D}'
    )
}

fn ws_normalize(s: &str) -> String {
    let mut out = String::new();
    let mut in_ws = false;
    for c in s.chars() {
        if is_js_whitespace(c) {
            if !in_ws {
                out.push(' ');
            }
            in_ws = true;
        } else {
            out.push(c);
            in_ws = false;
        }
    }
    out
}

fn trim_newlines(s: &str) -> String {
    // Port of JS's /(\s*)\n(\s*)/gm -> '\n': collapse any run of whitespace
    // containing at least one newline down to a single '\n'.
    let mut out = String::with_capacity(s.len());
    let chars: Vec<char> = s.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        if is_js_whitespace(chars[i]) {
            let start = i;
            let mut has_newline = false;
            let mut j = i;
            while j < chars.len() && is_js_whitespace(chars[j]) {
                if chars[j] == '\n' {
                    has_newline = true;
                }
                j += 1;
            }
            if has_newline {
                out.push('\n');
            } else {
                out.extend(&chars[start..j]);
            }
            i = j;
        } else {
            out.push(chars[i]);
            i += 1;
        }
    }
    out
}

impl crate::load::Sequence {
    fn seq_type_clone(&self) -> String {
        self.type_.clone()
    }
}
