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
  "maps": {...}
}
```

`l` maps `iso/abbr` (DBT) or `helloao:<id>`/`ebible:<id>` to a scheme name.
Cross-reference against [`_vrs/map/<scheme>-to-eng.json`](vrs-maps.md) for
the actual verse-level crosswalk once you know an edition's scheme.

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
  as "not checked" for these editions.
- **Psalm evidence exists but a tiebreaker is missing** (`ukr_npu`, the only
  such edition): the label is `undetermined`. The index used to write `eng`
  here, which contradicted the Psalm evidence. Fixed 2026-10-06.

If the index says `undetermined`, a client should use the verse numbers the
text gives and state that no scheme was determined. Don't assume a scheme.
