# pkf-decode

Decode a `.pkf` file (a Proskomma "succinct docSet" — the format behind
`cdn.bibel.wiki/pkf/<iso>/<collection>.pkf`, published by the `se-regional-pwa`
repo and sourced from Scripture App Builder / scriptureearth.org) into plain
USFM text, one file per book.

This is a sample client solution: PKF is a gzip-compressed JSON blob meant to
be loaded by [Proskomma](https://doc.proskomma.bible/), not read directly.
This script shows the minimum needed to get readable Scripture text out of
one — `proskomma-core`'s native `usfm` document field does the actual export,
so there's no custom parsing here.

## Setup

```bash
cd tools/pkf-decode
npm install
```

## Usage

```bash
# Decode a single .pkf file
node decode.mjs <path-to.pkf> [--out <dir>] [--book <BOOKCODE>]

# Decode every .pkf in a directory
node decode.mjs <dir-of-.pkf-files> [--out <dir>]
```

`--book` (optional) restricts output to one book (USFM/Paratext code, e.g.
`REV`, `MAT`) — useful for spot-checking a single passage instead of
exporting an entire collection.

### Example: fetch + decode a language from the CDN

```bash
curl -o aai_C01.pkf https://cdn.bibel.wiki/pkf/aai/aai_C01.Dv3gvNPV.pkf
node decode.mjs aai_C01.pkf --out out/aai --book REV
# -> out/aai/67-REV.usfm
```

The exact `.pkf` filename (with its content hash) for a given language and
collection is listed under `collections[].pkf` in
[`cdn.bibel.wiki/pkf/manifest.json`](https://cdn.bibel.wiki/pkf/manifest.json).

## Output

One `<NN>-<BOOKCODE>.usfm` file per book, standard USFM markup (`\c`, `\v`,
etc.) — the file number prefix keeps multi-book output sortable (OT 01-39,
NT 41-67, deuterocanon 68-87, peripherals after that).
