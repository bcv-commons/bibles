# Using Bible content in your app

This repo is the **discovery layer** for Bible text (and, over time, audio,
video, and pictures) published across several independent sources. It does
not host all the content itself — it tells you what exists, where, and how
the pieces relate to each other, so you don't have to independently
discover and reconcile each source yourself.

If you're integrating Bible content into a web app for the first time,
start here.

## The two files you need

1. **[`catalog-index.json`](catalog-index.md)** — "what exists, from whom."
   A compact availability index across every source, per language, per
   testament. Start here to discover whether a language you care about has
   any content at all, and from which source(s).

2. **[`catalog-overlap.json`](catalog-overlap.md)** — "how sources relate."
   Wherever more than one source has content for the same language, this
   file tells you whether they're the same translation (verified by actual
   text comparison, not guessed) or genuinely different — so you're never
   silently shown the same text twice under two different names, and never
   miss a real second option.

Fetch `catalog-index.json` first. If it shows only one source for the
language you need, use that source directly. If it shows more than one,
check `catalog-overlap.json` for that language before deciding — it'll
tell you whether they're duplicates or distinct.

## The sources

See **[`sources.md`](sources.md)** for what DBT, PKF, and helloAO each are,
how to fetch actual content from them, and the default priority order
(`pkf` → `helloao` → `dbt`) `catalog-index.json`/`catalog-overlap.json`
use when a client just wants one good default without deciding for itself.

## A working code example

**[`tools/pkf-decode/`](../tools/pkf-decode/)** — a real, runnable decoder
that turns a `.pkf` file (the format PKF publishes) into plain USFM text.
If you're looking for a concrete "how do I actually turn this into
readable verses" example, start there.

## Audio, video, pictures

- **Audio** — currently DBT is the only source with published audio.
  A dedicated audio-sync pipeline is being built in a separate repo; once
  it publishes, this doc and the catalog files will be extended to cover
  it. Not yet reflected in `catalog-index.json`.
- **Video, pictures** — not yet covered by anything published here.

## New, first-published-here texts

This repo is starting to publish some Bible texts that aren't available
from DBT, PKF, or helloAO at all — content native to this project. Once
that begins, it'll appear in the catalog files as its own source
(alongside `d`/`p`/`h`) rather than being folded into an existing one.
