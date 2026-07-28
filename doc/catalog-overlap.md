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
  ≥0.98 / `uncertain` ≥0.5 / `distinct` <0.5). A singleton omits `closest`
  for two DIFFERENT reasons, distinguished by `reachable` (below) — either
  genuinely nothing existed to compare it against (e.g. the sole DBT
  edition for a language with no other source at all), or the id itself
  couldn't be fetched at all, so no comparison was even attempted.
- **`cluster.reachable`** — only present, and only ever `false`, on a
  singleton where the id's text could not be fetched — never present when
  the id *was* successfully fetched (whether compared or left an isolated
  singleton for lack of a partner). Added 2026-07-28 after a client caught
  a real ambiguity: without this field, a bare `{"ids": [...]}` row didn't
  say whether that edition was actually fine (just nothing to compare
  against) or currently broken. See `pipeline/comparison/verify_samples.py`
  and the worked example below.
- **`cluster.confirmed_removed`** — only present alongside
  `reachable: false`, for an id `verify_samples.py` positively re-verified
  as gone (previously had real, locally-sampled content; now confirmed
  dead via a live re-check) — as opposed to a plain `reachable: false` with
  no `confirmed_removed`, which just means "failed this run" and may be
  transient (`compare_all.py` retries these automatically next run).

## Worked example: a confirmed-broken edition next to a confirmed-fine one

A client (2026-07-28) flagged `wlo` (Wolio): both its only two known
editions, `dbt:WLOWTG` and `helloao:wlo_wbt`, showed as bare
`{"ids": [...]}` rows with no way to tell which one (if either) was
actually usable. The real cause: `dbt:WLOWTG`'s live fetch fails (a
persistent 404, confirmed by hand), so `helloao:wlo_wbt` — otherwise its
only possible comparison partner — has nothing to compare against either.
Now:

```json
["wlo", "nt", {"ids": ["dbt:WLOWTG"], "reachable": false}]
["wlo", "nt", {"ids": ["helloao:wlo_wbt"]}]
```

`dbt:WLOWTG`'s `reachable: false` says plainly "this one doesn't work
right now." `helloao:wlo_wbt` carrying no such field says the opposite —
it fetched fine, there's just no sibling to compare it against.

## Why NT and OT can disagree about the same-looking editions

A client flagged what looked like a bug: `BSB`/`AAB`/`eng_msb` cluster
together in NT but not in OT (this specific case is now fixed — see below),
and asked why other same-named-looking groups (WEB, Wycliffe Modern) don't
always merge consistently across both canons either. Two of the three
patterns behind that report are permanent, by-design behavior, not bugs —
worth knowing before assuming a mismatch is an error:

- **NT and OT are separately probed and separately clustered.** Every
  relationship in this file comes from comparing one specific chapter
  (`probes` above) — a real match in NT says nothing about OT, and vice
  versa. Two ids can be an exact NT duplicate and a genuinely different OT
  edition at the same time (confirmed case: DBT's `ENGWM1` is byte-identical
  to `ENGWEB`/`ENGWWH` in NT but only ~0.90 similar to them in OT — a real
  difference in the underlying editions, not a comparison error). Don't
  assume a merge (or a `likely`/`closest` value) in one canon implies
  anything about the other.
- **The 1.0 merge threshold is exact, never inferred.** A score of 0.997 is
  not "close enough" — it stays a separate entry with a `near_identical`
  relationship instead of being folded into the matching cluster. This is
  deliberate: identity here means *verified byte-for-byte equal after
  normalization*, not "a human would call these the same edition." Expect
  to see near-duplicate pairs sitting just outside a cluster they look like
  they should be in.
- **`closest` is the single highest-scoring relationship actually found, not
  the best same-named-family match.** If an edition doesn't score highly
  against anything, `closest` can point to a completely differently-named
  edition that simply scored higher than the "obvious" sibling (confirmed
  case: `eng_wyc2017`'s NT `closest` is a Douay-Rheims translation, not
  `eng_wyc2018`, because that's what actually scored highest — `eng_wyc2017`
  isn't a strong match for anything in this dataset). A low or
  unexpected-looking `closest` usually means genuinely low similarity was
  found everywhere, not a data error.

The `BSB`/`AAB`/`eng_msb` case itself *was* a real, now-fixed gap: the
helloAO-vs-helloAO same-source leg had never been run for OT at all, so OT
singletons fell back to weaker cross-source signals instead of the direct
same-source comparison. All helloAO-vs-helloAO and DBT-vs-DBT comparisons
now cover both canons.

## Two shades of `reachable: false`

A catalog-known DBT id that's never been positively confirmed reachable
(e.g. `AUSWBT`, which 404s every time it's tried) gets a bare placeholder
row with `reachable: false` and no `confirmed_removed` — "we know the
catalog lists this, but we've never gotten real content from it, and this
run failed too." A different case, caught by a client (2026-07-23):
`BENBIB` (Bengali) had been verified byte-identical to `BNGDIP` from a
real, locally-sampled fetch — then went offline on DBT's side sometime
after that sample was taken, while comparisons kept trusting the
(now-stale) cached sample and continued reporting it as a live, verified
duplicate. `pipeline/comparison/verify_samples.py` re-checks a
previously-sampled id against DBT's live API; if confirmed dead, it prunes
the stale sample and marks the id `reachable: false, confirmed_removed:
true` — a stronger, positive statement than a plain `ids_failed` entry
("this specific edition was verified real, and has since been verified
gone," not just "didn't work this run, might be transient"). An earlier
version of this pipeline fully excluded confirmed-removed ids instead of
showing them — changed after the same 2026-07-28 `wlo` feedback that added
`reachable` in the first place: silently vanishing a once-real id is just
as uninformative as an unmarked bare row, for the same reason. Run
`verify_samples.py --id <ID>` to (re-)check whether a specific id has gone
offline.

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
