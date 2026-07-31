//! Rust sibling of ../pkf-decode/decode.mjs and ../pkf-decode-py/decode.py —
//! decodes a PKF file into one plain USFM file per book. Same CLI shape,
//! same output naming, same byte-for-byte USFM text (verified against
//! decode.mjs and the validated Python port; see verify_corpus.py).
//!
//! Usage:
//!   pkf-decode <path-to.pkf> [--out <dir>] [--book <BOOKCODE>]
//!   pkf-decode <dir-of-.pkf-files> [--out <dir>]

mod byte_array;
mod defs;
mod item;
mod load;
mod render;
mod succinct;
mod unsuccinctify;

use std::fs;
use std::path::{Path, PathBuf};
use std::process::exit;

use load::{load_pkf, Loaded};
use render::{Phase, Renderer};

fn book_num(code: &str) -> Option<&'static str> {
    // USFM/Paratext book id -> file number, for stable sortable filenames.
    // 40 is reserved (skipped) between OT (39 books) and NT (starts at 41).
    let pairs: &[(&str, &str)] = &[
        ("GEN", "01"), ("EXO", "02"), ("LEV", "03"), ("NUM", "04"), ("DEU", "05"), ("JOS", "06"), ("JDG", "07"),
        ("RUT", "08"), ("1SA", "09"), ("2SA", "10"), ("1KI", "11"), ("2KI", "12"), ("1CH", "13"),
        ("2CH", "14"), ("EZR", "15"), ("NEH", "16"), ("EST", "17"), ("JOB", "18"), ("PSA", "19"), ("PRO", "20"),
        ("ECC", "21"), ("SNG", "22"), ("ISA", "23"), ("JER", "24"), ("LAM", "25"), ("EZK", "26"), ("DAN", "27"),
        ("HOS", "28"), ("JOL", "29"), ("AMO", "30"), ("OBA", "31"), ("JON", "32"), ("MIC", "33"), ("NAM", "34"),
        ("HAB", "35"), ("ZEP", "36"), ("HAG", "37"), ("ZEC", "38"), ("MAL", "39"),
        ("MAT", "41"), ("MRK", "42"), ("LUK", "43"), ("JHN", "44"), ("ACT", "45"), ("ROM", "46"), ("1CO", "47"),
        ("2CO", "48"), ("GAL", "49"), ("EPH", "50"), ("PHP", "51"), ("COL", "52"), ("1TH", "53"),
        ("2TH", "54"), ("1TI", "55"), ("2TI", "56"), ("TIT", "57"), ("PHM", "58"), ("HEB", "59"),
        ("JAS", "60"), ("1PE", "61"), ("2PE", "62"), ("1JN", "63"), ("2JN", "64"), ("3JN", "65"),
        ("JUD", "66"), ("REV", "67"),
        // deuterocanon
        ("TOB", "68"), ("JDT", "69"), ("ESG", "70"), ("WIS", "71"), ("SIR", "72"), ("BAR", "73"), ("LJE", "74"),
        ("S3Y", "75"), ("SUS", "76"), ("BEL", "77"), ("1MA", "78"), ("2MA", "79"), ("3MA", "80"),
        ("4MA", "81"), ("1ES", "82"), ("2ES", "83"), ("MAN", "84"), ("PS2", "85"), ("ODA", "86"),
        ("PSS", "87"),
        // peripherals + user-defined "extra material" books (XXA-XXG)
        ("FRT", "A0"), ("BAK", "A1"), ("OTH", "A2"), ("INT", "A7"), ("CNC", "A8"), ("GLO", "A9"), ("TDX", "B0"),
        ("NDX", "B1"), ("XXA", "94"), ("XXB", "95"), ("XXC", "96"), ("XXD", "97"), ("XXE", "98"), ("XXF", "99"),
        ("XXG", "100"),
    ];
    pairs.iter().find(|(k, _)| *k == code).map(|(_, v)| *v)
}

fn decode_document(loaded: &Loaded, doc_id: &str) -> String {
    let doc = loaded.docs.iter().find(|(id, _)| id == doc_id).map(|(_, d)| d).unwrap();
    let report = Renderer::new(doc, Phase::Report, None).render().report;
    Renderer::new(doc, Phase::Usfm, Some(&report)).render().usfm
}

fn decode_pkf(pkf_path: &Path, out_dir: &Path, book_filter: Option<&str>) -> (usize, Vec<String>) {
    let bytes = fs::read(pkf_path).expect("failed to read pkf file");
    let loaded = load_pkf(&bytes);
    fs::create_dir_all(out_dir).expect("failed to create output dir");

    let mut n = 0;
    let mut unmapped = Vec::new();
    for (doc_id, doc) in &loaded.docs {
        let book_code = doc.header("bookCode").unwrap_or("");
        if let Some(filter) = book_filter {
            if book_code != filter {
                continue;
            }
        }
        let usfm = decode_document(&loaded, doc_id);
        let name = match book_num(book_code) {
            Some(num) => format!("{}-{}.usfm", num, book_code),
            None => {
                unmapped.push(book_code.to_string());
                format!("{}.usfm", book_code)
            }
        };
        fs::write(out_dir.join(name), usfm).expect("failed to write usfm file");
        n += 1;
    }
    (n, unmapped)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut input: Option<String> = None;
    let mut out: Option<String> = None;
    let mut book: Option<String> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--out" => {
                i += 1;
                out = args.get(i).cloned();
            }
            "--book" => {
                i += 1;
                book = args.get(i).map(|s| s.to_uppercase());
            }
            other if !other.starts_with("--") && input.is_none() => {
                input = Some(other.to_string());
            }
            _ => {}
        }
        i += 1;
    }

    let Some(input) = input else {
        eprintln!("usage: pkf-decode <path-to.pkf-or-dir> [--out <dir>] [--book <BOOKCODE>]");
        exit(2);
    };

    let input_path = PathBuf::from(&input);
    let pkf_files: Vec<PathBuf> = if input_path.is_dir() {
        let mut files: Vec<PathBuf> = fs::read_dir(&input_path)
            .expect("failed to read directory")
            .filter_map(|e| e.ok())
            .map(|e| e.path())
            .filter(|p| p.extension().map(|e| e == "pkf").unwrap_or(false))
            .collect();
        files.sort();
        files
    } else {
        vec![input_path]
    };

    if pkf_files.is_empty() {
        eprintln!("[pkf-decode] no .pkf files found in {}", input);
        exit(1);
    }

    let base_out = PathBuf::from(out.unwrap_or_else(|| "out".to_string()));
    let multi = pkf_files.len() > 1;
    for pkf_path in &pkf_files {
        let base = pkf_path.file_name().unwrap().to_string_lossy();
        let base = base.split('.').next().unwrap_or(&base).to_string();
        let out_dir = if multi { base_out.join(&base) } else { base_out.clone() };
        let (n, unmapped) = decode_pkf(pkf_path, &out_dir, book.as_deref());
        let mut msg = format!("[pkf-decode] {}: {} book(s) -> {}/", base, n, out_dir.display());
        if !unmapped.is_empty() {
            msg += &format!("  (unknown book code, named without a number prefix: {})", unmapped.join(", "));
        }
        println!("{}", msg);
    }
}
