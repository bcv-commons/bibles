# bibles

**The authoritative place for Bible editions in bcv-commons**: which editions exist, where
their text and audio are, how they relate to each other, and the shared rules for reading
them. Any work done on top of a Bible edition, such as audio alignment, word alignment,
stories or apps, starts from here and is coordinated through here.

## What this repo is for

- **Collect** every Bible edition we can freely collect, from every source we know of, into
  one catalog. Where a source's licence allows it and the source isn't directly usable, we
  republish the text ourselves on `cdn.bibel.wiki`.
- **Compare** editions across sources by their actual text. Same translation, a spelling or
  dialect variant, or a different translation is measured, never assumed. A client is
  never shown the same text twice under two names, and never misses a real second option.
- **Define** how to read an edition: one canonical text per edition, one extraction rule,
  one tokenizer and one fingerprint, in Python and JavaScript
  ([`tools/verse-text`](tools/verse-text/)). Every project that refers to a word or a verse
  refers to the same thing.
- **Coordinate** the projects that build on the editions. They publish their results next
  to ours, keyed to our catalog and fingerprints, and we list what they have done:

  | Project | Builds | Where |
  |---|---|---|
  | audio-sync | verse timing for audio | `cdn.bibel.wiki/align/` |
  | video-sync | timing for Open Bible Stories videos | `cdn.bibel.wiki/obs-video/` |
  | lexeme-aligner | word alignments, keyed on our text fingerprints | its own datasets |
  | bsb-add-books | new BSB-based editions; contributed written tokens to `tools/verse-text` | `b/` (not yet published) |
  | bible-story-builder | story apps built on the catalog | uses the catalog |

## Sources

**Free, no key:**

| Source | What it gives | How |
|---|---|---|
| PKF (`se-regional-pwa`) | text, audio and versification per language | linked |
| helloAO (bible.helloao.org) | text for over 1,200 editions; audio for BSB | linked |
| openbible (Biblica) and audiobiblia.org | text; audiobiblia's BLL audio | republished |
| eBible.org | editions helloAO doesn't carry | republished |
| CrossWire (SWORD modules) | text | republished |
| Door43 | Gateway Language texts with translators' word alignments | republished |
| Open Bible Stories (door43) | 50 stories, text and audio | cataloged |

**DBT, with a key.** [Digital Bible Platform / Bible Brain](https://www.digitalbibleplatform.com/),
by [Faith Comes By Hearing](https://www.faithcomesbyhearing.com/), is the one source that
needs your own API key. It is also what opens up audio: without it there are very few Bible
audio recordings, and with it there are thousands, many with verse timing. We catalog DBT
fully, so you can see what a key would give you before you get one. Fetching DBT's text,
audio and timing is done with your key, straight from DBT; we never republish it.

Full detail on each source, and the default order when several have the same text:
[`doc/sources.md`](doc/sources.md).

## Where to start

- **Using the data in an app:** [`doc/README.md`](doc/README.md), with runnable examples in
  [`doc/examples/`](doc/examples/).
- **Audio and verse timing:** [`doc/dbt-timing.md`](doc/dbt-timing.md), with the client
  code in [`tools/get-audio/`](tools/get-audio/).
- **Reading verse text the shared way:** [`tools/verse-text/`](tools/verse-text/).
- **Building on the editions** (a new project, or publishing results for an edition): talk
  to us first, so your results are keyed to the catalog and fingerprints and we can list
  them.
- **Working on the publish pipeline itself:** [`pipeline/README.md`](pipeline/README.md).
