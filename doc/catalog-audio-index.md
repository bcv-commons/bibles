# `catalog-audio-index.json`

`https://cdn.bibel.wiki/catalog/audio-index.json`

Thin, source-agnostic **audio existence** index — the audio counterpart to
[`catalog-index.json`](catalog-index.md) (which is text-only). Answers one
question: "does source X have real audio for this `(iso, canon)`" — nothing
about narrators, bitrate, format, or timing detail. Row shape and
conventions are deliberately identical to `catalog-index.json` so a client
already parsing that file needs zero new logic here.

## Shape

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "sources": [
    {"d": "https://cdn.bibel.wiki/dbt/_catalog.json"},
    {"p": "https://cdn.bibel.wiki/pkf/manifest.json"},
    {"h": "https://bible.helloao.org/api/available_translations.json"},
    {"o": "https://openbible-api-1.biblica.com/projects"}
  ],
  "entries": [
    ["aaa", "nt", "d"],
    ["ahr", "nt", "o", 3],
    ["eng", "nt", "d", 12],
    ["eng", "nt", "h"],
    ["eng", "ot", "d", 8],
    ["eng", "ot", "h"]
  ]
}
```

`schema_version` (added 2026-08-26) — same convention as
[`catalog-index.json`](catalog-index.md): an integer bumped only on a
breaking shape change, never on data changes. Currently `1`.

## Row format

`[iso, canon, source, count?]` — same meaning as
[`catalog-index.json`](catalog-index.md): `canon` is `nt`/`ntp`/`ot`/`otp`
(a complete Bible gets two rows, never a combined flag); `source` is a
single letter; `count` is the number of distinct versions from that source
with real audio for this `(iso, canon)`, omitted when exactly 1.

## Where to go for more detail per source

This file only tells you *that* audio exists, not how to fetch it or what
it sounds like:

- **`d` (DBT) rows** — real routing detail (which fileset id, bitrate,
  codec, DBT's own unverified timing claim) is in
  [`catalog-audio.json`](catalog-audio.md). Which editions and books have
  real per-verse timing is in `/dbt/<iso>/media.json` (`media: "at"`,
  `timingOnly`/`timingExcept`, `timingBooks`/`timingBooksSet`); the timing
  itself comes from audio-sync or DBT, see [`dbt-timing.md`](dbt-timing.md).
- **`h` (helloAO) rows** — fetch `https://bible.helloao.org/api/<translation_id>/<BOOK>/<chapter>.json`
  and read `thisChapterAudioLinks` (one URL per narrator) directly; no
  separate routing file for helloAO exists or is planned, since the real
  population is small (see below). helloAO's BSB `hays` narration is also
  listed in `/dbt/eng/media.json` as `ENGBSBHAY`, with audio-sync timing
  (see [`dbt-timing.md`](dbt-timing.md)); the other narrators have none
  from us.
- **`p` (PKF) rows** (since 2026-10-28) — PKF's own audio, mostly on
  scriptureearth.org: playable without a key, nearly all with PKF's verse
  timing (115 languages). Each is the language's PKF edition `<ISO>PKF` in
  `/dbt/<iso>/media.json` (`audioSource: {"source": "pkf"}`); the audio URL
  and timing come from `pkf/<iso>/`, see [`dbt-timing.md`](dbt-timing.md).
  The DBT audio PKF's apps stream is DBT's and counts under `d`.
- **`o` (openbible/Biblica) rows** — real, book-level verified (not just a
  claimed `type: "audio"`; see [`sources.md`](sources.md)). No fileset-
  routing file exists for these yet (the audio equivalent of
  `catalog-text.json`) — fetch `/projects/{id}/versions` then
  `/versions/{id}/artifacts` directly against Biblica's own API for the
  real per-book MP3/Timing artifact ids. This repo does not republish the
  actual audio bytes — see `sources.md`'s Audio section for why.
  `o` also counts audiobiblia's BLL (`spa`, `nt` and `ot`, added 2026-10-27),
  whose public-domain audio we do republish next to its text:
  `audiobiblia/spa/BLL/_meta.json` → `formats.audio` (see
  [`client-chapter-formats.md`](client-chapter-formats.md)).

## Why helloAO's population is small, and how it's verified

Unlike DBT (whose audio existence is derived directly and completely from
its own raw catalog listing), helloAO's catalog (`available_translations.json`)
has **no audio-existence field at all** — the only way to know a
translation has audio is to check `thisChapterAudioLinks` on a real,
live per-chapter response. Scanning all ~1,250 helloAO translations on
every generation run isn't practical, so `h` rows here come from a small,
hand-curated, hand-verified list (`data/helloao-audio.toml`), the same
"real, tracked, curated source data" convention as
`data/version-exclude.toml`.

As of this file's first build (2026-08-14), that list has exactly **one
real entry: `BSB`** (Berean Standard Bible), three narrators
(`david`/`hays`/`souer`), both NT and OT. Checked directly against a random
sample of ~40 other translations (English and non-English) and found audio
on none of them — this is not an underscan, helloAO audio genuinely is
that narrow today. (`AAB`, helloAO's own edition, also *reports* audio
links, but they resolve to the literal same `BSB` URLs — one real
production, not two — so it isn't listed as a separate entry.)

If you know of another helloAO translation with real audio, verify it
directly (don't infer from a name or another edition) and it can be added.
