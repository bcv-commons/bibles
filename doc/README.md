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

## Runnable code examples

**[`examples/`](examples/)** — small Python and JavaScript scripts that
actually fetch content: reading `catalog-index.json`/`catalog-overlap.json`,
pulling a chapter from DBT or helloAO, downloading a `.pkf` file, and
fetching an OBS story (both `contentLayout`s). No packages to install.
Start there if you want to see real output quickly.

**[`tools/pkf-decode/`](../tools/pkf-decode/)** — a real, runnable decoder
that turns a `.pkf` file (the format PKF publishes) into plain USFM text.
`examples/fetch_pkf.js`/`.py` only download the file; this is the actual
decode step.

## DBT's own text/audio fileset routing

If you already know you want DBT specifically (not comparing across
sources), **[`catalog-text.json`](catalog-text.md)** and
**[`catalog-audio.json`](catalog-audio.md)** give you DBT's real fileset
ids directly — "given this DBT version, which fileset(s) actually carry
its text/audio, in what format(s)." Narrower and more mechanical than
`catalog-index.json`/`catalog-overlap.json` above; most integrations
should start with those two instead and only reach for these when you
need DBT's own routing detail.

## Book names, license, and edition metadata

**[`books.json` (per-language)](catalog-books.md)** — vernacular book
names, license/year attribution, script direction, and font hints, merged
across DBT, PKF, and helloAO. Published one file per language
(`/catalog/<iso[0]>/<iso>/books.json`), not bundled into the files above —
reach for it once you already know which language(s) you need and want
real localized book titles for a UI, not for discovery.

## Audio, video, pictures

- **Audio** — **[`catalog-audio-index.json`](catalog-audio-index.md)** is
  the source-agnostic existence check: "does source X have audio for this
  `(iso, canon)`" across DBT and helloAO (PKF has a real audio endpoint
  too, not yet cataloged here — see that doc). DBT has by far the broadest
  real coverage; see `catalog-audio.json` above for its fileset routing.
  helloAO's real audio is small and specific (currently one edition, `BSB`)
  — check `catalog-audio-index.md` before assuming a helloAO translation
  has audio just because it has text. A dedicated audio-sync pipeline is
  being built in a separate repo; once it publishes, this doc and the
  catalog files will be extended to cover it.
- **Video, pictures** — not yet covered by anything published here.

## Open Bible Stories (OBS)

Story-format content (Open Bible Stories: 50 fixed stories, no
book/chapter/verse/canon) is a different content shape from a Bible
edition, so it publishes at its own root, `/obs/`, not `/dbt/`.

- **[`catalog-obs-index.json`](catalog-obs.md)** — existence signal, same
  `/catalog/` family as the two files above. Covers all 214 languages
  door43 has real OBS content for (92 with audio, 122 text-only), sourced
  directly from door43's own catalog — same principle as DBT audio
  existence being derived from DBT's own catalog, not a downstream
  pipeline.
- **[`/obs/<iso>/media.json`](obs-media.md)** — per-language detail
  (content routing, license, resolved audio URLs, per-story titles).
  Resolved directly from door43 too; exists for **every** language in the
  index above, full stop — no dependency on any staging pipeline's pace.
  Two different story-text layouts exist across languages
  (`contentLayout: "md"` for 197, `"ts-desktop"` for 17) — that doc shows
  the fetch code for both.
- **[`/obs/<iso>/timing.json`](obs-media.md#obsisotimingjson)** —
  per-story `[start, end]` timing, same shape convention as
  `/dbt/<iso>/timing/<BOOK>.json`. This one genuinely does lag: it depends
  on audio-sync's real, ongoing alignment work and covers a small,
  growing subset of the 92 audio-bearing languages — check
  `media.json`'s `timingStories` field for current coverage of a specific
  language.

## New, first-published-here texts

This repo is starting to publish some Bible texts that aren't available
from DBT, PKF, or helloAO at all — content native to this project. Once
that begins, it'll appear in the catalog files as its own source
(alongside `d`/`p`/`h`) rather than being folded into an existing one.
