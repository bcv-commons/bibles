# pkf-encode-py

Encodes a USFM file into a `.pkf` file (a Proskomma "succinct docSet",
gzip-compressed JSON) — the reverse direction of
[`../pkf-decode-py/`](../pkf-decode-py/). Built for publishing `bibles`'
own first-published-here content as PKF, so PKF-compatible clients
(`se-regional-pwa` and similar) can consume it.

No third-party dependencies — standard library only.

## Usage

```bash
python3 encode.py <path-to.usfm> --lang <iso> --abbr <version-abbr> [--out <path.pkf>]
```

## Scope

Targets **core Scripture text + word-level attributes + milestones**, not
full general USFM — a deliberate choice (see the conversation that led to
this package): no first-published-here content exists yet to derive real
requirements from, so the marker set is a fixed table
(`usfm_lexer.py`'s `HEADER_MARKERS`/`PARAGRAPH_MARKERS`/`CHAR_MARKERS`/
`NOTE_MARKERS`/`NOTE_CHAR_MARKERS`/`MILESTONE_MARKERS`) covering common
real Scripture markup (headers, paragraph/poetry/heading styles, character
styles, footnotes/cross-references, `\w` word attributes, `\zaln-s`/`\zaln-e`
alignment milestones) plus common front-matter/introduction markers. An
unrecognized marker raises rather than guessing — extend the tables as real
needs surface, don't silently approximate.

Tables, complex nested structures, and TSV alignment files are explicitly
out of scope for v1.

## Why this is a genuine reimplementation, not a spec transcription

There's no published spec for the succinct format (same situation
`pkf-decode-py` faced). What made this tractable despite that: the
**verification bar is round-trip** (encode → decode via the
already-validated `pkf-decode-py` reproduces the same USFM), not
byte-identical-to-the-real-library output. That means this encoder doesn't
need to replicate proskomma-core's own USFM-parsing algorithm or its enum
allocation order — it only needs to produce succinct bytes that are
*self-consistent* with what `pkf-decode-py` already knows how to read
(verified byte-for-byte against the real installed library separately).
Enum *order*, for instance, genuinely doesn't matter here — see
`enum_builder.py`.

That freedom is also why several parts of this encoder look deliberately
reverse-engineered from `pkf-decode-py`'s real-library-quirk-reproducing
behavior rather than from "how USFM is supposed to work":

- **`\w` word-attributes keep only the first attribute.** Confirmed by
  direct testing against the real renderer (not assumed): a wrapper's
  *opening* side never renders its attributes at all, and the only way to
  get an attribute onto the *closing* side (where it does render) only
  populates from the very first such item — later ones are silent no-ops.
  Milestones (`\zaln-s`) don't share this limit — their opening side does
  render attributes, and multiple accumulate correctly there. See
  `usfm_to_items.py`'s module docstring and `_close_attributed_wrapper`.
- **Closing a `\w`-with-attributes or `\zaln-s` milestone requires a
  synthetic trigger item**, because the real end scope for these is a
  structural no-op in the renderer — the wrapper only closes when a later,
  unrelated attribute-end item happens to arrive with no container open.
  `_close_attributed_wrapper()` emits exactly that trigger right after the
  tagged content. The one case that can't round-trip: an attributed `\w`
  or milestone as the literal last thing in a paragraph — matches a real
  limitation of the library itself, not a regression introduced here.
- **A `\c` chapter marker produces no rendered output of its own** — it
  only steers which *block* the chapter-position report attaches `\c N`
  to. Getting this right required understanding the report algorithm's
  actual attachment logic (see `_ensure_block`'s comment), not just USFM
  semantics.
- **Text runs are encoded as one token per contiguous run**, not properly
  split into word/punctuation/space tokens — round-trips identically
  given how the decoder concatenates tokens, with one narrow, purely
  cosmetic exception documented in `usfm_to_items.py`'s module docstring.

## Module map

- `usfm_lexer.py` — tokenizes raw USFM into a flat marker/text stream.
- `usfm_to_items.py` — the real design-heavy layer: turns that token
  stream into the block/sequence/item structure `pkf-decode-py` already
  knows how to read. Read its module docstring first.
- `byte_array.py`, `enum_builder.py`, `succinct_write.py` — the succinct
  binary format writer (write-side counterparts of `pkf-decode-py`'s
  `byte_array.py`/`succinct.py`).
- `build_pkf.py` — assembles a `Builder`'s output into the full gzip-
  compressed `.pkf` JSON structure.
- `encode.py` — CLI entry point.

## Verification

`../verify_pkf_encode_roundtrip.py` is the correctness gate: since no
first-published-here content exists yet to test against, it uses
`pkf-decode-py`'s own output on the real PKF corpus
(`internal-data/api-cache/pkf/`) as realistic USFM input — decode a real
`.pkf`, re-encode that USFM, decode again, and diff the two decoded texts
(should be identical). Most real books fail to *encode* at all
(unsupported marker — expected, given the deliberately narrower-than-full
USFM scope); what matters is zero *mismatches* among the ones that do
encode. Latest full run: 1077/1077 real round-trips clean (3 known,
documented, purely-cosmetic double-space edge cases against a much larger
run — see `usfm_to_items.py`'s module docstring).

```bash
python3 ../verify_pkf_encode_roundtrip.py --sample N --seed N [--book BOOKCODE]
```
