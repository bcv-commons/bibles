# `dbt/_vrs/index.json` — per-edition versification fingerprint

`https://cdn.bibel.wiki/dbt/_vrs/index.json`

Classifies every DBT (and helloAO/eBible) text edition into one of the
standard schemes (`eng`/`org`/`orgw`/`rso`/`lxx`/`vul`/`catm`), fingerprinted
from cheap structural + diagnostic-verse-count signals — not a download of
the whole text. See `pipeline/core/fingerprint_versification.py`'s
docstring for the exact method.

## Shape

```json
{
  "l": {"bul/BULCBV": "org", "eng/ENGKJV": "eng", "helloao:BSB": "eng"},
  "schemes": [...],
  "sentinels": {...},
  "map_base": "...",
  "maps": [...],
  "assumed": {"helloao:GHT": "nt_only", "helloao:aaz_ubb": "no_psalm_evidence"},
  "assumed_reasons": {"nt_only": "...", "no_psalm_evidence": "...", ...}
}
```

`l` maps `iso/abbr` (DBT) or `helloao:<id>`/`ebible:<id>` to a scheme name.
Cross-reference against [`_vrs/map/<scheme>-to-eng.json`](vrs-maps.md) for
the actual verse-level crosswalk once you know an edition's scheme.

`assumed` (added 2026-10-09) lists the keys of `l` whose label is a default or rests
on partial evidence, each with a reason explained in `assumed_reasons`:

| Reason | Meaning |
|---|---|
| `nt_only` | New Testament only; labelled `eng`, Old Testament numbering unknown |
| `no_psalm_evidence` | no Psalm probe data; labelled `eng` by default |
| `ebible_direct` | eBible text not mirrored in helloAO; labelled `eng` by default |
| `tiebreaker_unconfirmed` | family known from the Psalms, deciding chapter (MAL 4, HAG 1) not confirmed |
| `book_order_only` | `rso` from Byzantine book order alone |

Every label not in `assumed` is backed by probe evidence. Treat an assumed label as
"not checked": prefer the text's own verse numbers, and say so. On 2026-10-09 there
were 994 assumed entries (889 `nt_only`, 98 `no_psalm_evidence`, 7 `ebible_direct`),
all labelled `eng`.

## Coverage is partial, and that's stated honestly, not hidden

Only editions where classification succeeded appear in `l` — an edition
missing from this file hasn't necessarily been checked, it may just be
unclassified yet (as of 2026-09-04: 234 of 437 DBT text filesets with
Psalms are classified; the rest need probes that hit real DBT API access
issues during the last run, not a methodology gap).

## Known-fixed bug (2026-09-04): don't trust Byzantine NT book order alone

Earlier builds of this index short-circuited on Byzantine NT book order,
returning `rso` without checking real Psalm-numbering evidence — wrong
for any edition with Byzantine ordering but genuinely Masoretic-numbered
Psalms (confirmed real case: `bul/BULCBV`, corrected `rso` → `org`,
verified directly against live DBT content). Fixed — `rso` is now only
returned when Byzantine order is *also* corroborated by real LXX-numbered
Psalm evidence. If you cached a scheme value from before this date for a
Byzantine-order edition, re-fetch it.

## helloAO editions: `undetermined` vs `eng` (2026-10-06)

A helloAO edition is labelled from its Psalm-numbering probes (PS117, PS51)
and tiebreakers (1SA 17, 1KI 4, HAG 1, MAL 4). Where helloAO doesn't have
those chapters, the probe can't decide, and the label is one of two cases:

- **No Psalm evidence at all** (the 98 editions with no PS117 data): the
  index labels these `eng`. This is a default, not a finding. Treat `eng`
  as "not checked" for these editions; they're listed in `assumed` as
  `no_psalm_evidence`.
- **Psalm evidence exists but a tiebreaker is missing** (`ukr_npu`, the only
  such edition): the label is `undetermined`. The index used to write `eng`
  here, which contradicted the Psalm evidence. Fixed 2026-10-06.

If the index says `undetermined`, a client should use the verse numbers the
text gives and state that no scheme was determined. Don't assume a scheme.

## Rebuilds are reproducible without `--fetch` (fixed 2026-10-09)

A probe that DBT answers with "no such chapter" (404, or no verse text) is now cached
as a `.absent` marker next to the probe files, not just left uncached. Before this, a
rebuild without `--fetch` lost 7 correct `org` labels (`bul/BULCBV` and six others):
their catalog lists a 4th Malachi chapter, DBT confirmed it doesn't exist (so `org`,
not `orgw`), but only positive results were cached. A network error or a 403 is never
recorded as absent.
