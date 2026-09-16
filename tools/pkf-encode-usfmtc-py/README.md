# pkf-encode-usfmtc-py

An **alternate** Python example for encoding a USFM file into a `.pkf`
file (a Proskomma "succinct docSet") — alongside, not replacing,
[`../pkf-encode-py/`](../pkf-encode-py/). Same output, different
USFM-*parsing* frontend: this package uses
[`usfmtc`](https://pypi.org/project/usfmtc/) (a real,
independently-maintained USFM parser published by the USFM Technical
Committee) instead of `pkf-encode-py`'s own hand-rolled
`usfm_lexer.py` tokenizer.

Why both exist: `pkf-encode-py` is dependency-free — useful for a client
who doesn't want an external library. This package is for a client who'd
rather rely on one real, maintained USFM parser for the input side, at the
cost of one pip dependency (`pip install usfmtc`).

## What's shared vs. new

The succinct-encoding backend is **not duplicated** — this package imports
`../pkf-encode-py`'s `build_pkf.build_pkf_bytes()` (assembles the final
`.pkf` JSON + gzip) and `usfm_to_items.Builder` (the block/scope/token
structure builder, already round-trip-validated against the real
proskomma-core) directly, unchanged.

The only new code:

- **`usj_to_builder.py`** — walks a USJ tree (`usfmtc.readFile(...).outUsj()`)
  and drives `Builder`'s methods, in place of `usfm_to_items.build()`'s
  own token-stream walk.
- **`encode.py`** — thin CLI: `usfmtc.readFile()` → `usj_to_builder`
  → `build_pkf_bytes()`.

Because `usfmtc` hands back an already-closed, well-formed *tree* instead
of a flat token stream, this walker turns out simpler than the original in
a few real ways — no marker-classification tables to maintain for
character or paragraph styles, no separate self-closing-field code path,
no milestone-name allowlist. See `usj_to_builder.py`'s own docstring for
the specifics (each simplification is backed by a direct check against
`Builder`'s actual byte-level output, not assumed).

## Setup

```bash
pip install usfmtc
```

## Usage

Same CLI shape as `../pkf-encode-py/encode.py`:

```bash
python3 encode.py <path-to.usfm> --lang <iso> --abbr <version-abbr> [--out <path.pkf>]
```

## Verified — full round trip, on real content

Tested the whole loop, not just parsing: for 6 real `.pkf` files (from
`cdn.bibel.wiki` / this repo's own PKF cache — `aai`, `ake`, `cbu`, `qul`,
`agn`, `zca`), decoded each book with `../pkf-decode-py`, re-encoded every
resulting `.usfm` with *this* package, decoded the new `.pkf` again with
`../pkf-decode-py`, then compared extracted verse text (via
`pipeline/core/usfm_to_verses.py`) between the original decode and the
round-tripped one.

**Result: 196 of 197 books round-tripped with 0 verse-text differences.**
The one exception (`XXD`, a peripheral book containing a table) fails with
a clear `ValueError` — tables are explicitly out of scope for
`../pkf-encode-py` too (see that package's README), so this is the
intended "raise rather than guess" behavior for an unsupported construct,
not a defect.

## Known scope gaps (same boundary as `../pkf-encode-py`)

- Tables (USJ `table`/`row`/`cell`) — raises, not silently approximated.
- `\fig`, `\ref`, `\optbreak`, and any other USJ node type this package's
  `Builder` backend has no encoding for — raises.

These match `../pkf-encode-py`'s own stated v1 scope ("core Scripture text
+ word-level attributes + milestones") — this package inherits that
backend's limits, it doesn't remove any of them.
