# pkf-decode-py

Python sibling of [`../pkf-decode/`](../pkf-decode/) (the reference JS
implementation) — decodes a `.pkf` file (a Proskomma "succinct docSet",
gzip-compressed JSON) into one plain USFM file per book, byte-for-byte
identical to `decode.mjs`'s output.

No third-party dependencies — standard library only.

## Usage

```bash
python3 decode.py <path-to.pkf> [--out <dir>] [--book <BOOKCODE>]
python3 decode.py <dir-of-.pkf-files> [--out <dir>]
```

Same CLI shape, output naming, and behavior as `../pkf-decode/decode.mjs` —
see that package's README for examples.

## Why this isn't a JS-library binding

This is not a thin wrapper around `proskomma-core` — it's an independent
reimplementation of the one narrow feature `decode.mjs` actually uses:
decoding the succinct binary item format and reproducing the two-pass
succinct-driven render `document.usfm()` performs internally. There is no
published spec for the succinct format; this was built by reading
`proskomma-core`'s and `proskomma-json-tools`' real source (note: the
*installed* `proskomma-core@0.11.3` bundles its own copy of the render
pipeline inline — it does not go through the sibling `proskomma-json-tools`
package the way the readable checkouts of both projects' source suggest)
and validating byte-for-byte against real `.pkf` files from
`cdn.bibel.wiki/pkf/` throughout.

Several behaviors in this port look like bugs on a read-through and are
deliberately **not** "fixed" — they're real, confirmed quirks of the actual
installed library, reproduced because the goal is byte-for-byte parity with
`decode.mjs`, not "more correct" USFM. See `succinct_renderer.py`'s and
`usfm_render.py`'s docstrings/comments for the specifics (an unclosed
word-attribute wrapper, row/table blocks silently falling through to
paragraph handling, a `cell` wrapper's tag rendering as the literal text
"undefined", attribute values always comma-joined).

## Module map

- `byte_array.py` — the succinct format's low-level binary reader (base-128
  varints, counted UTF-8 strings, base64-encoded blocks).
- `defs.py`, `succinct.py`, `unsuccinctify.py` — decode a block's `bs`/`bg`/`c`
  byte arrays into `(type, subType, payload)` items.
- `load.py` — gunzip + JSON parse a `.pkf` file into a `Doc` per book.
- `succinct_renderer.py` — the succinct-driven event walker (mirrors the
  real `PerfRenderFromProskomma` class).
- `usfm_render.py` — the two action sets it's driven with (chapter-position
  report, then USFM text) and the CLI-facing decode functions.
- `decode.py` — CLI entry point, `BOOK_NUM` filename table.

## Verification

`../verify_pkf_decode.py` is the actual correctness gate — it runs this,
the Rust sibling, and the reference `decode.mjs` over the real PKF corpus
(`internal-data/api-cache/pkf/`, fetched via `scripts/fetch_pkf_corpus.py`)
and diffs output byte-for-byte. Run it after any change here:

```bash
python3 ../verify_pkf_decode.py --only py [--sample N]
```
