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
- **`source`** — single letter: `d` = DBT, `p` = PKF, `h` = helloAO. A `d`
  row means DBT's catalog has **independently fetchable text of its own**
  for this `(iso, canon)` — not just a catalog entry. Some DBT rows are
  external-source *pointers* (their text tag references helloAO's or
  eBible's text rather than hosting DBT's own) and are deliberately
  excluded, even though DBT's catalog technically lists them. Fixed
  2026-07-28 after a client hit a real cross-file contradiction: 22
  languages showed "2 sources" here (`d` + `h`) while
  [`catalog-overlap.json`](catalog-overlap.md) correctly had nothing at
  all for them, because DBT's listing never contributed anything
  independently comparable — only the pointed-to source (helloAO/eBible)
  did. If `d` appears here, `compare_all.py` can genuinely fetch
  something from it; that's now a real guarantee, not just usually true.
- **`count`** — how many distinct versions from that source exist for this
  `(iso, canon)` pair. **Omitted when exactly 1** (the overwhelming
  majority of rows) — treat a missing 4th element as `count == 1`.

## What it doesn't tell you

Whether multiple rows for the same `(iso, canon)` are actually the *same*
translation or genuinely different ones. That's exactly what
[`catalog-overlap.json`](catalog-overlap.md) is for — check there before
assuming two sources are redundant or that you're missing a real option.
