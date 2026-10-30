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

See **[`sources.md`](sources.md)** for what each source is (DBT, PKF and
helloAO, linked; openbible, eBible.org, CrossWire and Door43, republished
here), how to fetch content from it, and the default priority order
(`pkf` → `helloao` → `dbt` → `openbible` → `ebible` → `crosswire` →
`door43`) `catalog-index.json`/`catalog-overlap.json` use when a client
just wants one good default without deciding for itself.

Want readable openbible **text** specifically, without dealing with
Biblica's raw whole-edition zips? **[`openbible-chapters.md`](openbible-chapters.md)**
is a derived, per-chapter-fetchable endpoint (390 non-ND-only editions),
built as a cache in front of [`yaapi.bible`](https://yaapi.bible/)'s own
real extraction — no USFM parsing needed on your end.

## Runnable code examples

**[`examples/`](examples/)** — small Python and JavaScript scripts that
actually fetch content: reading `catalog-index.json`/`catalog-overlap.json`,
pulling a chapter from DBT or helloAO, downloading a `.pkf` file, and
fetching an OBS story (both `contentLayout`s). No packages to install.
Start there if you want to see real output quickly.

**[`tools/pkf-decode/`](../tools/pkf-decode/)** (JavaScript) and
[`tools/pkf-decode-py/`](../tools/pkf-decode-py/) (Python, same output) —
decoders that turn a `.pkf` file (the format PKF publishes) into plain
USFM text. `examples/fetch_pkf.js`/`.py` only download the file; this is
the decode step.

**[`tools/get-audio/`](../tools/get-audio/)** — the standard way to play a
chapter with verse timing: the audio URL (helloAO or DBT), then timing from
PKF, then audio-sync's `align/`, then DBT with your key. JavaScript, no
dependencies, runs in a browser.

**[`tools/sofria-render/`](../tools/sofria-render/)** — renders a Sofria
chapter to HTML with the same classes as SIL's Scripture App Builder.

## Reading verse text: which text, through which route

**[`text-route.json`](catalog-text-route.md)** — for every edition in
`catalog-overlap.json`, the one canonical text to read (Sofria, USJ, USX,
helloAO JSON, plain text or PKF) and where it is. Read it through
[`tools/verse-text`](../tools/verse-text/), and every client gets the same
verse text, tokens and fingerprint for the same edition.

**[`<iso[0]>/<iso>/edition-struct.json`](catalog-edition-struct.md)** — per language, per edition: name,
licence, textual basis, psalm titles, and its writing system: script (ISO
15924), direction, whether words are spaced, and the Unicode normalization
of its text, read from the text itself.

## DBT's own text/audio fileset routing

If you already know you want DBT specifically (not comparing across
sources), **[`catalog-text.json`](catalog-text.md)** and
**[`catalog-audio.json`](catalog-audio.md)** give you DBT's real fileset
ids directly — "given this DBT version, which fileset(s) actually carry
its text/audio, in what format(s)." Narrower and more mechanical than
`catalog-index.json`/`catalog-overlap.json` above; most integrations
should start with those two instead and only reach for these when you
need DBT's own routing detail.

A partial DBT edition's book set (e.g. `PORALM`: 4 NT books + 1 Tanakh book)
can't be assumed from an `"nt"`/`"ot"` canon label: its books and chapters
are in [`books.json`](catalog-books.md#dbt-book-coverage-from-a-fileset)
below. (`/dbt/<iso>/coverage.json` held the same per fileset and is being
retired.)

Each of these all-language files (`text-route.json`, `catalog-overlap.json`,
`catalog-text.json`, `catalog-audio.json`, and `dbt/_vrs/index.json` below) also comes
**per language** since 2026-10-26, at `catalog/<iso[0]>/<iso>/` next to `books.json`:
`text-route.json`, `overlap.json`, `text.json`, `audio.json`, `versification.json`. Same keys
and shape, one language's entries; most apps need one to a few languages, so fetch those.

## Book names, license, and edition metadata

**[`openbible-abbr.json`](catalog-openbible-abbr.md)** — our abbreviation
for every Biblica (openbible) project, the `o:` id in all catalog files,
with Biblica's project id behind it.

**[`books.json` (per-language)](catalog-books.md)** — vernacular book
names, license/year attribution, script direction, and font hints, merged
across DBT, PKF, and helloAO. Published one file per language
(`/catalog/<iso[0]>/<iso>/books.json`), not bundled into the files above —
reach for it once you already know which language(s) you need and want
real localized book titles for a UI, not for discovery.

## Audio, video, pictures

- **Audio** — **[`/dbt/<iso>/media.json`](dbt-timing.md)** lists, per
  language and testament, the audio filesets and which books have verse
  timing (`"at"`, `timingOnly`/`timingExcept`): DBT's (with your key),
  helloAO's and PKF's own audio (`<ISO>PKF` editions, no key, 115 languages). Timing itself comes from
  PKF first, then audio-sync's `align/`, then DBT with your own key; bibles
  publishes no timing files. [`dbt-timing.md`](dbt-timing.md) has the URLs,
  and [`tools/get-audio`](../tools/get-audio/) the code.
- **Audio existence across sources** — **[`catalog-audio-index.json`](catalog-audio-index.md)** is
  the source-agnostic existence check: "does source X have audio for this
  `(iso, canon)`" across DBT, PKF, helloAO and openbible (Biblica). DBT has
  by far the broadest real coverage; see `catalog-audio.json` above for
  its fileset routing. openbible is a real second broad source (357 audio
  projects, book-level verified) but has no fileset-routing file yet —
  query Biblica's own API directly for that (see `sources.md`). helloAO's
  real audio is small and specific (currently one edition, `BSB`) —
  check `catalog-audio-index.md` before assuming a helloAO translation
  has audio just because it has text.
- **Video, pictures** — not yet covered by anything published here.

## Open Bible Stories (OBS)

Story-format content (Open Bible Stories: 50 fixed stories, no
book/chapter/verse/canon) is a different content shape from a Bible
edition, so it publishes at its own root, `/obs/`, not `/dbt/`.

- **[`catalog-obs-index.json`](catalog-obs.md)** — existence signal, same
  `/catalog/` family as the two files above. Covers all 214 languages
  door43 has real OBS content for (93 with audio, 121 text-only), sourced
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
- **OBS story timing** — bibles publishes no OBS timing file; it comes
  from audio-sync's `align/obs/` (80 languages) and, for the 12 video-only
  languages, from video-sync's `obs-video/`. See
  [`obs-media.md`](obs-media.md#obs-story-timing) for the URLs, and
  `media.json`'s `timingStories` (and `timingSource`) for a language's coverage.

## Language display names + coverage summary

Building a language picker? Start with these two, in order:

1. **[`language-names.json`](language-names.md)** — the single,
   canonical `iso -> {name, vernacular}` lookup, unioned across every
   source this repo knows about (DBT-family, PKF, and OBS-only
   languages). Compact, name-only — nothing else. Use this to populate
   the picker itself; if you maintain your own multi-source name
   fallback logic today, this file is meant to replace it.
2. **[`/dbt/<iso>/availability.json`](language-availability.md)** — once
   a language is picked, one fetch for "what's actually available for
   it" — real editions (deduped, cross-source), audio/timing book-level
   detail, and OBS presence, joined from the files below so you don't
   have to cross-reference them yourself.

Building a **text-language** picker specifically (one that must exclude
audio-only languages)? **[`audio-only.json`](audio-only.md)** is a small
exclusion list (624 isos) — drop anything in it from
`language-names.json`'s universe to get a reliable text-only selector,
no category-string guessing. `catalog/index.json` (below) answers the
same underlying question too, if you're already fetching it for other
reasons — see `audio-only.md` for the tradeoff.

**[`langs.json` / `langs-mini.json`](catalog-langs.md)** — an older,
narrower sibling: per-language display names (`{n, v, s}`, DBT-oriented,
smaller source coverage than `language-names.json` above) bucketed by
NT, Tanakh and OBS coverage category (`with-timecode`/`audio-with-timecode`/
`syncable`/`text-only`/`audio-only`). Useful if you specifically want the
category bucketing or the ISO 15924 script code (`s`); for a plain
name lookup or picker, prefer `language-names.json` instead — it has
broader coverage (PKF- and OBS-only languages this file's DBT-oriented
derivation doesn't reach) and a smaller wire format.

## Versification per edition

**[`dbt/_vrs/index.json`](vrs-index.md)** fingerprints each DBT (and
helloAO/eBible) text edition's versification scheme (`eng`/`org`/`orgw`/
`rso`/`lxx`/`vul`/`catm`) — useful for detecting text/audio versification
mismatches within an edition, or just knowing which `.vrs` shape applies.
**[`_vrs/map/<scheme>-to-eng.json`](vrs-maps.md)** gives the real,
verse-precise crosswalk from any non-`eng` scheme to `eng` — read that doc
before assuming the (usually empty, and *not* what you want)
`crosswalk` field is the real data; the real per-verse rows are in `map`.

## New, first-published-here texts

Texts native to this project, not available from any source above, are
being prepared under [`b/`](../b/) (e.g. `b/bsb-global/`, not yet
published). Once published, they'll appear in the catalog files as their
own source, alongside `d`/`p`/`h`/`o`/`e`/`c`/`g`, rather than being folded
into an existing one.
