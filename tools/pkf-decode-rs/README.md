# pkf-decode-rs

Rust sibling of [`../pkf-decode/`](../pkf-decode/) (the reference JS
implementation) and [`../pkf-decode-py/`](../pkf-decode-py/) — decodes a
`.pkf` file (a Proskomma "succinct docSet", gzip-compressed JSON) into one
plain USFM file per book, byte-for-byte identical to `decode.mjs`'s output.

## Build

```bash
cargo build --release
```

Dependencies: `flate2` (gzip), `serde_json` (with `preserve_order` — header
key order matters for output, see below), `base64`.

## Usage

```bash
./target/release/pkf-decode <path-to.pkf> [--out <dir>] [--book <BOOKCODE>]
./target/release/pkf-decode <dir-of-.pkf-files> [--out <dir>]
```

Same CLI shape, output naming, and behavior as `../pkf-decode/decode.mjs`.

## Why this isn't a JS-library binding, and why some code looks "wrong"

See [`../pkf-decode-py/README.md`](../pkf-decode-py/README.md)'s "Why this
isn't a JS-library binding" section — everything there applies here too;
this is a second independent reimplementation of the same validated
algorithm, not a port of the Python code. `src/render.rs`'s module doc
comment lists the specific real-library quirks reproduced verbatim (an
unclosed word-attribute wrapper, row/table blocks silently falling through
to paragraph handling, a `cell` wrapper's tag rendering as the literal text
"undefined", attribute values always comma-joined) — do not "fix" these.

One Rust-specific note: `serde_json`'s `preserve_order` feature is required
because `Doc::headers` must iterate in the `.pkf` file's original JSON key
order (`document.usfm()`'s `\id`/`\usfm`/etc. header lines are emitted in
that order) — Rust's `HashMap` would silently reorder them.

## Module map

Mirrors `pkf-decode-py`'s module map directly:

- `byte_array.rs` — succinct format's low-level binary reader.
- `defs.rs`, `succinct.rs`, `unsuccinctify.rs`, `item.rs` — decode a block's
  `bs`/`bg`/`c` byte arrays into items.
- `load.rs` — gunzip + JSON parse into a `Doc` per book.
- `render.rs` — the succinct-driven renderer, both action sets (chapter
  report, USFM text) inlined as a `Phase`-gated match rather than a
  pluggable-closures abstraction (there are only ever two fixed action
  sets here, so Rust doesn't need the JS/Python generality).
- `main.rs` — CLI entry point, `BOOK_NUM` filename table.

## Verification

`../verify_pkf_decode.py` is the actual correctness gate — it runs this
(via the release binary), the Python sibling, and the reference
`decode.mjs` over the real PKF corpus
(`internal-data/api-cache/pkf/`, fetched via `scripts/fetch_pkf_corpus.py`)
and diffs output byte-for-byte. Run it after any change here:

```bash
cargo build --release
python3 ../verify_pkf_decode.py --only rs [--sample N]
```
