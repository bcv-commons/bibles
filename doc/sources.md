# The three sources

## DBT (Bible Brain, Digital Bible Platform, by Faith Comes By Hearing)

The largest catalog by far, and the only source with **broad, catalog-wide**
published audio (thousands of versions). Real-time API, no bulk download.

- Catalog: `https://cdn.bibel.wiki/dbt/_catalog.json` — one row per
  `[iso, distinct_id, canon, ...tags]`. `canon` is `nt`/`ntp`/`ot`/`otp`
  (`p` suffix = Portions, i.e. partial coverage — the same convention
  `catalog-index.json` reuses directly). Tags are `a:`/`A:` (audio) and
  `t:`/`T:` (text); lowercase means "append to the distinct_id to get the
  fileset id", uppercase means "this is the full fileset id already".
- Fetching actual verse text/audio requires a DBT API key against
  `https://4.dbt.io/api/...` — this repo doesn't proxy that; you'd need
  your own DBT API access to pull content directly, or read the metadata
  this repo already publishes (timing, media availability) under
  `/dbt/<iso>/`.

## PKF (published by `se-regional-pwa`, at `cdn.bibel.wiki/pkf/`)

- Manifest: `https://cdn.bibel.wiki/pkf/manifest.json` — per-language
  `collections[]`, each with a `.pkf` filename and a `catalog` filename.
- **A `.pkf` file is a gzip-compressed Proskomma "succinct docSet"** — not
  plain text, not USFM directly. Use **[`tools/pkf-decode/`](../tools/pkf-decode/)**
  (in this repo) to turn it into readable USFM.
- No API key needed to fetch the `.pkf`/`manifest.json` files themselves.
- Per-language `app-config.json` carries a `copyright` block
  (`CC-BY-NC-ND-4.0` / `CC-BY-4.0` / Public Domain, varies per language) —
  check it before redistributing decoded text.
- A real timing/audio endpoint exists per language:
  `<iso>/timing/<BOOK>-<chapter>.json`.

## helloAO (`bible.helloao.org`)

- Catalog: `https://bible.helloao.org/api/available_translations.json` —
  flat list, no API key, no documented rate limit.
- Per-chapter content: `https://bible.helloao.org/api/<id>/<BOOK>/<chapter>.json`
  — structured JSON (verses, headings, footnotes as typed blocks), not
  USFM. Straightforward to extract plain text from directly.
- Per-translation book list: `https://bible.helloao.org/api/<id>/books.json`
  — use this to check exactly which books a translation actually has
  before assuming coverage from a book count alone.
- **Has real published audio for one edition: `BSB`** (Berean Standard
  Bible), three narrators (`david`/`hays`/`souer`), verified directly
  (2026-08-14) via `thisChapterAudioLinks`/`nextChapterAudioLinks` on the
  per-chapter endpoint — e.g.
  `https://audio.bible.helloao.org/api/BSB/GEN/1/audio/hays.mp3`. Checked
  across a random sample of ~40 other translations (English and non-English)
  and found audio on none of them — this is not a general helloAO
  capability, it's one specific attached recording. `AAB` ("Accessible
  Ancients Bible", helloAO's own edition) also *reports* audio links, but
  they resolve to the same `/api/BSB/...` URLs — there is exactly one real
  audio production in helloAO's system, not two. No per-verse timing
  accompanies it (`thisChapterAudioTimings` is present in the response
  shape but empty on every chapter checked). Not currently cataloged
  anywhere this repo publishes — see
  `internal-docs/catalog-audio-ownership-architecture.md` §8 for the
  scoping notes on adding it.

## Priority (when more than one source has the same content)

```
1. pkf
2. helloao
3. dbt
```

This is the **default** `catalog-index.json`/`catalog-overlap.json` point
to when sources overlap — not a filter. Every source that has content for
a language is always listed; nothing is hidden because a higher-priority
source also has it. Pick the default if you don't have a reason to choose
otherwise; check the alternatives if you do.

## Audio

DBT is the only source with **broad** published audio (thousands of
versions, cataloged today in `catalog-audio.json`). helloAO has one real
edition with audio (`BSB` — see above), not yet cataloged by this repo. A
separate audio-sync pipeline (different repo) is expected to add more over
time via its own alignment work — once it publishes, it'll be reflected
here too.
