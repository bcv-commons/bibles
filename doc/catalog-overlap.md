# `catalog-overlap.json`

`https://cdn.bibel.wiki/dbt/_app/catalog-overlap.json`

The verified relationship data between sources, wherever more than one has
content for a language. Every comparison here is a **real text
comparison**, not a guess or a naming-convention inference — see
[`sources.md`](sources.md) for what's actually being compared.

Only covers `(iso, canon)` pairs where at least one id was actually
fetched and checked. If `catalog-index.json` lists an id for a language
but this file has nothing for that `(iso, canon)` at all, it means that
language had only one known candidate anywhere — nothing existed to
compare it against, so no fetch was even attempted; check
[`catalog-index.json`](catalog-index.md) for coarse per-source existence
instead (this is a deliberate exclusion, not a gap — see "What's excluded"
below).

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
  "entries": {
    "aai:nt": [
      {"ids": ["d:AAIWBT", "h:aai_wbt", "p:AAIPKF"], "pkf_ref": "aai_C01"}
    ],
    "spa:nt": [
      {"ids": ["d:SPNR02", "h:spa_r09"]},
      {"ids": ["d:SPAERV", "d:SPAWTC"]},
      {"ids": ["d:SPARVC"], "likely": "dialect_variant", "closest": "d:SPNR02", "score": 0.9394},
      {"ids": ["h:spa_onbv"], "likely": "distinct_translation", "closest": "d:SPANTV", "score": 0.7163}
    ]
  }
}
```

`d:SPAERV`/`d:SPAWTC` are a DBT-vs-DBT same-source cluster — an exact
duplicate found by comparing DBT against itself, with no other source
involved at all. `d:SPARVC` is a DBT-only singleton whose `closest`
reference (`d:SPNR02`) also comes from that same-source leg — this is the
case a client originally flagged: `SPARVC`'s name ("Reina Valera 1909")
suggested it might be another RV-family variant, and the same-source
comparison confirms it.

## Row format (revised 2026-07-28 for compactness — see below)

`entries["<iso>:<canon>"] = [cluster, cluster, ...]` — grouped by language
and testament so a language with many clusters (e.g. `eng`/`nt` has 40+)
doesn't repeat the same two strings on every row.

- **`iso`, `canon`** — same as `catalog-index.json` (`canon` includes the
  `ntp`/`otp` Portions suffix where applicable), joined with `:` as the key.
- **`cluster.ids`** — every id in this cluster, always source-prefixed with
  a single letter — `d:` (DBT), `h:` (helloAO), `p:` (PKF) — matching
  `catalog-index.json`'s own source-code convention, never a bare id.
  Checked directly: there's no collision across DBT/PKF-minted/helloAO id
  spaces today, but nothing structurally guarantees that stays true
  forever, so a bare id is never published as unambiguous on its own. Each
  id here is the source's own **real, queryable identifier** — never a
  borrowed display label — with one deliberate exception: `p:<ISO>PKF`
  is always a *minted* label (PKF has no natural per-language id of its
  own), so the real fetchable reference for it is `pkf_ref` (the `.pkf`
  collection filename prefix), present on any cluster containing a `p:`
  member.
- **No `default` field.** A multi-id cluster used to carry a computed
  `default` (the highest-priority source present, per `priority` below) —
  removed 2026-07-28. Any client that wants a single preferred id can
  derive it in one line from `priority` + `ids` themselves; publishing a
  field for something every client can trivially compute added a field to
  every multi-id cluster for no real benefit. `priority` is unchanged and
  is the authoritative place this convention lives — **apply it yourself**:
  sort `ids` by each id's source position in `priority` and take the first.
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
  ≥0.98 / `uncertain` ≥0.5 / `distinct` <0.5). A singleton with none of
  these three fields means: confirmed fetched with real content, but no
  comparison partner existed to score it against (see `wlo`'s
  `h:wlo_wbt` below) — distinct from `r: false` (next).
- **`cluster.r`** — only present, and only ever `false`, on a singleton
  where the id's text could not be fetched — never present when the id
  *was* successfully fetched (whether compared or left an isolated
  singleton for lack of a partner). Added 2026-07-28 after a client caught
  a real ambiguity: without this field, a bare `{"ids": [...]}` row didn't
  say whether that edition was actually fine (just nothing to compare
  against) or currently broken. See `pipeline/comparison/verify_samples.py`
  and the worked example below.
- **`cluster.confirmed_removed`** — only present alongside `r: false`, for
  an id `verify_samples.py` positively re-verified as gone (previously had
  real, locally-sampled content; now confirmed dead via a live re-check) —
  as opposed to a plain `r: false` with no `confirmed_removed`, which just
  means "failed this run" and may be transient (`compare_all.py` retries
  these automatically next run). Occurs on only 2 rows in the whole file
  today (`BENBIB`) — deliberately NOT abbreviated further, unlike `r`: at
  this frequency, shortening it saves under 30 bytes total while making an
  already-rare, important flag needlessly cryptic. `ids`/`likely`/`closest`/
  `score` are the same way — their own *values* average 12-20 characters,
  so shrinking a 6-7 character key barely moves the needle, and a bare
  single letter (`l`/`c`) would read ambiguously next to a field like
  `confirmed_removed`.

## What's excluded: never-attempted single-candidate ids

If an `(iso, canon)` had exactly one known candidate anywhere (across
DBT+PKF+helloAO combined) — nothing to compare it against — `compare_all.py`
skips fetching it at all, and it gets **no row in this file whatsoever**.
This is not a gap: `catalog-index.json` already tells you a source has
*something* for that language, and checking reachability for an id with
zero possible comparison partners produces no information beyond "yes,
one edition exists" — which the index already gives you. Before 2026-07-28
these were published as bare `{"ids": [...]}` placeholder rows anyway; they
made up 1775 of 4222 rows (42%) for zero benefit and were removed.

This is a genuinely different case from a bare row that IS still published
— see the worked example below.

## Worked example: a confirmed-broken edition next to a confirmed-fine one

A client (2026-07-28) flagged `wlo` (Wolio): both its only two known
editions, `dbt:WLOWTG` and `helloao:wlo_wbt`, showed as bare `{"ids": [...]}`
rows with no way to tell which one (if either) was actually usable. The
real cause: `dbt:WLOWTG`'s live fetch fails (a persistent 404, confirmed by
hand), so `helloao:wlo_wbt` — otherwise its only possible comparison
partner — has nothing to compare against either. Now:

```json
"wlo:nt": [
  {"ids": ["d:WLOWTG"], "r": false},
  {"ids": ["h:wlo_wbt"]}
]
```

`d:WLOWTG`'s `r: false` says plainly "this one doesn't work right now."
`h:wlo_wbt` carrying no such field says the opposite — it fetched fine,
there's just no sibling to compare it against. Both rows are still
published (unlike the never-attempted case above) precisely because both
carry real, positively-confirmed information: one edition is broken, the
other is confirmed real and fetchable.

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

## Two shades of `r: false`

A catalog-known DBT id that's never been positively confirmed reachable
(e.g. `AUSWBT`, which 404s every time it's tried) gets a bare placeholder
row with `r: false` and no `confirmed_removed` — "we know the catalog
lists this, but we've never gotten real content from it, and this run
failed too." A different case, caught by a client (2026-07-23): `BENBIB`
(Bengali) had been verified byte-identical to `BNGDIP` from a real,
locally-sampled fetch — then went offline on DBT's side sometime after
that sample was taken, while comparisons kept trusting the (now-stale)
cached sample and continued reporting it as a live, verified duplicate.
`pipeline/comparison/verify_samples.py` re-checks a previously-sampled id
against DBT's live API; if confirmed dead, it prunes the stale sample and
marks the id `r: false, confirmed_removed: true` — a stronger, positive
statement than a plain `ids_failed` entry ("this specific edition was
verified real, and has since been verified gone," not just "didn't work
this run, might be transient"). An earlier version of this pipeline fully
excluded confirmed-removed ids instead of showing them — changed after the
same 2026-07-28 `wlo` feedback that added `r` in the first place: silently
vanishing a once-real id is just as uninformative as an unmarked bare row,
for the same reason. Run `verify_samples.py --id <ID>` to (re-)check
whether a specific id has gone offline.

## Top-level fields

- **`probes`** — which chapter(s) each comparison was actually based on.
  OT has two: `PSA117` (short, 2 verses, the default) and `PSA51` (longer,
  used to re-check any non-1.0 PSA117 result for a more statistically
  reliable verdict — a 2-verse chapter has weak discriminating power).
- **`priority`** — see [`sources.md`](sources.md). The convention a client
  should apply themselves to pick one preferred id from a multi-id
  cluster (no `default` field is published — see "Row format" above);
  every id is still listed in `ids` regardless of priority.
- **`audio_source`** — currently always `"dbt"` (see
  [`sources.md`](sources.md)).

## Format notes

The published file is minified (no whitespace) — pretty-print it yourself
if reading by hand. Source prefixes in `ids`/`closest` are single letters
(`d`/`h`/`p`), not the full source name — see "Row format" above.
