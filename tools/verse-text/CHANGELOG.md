# Changelog

A change to the verse text, tokens or a fingerprint for any input is a new major version,
because published alignments and fingerprints refer to the old output. Additions that
leave every existing output unchanged are minor versions.

## 1.0.0 (2026-10-17)

First versioned release.

- **Verse text** from USJ (`extract_usj`) and Sofria (`extract_sofria`): one rule in
  Python and JS, identical for every chapter we publish, from both formats.
- **`|` in source text** (new in this release): legacy formatting codes `|i`, `|sc`
  (opening) and `|r`, `|d` (closing) dropped; proskomma's `| default="X"` reads as `|X`,
  also when its closing quote was lost to truncation. Changes no text we publish.
- **Plain reader** (`extract_plain`, new): DBT `text_plain` verse JSON, for editions with
  no structured text only.
- **helloAO converter**: the JS version moved to `js/helloao_to_usj.mjs`
  (`../helloao-to-sofria/helloao_to_usj.mjs` re-exports it).
- **USX** (last resort): `usx_to_usj.py` (usfmtc), `usx_to_sofria.mjs` (proskomma-core,
  `|` protected).
- **Tokenizer v2 and text fingerprint v1**: lexeme-aligner's reference implementation
  (handover of 2026-10-17, CC0), copied verbatim: `bcv_tokenize.py`, `tokenize.js`,
  `text_fingerprint.mjs`.
- **Content fingerprint v1** (new, for diagnosis): letters and marks only, lowercase,
  apostrophe forms unified, NFC.
- **Conformance suite**: synthetic rule cases, 169 helloAO chapters through the whole
  chain, and 11 DBT chapters by fileset id with their fingerprints per route.
