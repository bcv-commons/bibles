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

`l` maps `iso/abbr` (DBT), `helloao:<id>`/`ebible:<id>` or `pkf:<collection id>`
(e.g. `pkf:aai_C01`, the `.pkf` file name without its hash) to a scheme name.
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
| `near_match` | PKF custom `.vrs` within 5 chapters of the scheme; the differing chapters are in `irregular.json` |

Every label not in `assumed` is backed by probe evidence. Treat an assumed label as
"not checked": prefer the text's own verse numbers, and say so. On 2026-10-09 there
were 994 assumed entries (889 `nt_only`, 98 `no_psalm_evidence`, 7 `ebible_direct`),
all labelled `eng`.

## New Testament: `nt` and `nt-variants.json` (added 2026-10-09)

`l` describes the Old Testament and, unless the key has an `nt` entry, the New Testament
too. New Testament numbering varies on its own, so an edition can have an `nt` entry:

```json
"nt": { "pkf:abx_C01": { "variants": ["3JN1-14", "REV12-17"], "profile": "kjv" },
        "pkf:xyz_C01": { "variants": ["2CO13-13"], "unexplained": ["1CO 5"] } },
"nt_variants": "nt-variants.json"
```

- `variants`: the New Testament numbering variants the edition follows, named
  `<BOOK><chapter>-<last verse>`. They're the renumbering tests TVTMS defines (e.g.
  Revelation 12 ending at 17 instead of 18), each mapped to `eng.vrs` in
  `map_base` + `nt_variants` (`_vrs/map/nt-variants.json`).
- `profile`: a name for a common set of variants, listed in that file's `profiles`. The
  same thing as the variants, for grouping:

  | Profile | Variants | Editions (2026-10-09) |
  |---|---|---|
  | `nrsv` | `2CO13-13` | 603 |
  | `niv` | `REV12-17` (12:18 starts 13:1) | 513 |
  | `kjv` | `3JN1-14`, `REV12-17` | 172 |
  | `greek` | `2CO13-13`, `ACT19-40` (NA/UBS) | 97 |
  | `esv` | `REV12-17esv` (12:18's text ends 12:17) | 72 |

  The other 446 entries have a variant list without a profile, most often with
  `JHN7-52` (John 7:53 absent or merged into 8:1), which is a missing passage rather
  than a numbering tradition.
- `unexplained`: chapters whose length matches no scheme and no variant, usually text
  missing from that edition. Information only: number them as `eng` does.

Client rule: for a key with an `nt` entry, take New Testament rows from its variants
(identity elsewhere) and ignore the New Testament rows of the `l` scheme's map. For a key
without one, use the `l` map for both testaments, as before.

How it's found: for PKF collections, from their `.vrs` files (every chapter); for DBT and
helloAO editions, by probing the last verse of the 15 chapters TVTMS tests
(`pipeline/core/nt_probes.py`). Revelation 12 with 17 verses is told apart (KJV/NIV vs
ESV) by the lengths of 12:17 and 13:1. As of 2026-10-09, 1,903 editions have an `nt`
entry: 907 DBT, 743 helloAO, 253 PKF. An edition with fewer than 8 of the 15 tested
chapters (a partial New Testament) gets none; 53 DBT editions couldn't be probed
(44 refused with 403, 9 failing on a chapter). Chapters outside the 15 tested ones aren't probed
for DBT and helloAO, so their `unexplained` lists are from those chapters only.

## DBT New-Testament-only editions (added 2026-10-09)

DBT editions without Psalms used to be left out of `l`. The 1,480 with a New Testament
text fileset are now in, labelled `eng` and listed in `assumed` as `nt_only` (their Old
Testament numbering is unknown), with an `nt` entry where their New Testament differs.
Audio-only editions (no text to probe) are still left out.

## PKF collections (added 2026-10-09)

A PKF collection is labelled from its manifest's declared `vrs`: a scheme name (`eng`,
`org`, `rso`) as is, or a custom Paratext `.vrs` file (`pkf/_vrs/<hash>.vrs`) matched
against our schemes, testament by testament. These files record what the translation
contains, so a partly translated chapter is shorter; that alone doesn't count against a
scheme (it's listed as unexplained in `irregular.json`). A file without an Old
Testament is labelled from its New Testament and listed in `assumed` as `nt_only`.

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
