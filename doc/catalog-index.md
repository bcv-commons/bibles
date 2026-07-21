# `catalog-index.json`

`https://cdn.bibel.wiki/dbt/_app/catalog-index.json`

Thin existence/availability index across all three sources. Answers "what
exists, from whom, for this language, complete or partial" — nothing else.
No comparison data here; see [`catalog-overlap.json`](catalog-overlap.md)
for that.

## Shape

```json
{
  "generated_at": "...",
  "sources": [
    {"d": "https://cdn.bibel.wiki/dbt/_catalog.json"},
    {"p": "https://cdn.bibel.wiki/pkf/manifest.json"},
    {"h": "https://bible.helloao.org/api/available_translations.json"}
  ],
  "entries": [
    ["aai", "nt", "d"],
    ["aai", "nt", "h"],
    ["aai", "nt", "p"],
    ["aau", "ntp", "d"],
    ["xyz", "nt", "h", 2]
  ]
}
```

## Row format

`[iso, canon, source, count?]`

- **`iso`** — ISO 639-3 language code.
- **`canon`** — one of `nt` / `ntp` / `ot` / `otp`. The `p` suffix means
  **Portions** (partial coverage), matching DBT's own convention exactly.
  A language with a complete Bible gets **two rows** — one `nt`, one
  `ot` — never a combined "full bible" flag. Testament coverage is always
  assessed independently.
- **`source`** — single letter: `d` = DBT, `p` = PKF, `h` = helloAO.
- **`count`** — how many distinct versions from that source exist for this
  `(iso, canon)` pair. **Omitted when exactly 1** (the overwhelming
  majority of rows) — treat a missing 4th element as `count == 1`.

## What it doesn't tell you

Whether multiple rows for the same `(iso, canon)` are actually the *same*
translation or genuinely different ones. That's exactly what
[`catalog-overlap.json`](catalog-overlap.md) is for — check there before
assuming two sources are redundant or that you're missing a real option.
