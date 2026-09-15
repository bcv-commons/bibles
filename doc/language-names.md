# `language-names.json`

`https://cdn.bibel.wiki/dbt/_app/language-names.json`

A single, compact `iso -> {name, vernacular}` lookup covering every
language this repo's catalog knows about from any source — built for a
"pick a language before you know what's in it" UI (a selection list),
not media detail. If you're maintaining your own multi-source fallback
logic to resolve a language's display name, this file is meant to let
you delete it and read this instead.

## Why this exists

Built 2026-09-15 after a real, client-reported bug: a PKF-only language
(`ivv`/Ivatan) had a real name in PKF's own manifest, but the client's
own name-resolution code hadn't been taught to look there, so it silently
fell back to showing the raw ISO code. This file is the single place that
already does the cross-source union so no client has to maintain that
logic independently.

## Shape

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "count": 2435,
  "l": {
    "ivv": "Ivatan",
    "eng": "English",
    "cmn": ["Chinese", "中文"],
    "ar-xzn": ["Khuzestani Arabic", "عربی-خوزستان"]
  }
}
```

`schema_version` — an integer, bumped only on a breaking shape change,
never on data changes (new languages, name corrections, etc. never bump
it). Currently `1`.

## Row format

`l[iso]` is either a bare string (just the name — no distinct vernacular
known, or it's identical to the name) or a `[name, vernacular]` array.
Never an object with named keys — this was a deliberate compactness
choice: measured across the real 2,532-language catalog, this shape is
23% smaller minified than a per-language `{"nm":..,"v":..}` object (see
git history for the measurement), and a client only ever needs one of two
checks (`typeof v === "string"` vs an array) to read either case.

No script code, text direction, or source-provenance field — this file
is deliberately scoped to exactly what a selection list needs. If you
need script/direction, see [`catalog-langs.json`](catalog-langs.md)
(`{n, v, s}`, DBT-oriented, narrower source coverage) or
`/dbt/<iso>/availability.json` ([doc](language-availability.md)) once
you've actually picked a language.

## Sources, in priority order (first found wins)

1. `/dbt/_app/media-index.json`'s own name resolution — helloAO's
   catalog, then the DBS bible-details cache, then (last resort)
   `ALL-langs-compact.json`. See [`catalog-langs.md`](catalog-langs.md)
   for how that resolution itself works.
2. **PKF's manifest** (`https://cdn.bibel.wiki/pkf/manifest.json`) — the
   source `media-index.json` never included, and the direct cause of the
   `ivv` bug above. Adds languages PKF has that no DBT-family source
   does (19 as of 2026-09-15).
3. **OBS existence** (`catalog/obs-index.json`) — unions in every
   OBS-only language too, so a language whose only real content is Open
   Bible Stories is still selectable. OBS's own per-language
   `media.json` carries no name field at all, so these are resolved via
   `data/obs-unresolved-language-names.toml`, a maintained table in this
   repo (see below) — sourced primarily from door43's own per-repo
   `language_title` (the actual content owner's chosen title), with a
   handful still needing a manual literature check (private-use dialect
   tags and retired ISO codes) when door43's title alone isn't decisive.
   As of 2026-09-15 all 87 OBS-only gaps are resolved — 0 fall back to
   the bare ISO code.

## A note on trust

Every name in this file traces back to a real source this repo can
point to — nothing here is inferred from the ISO code itself or guessed.
Where two real sources disagreed during construction (notably several
Romani-family dialect codes, where a generic ISO 639-3 registry lookup
gave a flatly wrong subgroup name), the more specific, directly-sourced
answer won — see `data/obs-unresolved-language-names.toml`'s header
comments for the full reasoning on each contested case, kept there
rather than summarized away here.
