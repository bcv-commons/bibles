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

Published as **clusters of genuinely distinct options**, not a raw
comparison matrix. A language with 7 DBT versions and 8 helloAO
translations doesn't mean 15 confusing, overlapping entries — items
verified identical (score == 1.0, real text comparison, never guessed) are
grouped into one cluster; everything else gets its own entry with a single
"closest relative" and a taxonomy category explaining *why* it's separate,
instead of a wall of raw scores against every other version.

Built from **five** comparison legs, not just cross-source ones: PKF-vs-DBT,
helloAO-vs-DBT, PKF-vs-helloAO, and two same-source legs — DBT's own
multiple native versions against each other, and helloAO's own multiple
translations against each other. The same-source legs matter because a
single source can independently publish more than one edition of the same
underlying translation (e.g. DBT's `SPAERV`/`SPAWTC`, which are an exact
duplicate of each other) — without comparing a source against itself, a
bare singleton from that source got no "closest relative" reference at all,
even when one existed. This is the direct fix for `spa`'s `SPARVC`
("Reina Valera 1909"), which now correctly shows a `dialect_variant`
relationship to `SPNR02` (see the example below).

## Shape

```json
{
  "generated_at": "...",
  "probes": {"nt": ["REV15"], "ot": ["PSA117", "PSA51"]},
  "priority": ["pkf", "helloao", "dbt"],
  "audio_source": "dbt",
  "entries": [
    ["aai", "nt", {"ids": ["dbt:AAIWBT", "helloao:aai_wbt", "pkf:AAIPKF"],
                    "pkf_source_ref": "aai_C01", "default": "pkf:AAIPKF"}],

    ["bsn", "nt", {"ids": ["dbt:BSNTBL"]}],
    ["bsn", "nt", {"ids": ["helloao:bsn_tbl", "pkf:BSNPKF"],
                    "pkf_source_ref": "bsn_C01", "default": "pkf:BSNPKF"}],

    ["spa", "nt", {"ids": ["dbt:SPNR02", "helloao:spa_r09"], "default": "helloao:spa_r09"}],
    ["spa", "nt", {"ids": ["dbt:SPAERV", "dbt:SPAWTC"], "default": "dbt:SPAERV"}],
    ["spa", "nt", {"ids": ["dbt:SPARVC"], "likely": "dialect_variant",
                    "closest": "dbt:SPNR02", "score": 0.9394}],
    ["spa", "nt", {"ids": ["helloao:spa_onbv"], "likely": "distinct_translation",
                    "closest": "dbt:SPANTV", "score": 0.7163}]
  ]
}
```

`dbt:SPAERV`/`dbt:SPAWTC` are a DBT-vs-DBT same-source cluster — an exact
duplicate found by comparing DBT against itself, with no other source
involved at all. `dbt:SPARVC` is a DBT-only singleton whose `closest`
reference (`dbt:SPNR02`) also comes from that same-source leg — this is the
case a client originally flagged: `SPARVC`'s name ("Reina Valera 1909")
suggested it might be another RV-family variant, and the same-source
comparison confirms it.

## Row format

`[iso, canon, cluster]`

- **`iso`, `canon`** — same as `catalog-index.json` (`canon` includes the
  `ntp`/`otp` Portions suffix where applicable).
- **`cluster.ids`** — every id in this cluster, always source-prefixed
  (`"dbt:<id>"` / `"pkf:<id>"` / `"helloao:<id>"`) — never a bare id.
  Checked directly: there's no collision across DBT/PKF-minted/helloAO id
  spaces today, but nothing structurally guarantees that stays true
  forever, so a bare id is never published as unambiguous on its own. Each
  id here is the source's own **real, queryable identifier** — never a
  borrowed display label — with one deliberate exception: `pkf:<ISO>PKF`
  is always a *minted* label (PKF has no natural per-language id of its
  own), so the real fetchable reference for it is `pkf_source_ref`
  (the `.pkf` collection filename prefix), present on any cluster
  containing a `pkf:` member.
- **`cluster.default`** — only present when `ids` has ≥2 members (a
  single-member cluster has nothing to choose between). The
  highest-priority source **actually present in this specific cluster**,
  strictly `pkf > helloao > dbt` — never a separate "which id looks
  nicer" choice. E.g. a DBT+helloAO cluster with no PKF member defaults to
  `helloao`, not `dbt`, even though DBT's id might look more established.
- **`cluster.likely` / `closest` / `score`** — only present for
  non-identical single-member clusters. `closest` is the single most
  informative relationship this item has (highest score among whatever
  was actually compared — not always vs. DBT; e.g. a PKF item's closest
  relative could be a helloAO translation instead, or a DBT item's closest
  relative could be another DBT version, via the same-source leg). `likely`
  is either the fine-grained taxonomy (`orthography_convention` /
  `phonemic_distinction` / `dialect_variant` / `source_duplication` /
  `distinct_translation` — computed per language/pair by a diagnosis pass,
  see `pipeline/research/`) or, where no diagnosis has run for that
  specific relationship, the coarser score-bucket tier (`near_identical`
  ≥0.98 / `uncertain` ≥0.5 / `distinct` <0.5). A singleton only omits
  `closest` entirely when NO comparison (cross-source or same-source) ever
  covered it — e.g. a DBT version that's the sole DBT edition for that
  language, in a language with no other source to compare against either.

## Top-level fields

- **`probes`** — which chapter(s) each comparison was actually based on.
  OT has two: `PSA117` (short, 2 verses, the default) and `PSA51` (longer,
  used to re-check any non-1.0 PSA117 result for a more statistically
  reliable verdict — a 2-verse chapter has weak discriminating power).
- **`priority`** — see [`sources.md`](sources.md). Only affects which
  member of a multi-item cluster is picked as `default`; every id is
  still listed in `ids` regardless.
- **`audio_source`** — currently always `"dbt"` (see
  [`sources.md`](sources.md)).
