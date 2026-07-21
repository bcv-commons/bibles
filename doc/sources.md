# The three sources

## DBT (Bible Brain, Digital Bible Platform, by Faith Comes By Hearing)

The largest catalog by far, and currently the **only source with published
audio**. Real-time API, no bulk download.

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

DBT is the only source with published audio today. A separate audio-sync
pipeline (different repo) is expected to add more over time — once it
publishes, it'll be reflected here.
