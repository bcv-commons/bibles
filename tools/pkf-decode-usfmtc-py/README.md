# pkf-decode-usfmtc-py

An **alternate** Python example for decoding a `.pkf` file (a Proskomma
"succinct docSet") into USFM text — alongside, not replacing,
[`../pkf-decode-py/`](../pkf-decode-py/). Same input, same kind of output,
different final-generation strategy: this package hands the decoded
structure to [`usfmtc`](https://pypi.org/project/usfmtc/) (a real,
independently-maintained USFM parser/generator published by the USFM
Technical Committee) to produce the final `.usfm` text, instead of
`pkf-decode-py`'s own hand-rolled `succinct_renderer.py`/`usfm_render.py`
string builder.

Why both exist: `pkf-decode-py` is a complete, dependency-free
reimplementation — useful for a client who wants zero external
dependencies. This package is for a client who'd rather rely on one real,
maintained USFM library for the *text-generation* half, at the cost of one
pip dependency (`pip install usfmtc`).

## What's shared vs. new

The succinct-parsing half is **not duplicated** — this package imports
`../pkf-decode-py`'s `load_pkf` (gzip/JSON unpacking) and
`SuccinctRenderer` (the block/scope/token walking engine) directly, plus
`calculate_usfm_chapter_positions()` (the report pass that decides which
output block a `\c N` mark attaches to — format-agnostic, unchanged).

The only new code:

- **`usj_render.py`** — a second `SuccinctRenderer` *action set*
  (alongside `usfm_render.py`'s `_usfm_actions()`), driven by the exact
  same render events, but building a
  [USJ](https://github.com/usfm-bible/usj) (Unified Scripture JSON) tree
  instead of a flat USFM string.
- **`decode.py`** — thin CLI, hands the USJ tree to
  `usfmtc.usjtousx()` + `usfmtc.usx2usfm()` for final formatting.

## Setup

```bash
pip install usfmtc
```

## Usage

Same CLI shape as `../pkf-decode-py/decode.py`:

```bash
python3 decode.py <path-to.pkf> [--out <dir>] [--book <BOOKCODE>]
python3 decode.py <dir-of-.pkf-files> [--out <dir>]
```

## Verified — but not byte-identical to `pkf-decode-py`, by design

`usfmtc`'s generator always emits well-formed closing tags (e.g.
`\xo ...\xo*`), even for fields the *real* proskomma-core text renderer
never explicitly closes (`\fr`/`\fq`/`\xo`/etc. — see
`../pkf-decode-py/usfm_render.py`'s `_NO_END_TAG_WRAPPERS`). That's a real,
expected formatting difference, not a bug: both are valid USFM, and a
downstream USFM parser reads them identically either way.

What *was* checked, directly, on real content — not assumed: extracted
verse text (via `pipeline/core/usfm_to_verses.py`, itself `usfmtc`-based)
from both this package's and `pkf-decode-py`'s output, across 6 real
`.pkf` files fetched from `cdn.bibel.wiki` / this repo's own PKF cache
(`aai`, `ake`, `cbu`, `qul`, `agn`, `zca` — 201 books total, spanning
different scripts and structural content including footnotes/
cross-references and at least one table). **0 verse-text differences, 0
parse failures**, across all 201 books.

## Two real bugs found and fixed during that verification (kept here as a
record — not speculative, both confirmed against actual `.pkf` content)

- **Note callers are not always inline text.** A footnote/cross-reference's
  caller symbol (e.g. `"+"`) is sometimes a nested `graft` of subtype
  `"noteCaller"` to a separate one-token sub-sequence, not inline text
  inside the `\f`/`\x` block itself (confirmed directly by inspecting a
  real REV 1:1 footnote's raw succinct items). Treating every graft as a
  new note container mis-attributed this as a spurious nested `"note"`
  node with a literal `"note_caller"` marker. Fixed in `usj_render.py`'s
  `inline_graft`: only `footnote`/`xref` grafts open a new note node — any
  other graft subtype (i.e. `noteCaller`) just recurses, landing its text
  in the *already-open* note's `caller` via the same capture mechanism a
  plain inline caller would use.
- **Table cell attributes aren't all strings.** `succinct_renderer.py`'s
  cell-wrapper handling casts `nCols` to a real Python `int`
  (`"nCols": int(scope_bits[3])`) — `usfmtc`'s attribute escaper requires
  a string and raised on it. Fixed by coercing every non-list attribute
  value to `str()` in `_atts_flat()` (list-valued attributes, e.g.
  multi-value milestone atts, were already fine).

## Known scope gap (inherited, not introduced here)

Table rows/cells fall through to the generic paragraph/wrapper USJ
handling (marker `"tr"`/`"cell"`) rather than USJ's dedicated `table`/
`row`/`cell` node types — consistent with this repo's existing stance that
tables are out of scope for v1 (see `../pkf-encode-py/README.md`). Not
hit as a parse failure in the 201-book verification above, but not
independently verified against USJ's table schema either.
