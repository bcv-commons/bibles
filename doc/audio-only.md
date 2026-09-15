# `audio-only.json`

`https://cdn.bibel.wiki/dbt/_app/audio-only.json`

A compact **exclusion** list — every iso this repo's catalog confirms has
real audio but zero real text anywhere (DBT, PKF, helloAO, or OBS).
Built for a "pick a language for reading" UI: fetch
[`language-names.json`](language-names.md) for the full picker universe,
then drop anything that appears in this file to get a reliable
text-language selector.

## Why an exclusion list, not an inclusion list

Of the full `language-names.json` universe (2,435 languages as of
2026-09-15), roughly 1,900 have real text somewhere and only **624** are
genuinely audio-only. Publishing the smaller set is the more compact
choice — same principle as `media.json`'s `audioBooksSet`/
`timingBooksSet` only appearing when coverage is partial, not
enumerating the common case.

## Shape

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "count": 624,
  "audioOnly": ["abs", "abz", "acb", "ada", ...]
}
```

`schema_version` — an integer, bumped only on a breaking shape change,
never on data changes. Currently `1`.

`audioOnly` — a flat array of ISO 639-3 codes, nothing else. No
per-canon detail, no source attribution — if you need to know *which*
source has the audio, fetch `/dbt/<iso>/media.json` or
`/dbt/<iso>/availability.json` for that specific language.

## Why not fold this into `media-index.json`

That file's own `m` field is only ever derived for languages that
contribute real audio (`"a"`/`"at"`) — a language with text but no audio
contributes nothing to it at all, so it never appears there, and adding
a bare `m: "t"` case for every text-only language would grow that
already-published file for every consumer, not just the ones asking for
this specific audio-only filter. A separate, small, single-purpose file
is cheaper for everyone who doesn't need it.

## A heavier, already-existing alternative

[`catalog/index.json`](catalog-index.md) already answers "does this
language have real text" too — by its own documented definition, a row
there means independently-fetchable text from that source. If you're
already fetching that file for other reasons, you may not need this one
at all: any iso with *no* row there and *no* `catalog/obs-index.json`
row with `media` `t`/`at` is audio-only. The tradeoffs going the other
way: `catalog/index.json` is per-`(iso, canon, source)` (3,900+ rows,
much heavier for this one question) and doesn't cover OBS text-only
languages on its own. This file is a purpose-built, much smaller
derivative of exactly that same signal (plus OBS folded in) for the one
specific "exclude audio-only from a text picker" case.
