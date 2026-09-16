# `availability.json`

`https://cdn.bibel.wiki/dbt/<iso>/availability.json`

The merged, per-language "what's available, now that you've picked this
language" rollup — one fetch instead of cross-referencing
`catalog/index.json`, `catalog/overlap.json`, `/dbt/<iso>/media.json`,
and `catalog/obs-index.json` separately. Published one file per language
that has any Bible-edition or OBS presence (1,970 languages as of
2026-09-15).

Fetch [`language-names.json`](language-names.md) first to let someone
pick a language; fetch this file next, for that one language, once
they've picked it.

## This is a join, not new data

Every field here already exists in a file this repo publishes
separately — nothing is re-derived or duplicated in full:

- **`catalog/index.json`** — real existence per `(iso, canon, source)`.
- **`catalog/overlap.json`** — verified cross-source dedup clusters
  (real text comparison, never guessed) — only present for `(iso,
  canon)` pairs that were actually fetched and compared.
- **`/dbt/<iso>/media.json`** — the `media` flag and real
  `audioBooks`/`audioBooksSet`/`timingBooks`/`timingBooksSet` detail.
- **`catalog/obs-index.json`** — OBS existence + media flag.

A client that wants to actually fetch/play a specific edition still goes
to [`catalog-text.json`](catalog-text.md)/[`catalog-audio.json`](catalog-audio.md)
(DBT's own fileset routing) or `/dbt/<iso>/media.json` for the resolved
ids — this file tells you what exists and how many genuinely distinct
options there are, not how to fetch any one of them.

## Shape

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "iso": "asm",
  "bible": {
    "nt": {
      "sources": ["d", "h"],
      "editions": [
        { "ids": ["d:ASMDPI", "h:asm_irv"] }
      ],
      "media": "at",
      "audioBooks": 27
    },
    "ot": {
      "sources": ["d", "h"],
      "editions": [
        { "ids": ["d:ASMDPI", "h:asm_irv"] }
      ],
      "media": "at",
      "audioBooks": 39,
      "timingBooks": 1,
      "timingBooksSet": ["JOS"]
    }
  },
  "obs": { "media": "t" }
}
```

`schema_version` — an integer, bumped only on a breaking shape change,
never on data changes. Currently `1`.

## `bible[canon]` fields

- **`canon`** — `nt`/`ntp`/`ot`/`otp`, same 4-value enum as
  `catalog/index.json`. Only canons with real existence appear; a
  language with only NT content has no `ot`/`otp` key at all.
- **`sources`** — single letters (`d`=DBT, `p`=PKF, `h`=helloAO), copied
  directly from `catalog/index.json`'s rows for this `(iso, canon)`.
  Always present.
- **`editions`** — **only present when `catalog/overlap.json` has a real,
  verified answer for this `(iso, canon)`.** Each entry is one of that
  file's clusters verbatim: `ids` (the real source-prefixed ids that are
  the same underlying text), and, for entries that weren't merged into a
  cluster, `likely` (`dialect_variant`/`distinct_translation`),
  `closest`, and `score` — see [`catalog-overlap.md`](catalog-overlap.md)
  for what those mean. **Absent, not fabricated, when no overlap data
  exists** — a language can have `sources: ["d","h"]` with no `editions`
  key at all, meaning both sources have something but it was never
  actually compared (see `catalog-overlap.md`'s own note on this — it
  usually means genuinely only one real candidate existed, not that
  something is missing). Never guess a single-edition merge here just
  because only one source letter is present.
- **`media`**/**`audioBooks`**/**`audioBooksSet`**/**`timingBooks`**/
  **`timingBooksSet`** — copied from `/dbt/<iso>/media.json` for the
  base testament (`nt`/`ot` only — media.json has no separate Portions
  tracking, so these never appear on an `ntp`/`otp` canon key). Omitted
  fields follow media.json's own omit-if-absent/omit-if-complete
  conventions (a `*Set` field only appears when coverage is partial).

## `obs`

A sibling key to `bible`, not nested under it — OBS has no `nt`/`ot`/
canon concept at all (see [`catalog-obs.md`](catalog-obs.md) for the
same reasoning applied to keeping `catalog/obs-index.json` separate from
`catalog/index.json`), so nesting it under `bible` would misrepresent
it. Just the `media` flag (`"t"`/`"at"`) from `catalog/obs-index.json` —
absent entirely if the language has no real OBS content. Fetch
[`/obs/<iso>/media.json`](obs-media.md) for full OBS detail (story
titles, resolved audio, license).

## openbible (Biblica) coverage

Added 2026-09-16 — see [`sources.md`](sources.md) for the full source
description. Biblica joins `bible[canon].sources` as a new source letter
(`o`) and `editions[].ids` with an `o:` prefix, the same way `d`/`p`/`h`
already work — no new sibling key, no special-casing needed on the
consuming side.

One real asymmetry worth knowing: Biblica's **audio** existence
(`catalog/audio-index.json`'s `o` rows) is not yet joined into `obs`-style
detail the way DBT's is — there's no Biblica equivalent of
`catalog-audio.json`'s fileset routing published yet, only existence. A
client wanting to actually fetch a specific Biblica audio edition needs to
query `/projects/{id}/versions` → `/versions/{id}/artifacts` directly
against Biblica's own API for the real per-book artifact ids — see
`sources.md`.
