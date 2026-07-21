# `catalog-overlap.json`

`https://cdn.bibel.wiki/dbt/_app/catalog-overlap.json`

The verified relationship data between sources, wherever more than one has
content for a language. Every comparison here is a **real text
comparison**, not a guess or a naming-convention inference — see
[`sources.md`](sources.md) for what's actually being compared.

Only covers languages where a comparison was run (i.e. where
[`catalog-index.json`](catalog-index.md) shows ≥2 sources for that
`(iso, canon)`). If a language only has one source, there's nothing to
compare — check `catalog-index.json` instead.

## Shape

```json
{
  "generated_at": "...",
  "probes": {"nt": ["REV15"], "ot": ["PSA117", "PSA51"]},
  "priority": ["pkf", "helloao", "dbt"],
  "audio_source": "dbt",
  "defaults": {"bsn:nt": "pkf", "maj:nt": "dbt"},
  "entries": [
    ["aai", "nt", "dbt", "AAIWBT"],
    ["aai", "nt", "pkf", "AAIWBT",
      [["dbt:AAIWBT", "identical", 1.0], ["helloao:aai_wbt", "identical", 1.0]],
      "aai_C01"],
    ["aai", "nt", "helloao", "AAIWBT",
      [["pkf:AAIWBT", "identical", 1.0]]],

    ["bsn", "nt", "dbt", "BSNTBL"],
    ["bsn", "nt", "pkf", "BSNPKF",
      [["dbt:BSNTBL", "phonemic_distinction", 0.9292], ["helloao:bsn_tbl", "identical", 1.0]],
      "bsn_C01"]
  ]
}
```

## Row format

`[iso, canon, source, version_id, comparisons?, source_ref?]`

- **`iso`, `canon`** — same as `catalog-index.json` (`canon` includes the
  `ntp`/`otp` Portions suffix where applicable).
- **`source`** — `dbt` / `pkf` / `helloao` (full word here, unlike the
  single-letter code in `catalog-index.json`).
- **`version_id`** — the id to reference this row by. **Reused from a
  higher-priority source when the content is verified identical** (e.g. a
  PKF row that's identical to DBT displays DBT's own id) — this is display
  convenience only; the `comparisons` array underneath always has the real
  evidence. A DBT row's `version_id` is always its own native id (DBT never
  borrows).
- **`comparisons`** — `[[ref, likely, score], ...]`, one entry per *other*
  source this row was actually compared against. `ref` is `"dbt:<id>"` /
  `"pkf:<id>"` / `"helloao:<id>"`. Present for every DBT version that
  exists, not just the closest match — a language with 5 native DBT
  versions and 1 helloAO translation gets all 5 relationships listed, not
  just the best one. **`likely`** is either the fine-grained taxonomy
  (`identical` / `orthography_convention` / `phonemic_distinction` /
  `dialect_variant` / `source_duplication` / `distinct_translation` — only
  computed for PKF-vs-DBT so far) or, for helloAO-involving comparisons,
  the coarser score-bucket tier (`identical` ≥1.0 / `near_identical` ≥0.98
  / `uncertain` ≥0.5 / `distinct` <0.5).
- **`source_ref`** — the *actual, queryable* identifier at that source,
  when it differs from the display `version_id` (e.g. a PKF collection
  filename prefix, or the real helloAO translation id when the row's
  display id was borrowed from DBT/PKF). **Always fetch content using
  `source_ref` when present, not `version_id`** — `version_id` may be a
  borrowed display label that doesn't exist as a literal id at that
  source.

## Top-level fields

- **`probes`** — which chapter(s) each comparison was actually based on.
  OT has two: `PSA117` (short, 2 verses, the default) and `PSA51` (longer,
  used to re-check any non-1.0 PSA117 result for a more statistically
  reliable verdict — a 2-verse chapter has weak discriminating power).
- **`priority`** / **`defaults`** — see [`sources.md`](sources.md). Purely
  a suggested default; every row still appears regardless of what
  `defaults` points to. Skip `defaults` entirely if you want to make your
  own choice per language rather than take the suggested one.
- **`audio_source`** — currently always `"dbt"` (see
  [`sources.md`](sources.md)).
