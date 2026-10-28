# Scheme manifest (2026-10-09)

One entry per published scheme. A client uses this to check that an edition
matches a scheme's shape, and that the map for that scheme is the one we
published. Each entry gives the shape file, the map, the pinned TVTMS
revision and what the checks found. Per-edition assignments live in
`cdn.bibel.wiki/dbt/_vrs/index.json`; its `maps` list names every map file
below.

Checksums are sha256 of the live CDN files, as of 2026-10-09 (orgw, catm and the multi-verse files: 2026-10-12; `rso-to-org.json`: 2026-10-28).

## New Testament

The maps cover Old Testament numbering differences, plus one narrow New
Testament exception (2026-10-07). Each row is read from TVTMS's own section
for that chapter:

| Chapter | Schemes | Relation (scheme → eng) | TVTMS lines |
|---|---|---|---|
| 2CO 13 | org, orgw, rso, catm | 13:12 → 13:12-13 (multi-verse); 13:13 → 13:14 | 4080-4082 |
| ACT 19 | org, orgw, rso, catm | 19:40 → 19:40-41 (multi-verse) | 4046-4047 |
| REV 12–13 | rso | 13:1 → 12:18-13:1 (multi-verse) | 4105-4106 |
| ROM 14–16 | rso | 14:24-26 → 16:25-27 (the doxology) | none: a text override in `derive_tvtms_org_eng.py`, text-checked by a partner |

Every other NT chapter is identity in every map. `vul` has no NT rows. Its
3 John 1:15 difference from eng is not mapped, because `vul` stays
Old Testament only.

## rso (Russian Synodal, reference text: helloAO `rus_syn`)

- Shape: `_vrs/rso.vrs` `56e9042dabaf53017bac48f8e82ff4cfffca91e5f9aba4d0d9caab937a33c761`
- Map: `_vrs/map/rso-to-eng.json` `cf324586456ab280dbc421a08a368f19ddd4fe295f87562ec88d3375f64c4637` (3,004 rows)
- Multi-verse: `_vrs/map/rso-to-eng.multiverse.json` `c4408debfd7fa2f23eaafb209787423788e0963887c96b2c94e0e4b4d1725f6d` (7 relations: 4 Old Testament, 3 New Testament)
- TVTMS: `902681f77a4a2975b809555ff3c35ffe3c48a1d5`
- Checks: zero collisions outside title rows; no rows in books or chapters where the shape equals English; text-checked against `rus_syn` on the cases listed in the message history (Job 39–41, Proverbs 18, Psalms 12–13 and 50–60, Jeremiah 25/26/30/38, Exodus 36/38, 1 Chronicles 6, Joshua 5–6, Leviticus 14, Daniel 3–4). Audited by lexeme-aligner (0 spine verses unmapped; 8 unreached verses, all expected).
- Not verified against text: the deuterocanon rows (1 Esdras, Sirach, Tobit, Baruch, the Letter of Jeremiah). Kept because five editions use them. Judith, Wisdom, Susanna and Bel (Daniel 13–14) have no rows.
- Not a single layout: ten IBT-family editions share some shape features but differ from `rus_syn`. They are not labelled `rso`.

## org (Hebrew, Masoretic)

- Shape: `_vrs/org.vrs` `bf70cea4115322d4b286206f240e90d12cf16abeec39ba351df1ef8cf9174e23`
- Map: `_vrs/map/org-to-eng.json` `efed1a4ea7e4e4ac5bab19f78a759ba641d0f25af086863c1fb1ff5327b83c98` (2,033 rows)
- Multi-verse: `_vrs/map/org-to-eng.multiverse.json` `63c5f9f4ee047769bbe65af21a3b2c6e1fc98f0873bc4402ba8307a8a934356b` (8 relations: 6 Old Testament, 2 New Testament)
- TVTMS: `902681f77a4a2975b809555ff3c35ffe3c48a1d5`
- Checks: Daniel included (Hebrew numbering in 3–4). Verified against the org baseline and the partner's shape check (clean).

## orgw (Hebrew numbering, English chapters)

- Shape: `_vrs/orgw.vrs` `1f00151de97901aae13f338f639fd590bc10f92b523ca4723ebc49dc764c9123`
- Map: `_vrs/map/orgw-to-eng.json` `6c088abfb15aeea37fb99ae6fb7914132322043c8039cd9716178f0ba9ba558e` (1,467 rows)
- Multi-verse: `_vrs/map/orgw-to-eng.multiverse.json` `f05f1012050e47cfb4ac11746de5b8e425d52f192031291687fb808a58852679` (6 relations: 4 Old Testament, 2 New Testament)
- TVTMS: `902681f77a4a2975b809555ff3c35ffe3c48a1d5`
- Checks: no rows in books where the shape equals English; no Daniel rows; no Numbers 17 or 1 Kings 5 chapter-boundary rows. bcv-query's shape check: 67 defects against `orgw.vrs`, as predicted. Text evidence: Louis Segond (`fra/FRNTLS`) numbers Psalm 51's title as verses 1–2 and keeps English chapters (Malachi 4), checked 2026-10-08.
- Fixed 2026-10-12: 70 rows removed from four chapters orgw numbers as English (EXO 22, 1SA 21, 2CH 2, HOS 14; org's renumbering doesn't apply there), checked against fra_lsg, swe_fol and nld_nbg. Old Testament multi-verse relations added: org's where orgw's shape and rows agree (1KI 22:43-44, PSA 13:6, ISA 63:19), plus 1SA 20:42-43 → 1SA 20:42 (orgw puts Hebrew 21:1 at 20:43; fra_lsg). Hosea 13–14 isn't uniform among orgw editions: swe_fol and nld_nbg use Hebrew chapters there (15/10), fra_lsg and `orgw.vrs` English ones (16/9).
- Job 38–41, Ecclesiastes 11–12, Hosea 13–14 (2026-10-16): orgw editions disagree in these blocks (all 35 probed; lexeme-aligner's audit raised it): five Job layouts, two of Ecclesiastes, two of Hosea. `orgw.vrs` and the map follow the majority in each: Job the Louis Segond layout (38/38/28/25, 19 editions; rows text-checked against fra_lsg), Ecclesiastes English (10/14), Hosea Hebrew (15/10). Every other layout is a per-edition variant in `_vrs/map/ot-variants.json` `95dd7d89ca23f2dddb8e0ce1b90a67fb6f69737a9ac75186855fa2138278614a` (10 variants, each text-checked), listed in the index's `ot` entries; see `doc/vrs-index.md`. `generate_vrs.py` keeps these majority values when it regenerates `orgw.vrs` from fra_lsg (`FAMILY_LAYOUT`).

## catm (Catholic Masoretic)

- Shape: `_vrs/catm.vrs` `9c76c19ed695b65704d81b6d7eca285e98961ce8c90c372543ecf9223da5bf68`
- Map: `_vrs/map/catm-to-eng.json` `ebefc0af68d678ab1f60836671f96be3cd23a84fd86d125d1f293032c7d8a724` (1,992 rows)
- Multi-verse: `_vrs/map/catm-to-eng.multiverse.json` `693634e6475faaac0107343448b72013bd8aca079a7e2619401eae972d9de2e0` (7 relations: 5 Old Testament, 2 New Testament)
- Built from org's derived rows minus the chapters catm numbers as English (`data/vrs/tvtms-catm-to-eng.derived.tsv`), compared against `org.vrs`: 51 shape exceptions recorded in the map file (chapter-level divergences from org).
- Fixed 2026-10-12: 41 rows removed from 1CH 12 and NEH 7, which catm numbers as English (fra_ncl). Old Testament multi-verse relations added where catm's shape and rows agree with org's: NUM 25:19-26:1, 1SA 20:42-21:1, 1KI 22:43-44, PSA 13:6, ISA 63:19.

## vul (Vulgate)

- Shape: `_vrs/vul.vrs` `0b8f8ea8d07e5f3bf990434b070aa50e3870fde224c4d440daa142af6c40706b`
- Map: `_vrs/map/vul-to-eng.json` `938063ad61bdb5023077078cee7abf16769bfbd004e5b0639298e64fe7c225e7` (4,101 rows, 0 shape exceptions)
- Multi-verse: `_vrs/map/vul-to-eng.multiverse.json` `80846a13fdbc3208e21d2ddcb6c8475a589844ea015b2f21367fb6daa2fab7fa` (355 relations: several Vulgate verses in one English verse, e.g. SIR 1:17-20 → SIR 1:16, or one in several). They cover 340 of the 346 Vulgate verses that have no row in the single-verse map but whose own number is another row's target. 13 TVTMS relations are flagged in the file, not published (outside our shapes, or range-to-range).
- TVTMS: `902681f77a4a2975b809555ff3c35ffe3c48a1d5` (pinned 2026-10-09). Derived by `pipeline/core/derive_tvtms_org_eng.py` from TVTMS's Latin sections: Old Testament and deuterocanon, every source valid in `vul.vrs`, every target valid in `eng.vrs`, one-to-one (no source or target used twice).
- Replaces the unpinned strongs-aligner baseline: all 2,845 of its rows are kept with the same target. Added: 1,253 rows, nearly all deuterocanon (SIR, DAN additions, TOB, JDT, WIS, BAR, 2MA).
- Added 2026-10-12: PSA 42:5 → 43:5, 125:6 → 126:6, 135:26 → 136:26. TVTMS's Latin column has one verse more at the end of these Psalms than `vul.vrs` and maps the pair to one English verse, so the relation fell outside our shape and the verse had no row; in `vul.vrs` (lat_clv) the last verse holds the whole English verse (checked against lat_clv's text). Same-shaped deuterocanon cases (SIR, 1ES, 2ES) stay flagged.
- Editions: helloAO `lat_clv`, `eng_dra`.
- Old Testament only; no New Testament rows.

## lxx (Septuagint)

- Shape: `_vrs/lxx.vrs` `abfcbfa86f888598f06cb3797cb9fe0b3854ded674e372e03d39ca9d6e6761e2`
- Map: `_vrs/map/lxx-to-eng.json` `04b561ba4d99037fa9332a6d5348e4a66f4a71107abe63addff1067a34f7abb9` (4,748 rows, including 28 Greek Esther rows; 28 rows outside our shapes, kept and listed in the map file)
- TVTMS: `902681f77a4a2975b809555ff3c35ffe3c48a1d5` (pinned 2026-10-09). Derived by `pipeline/core/derive_tvtms_org_eng.py` from TVTMS's `Greek` sections, with its second Greek edition (`Greek2`) for MAL 3, JER 34 and 4MA 7, 8, 12, the chapters where it fits `lxx.vrs` better. Book codes are mapped by `data/vrs/crosswalk-lxx.toml` (DAN → DAG, NEH → EZR chapter + 10, 2CH 37 → MAN). Greek Esther comes from the hand-curated supplement `data/vrs/esg-lxx-to-eng.tsv`.
- One-to-one: no source maps to two verses and no English verse is the target of two. Psalm titles are the one intended exception: a two-verse superscription maps both verses to the title (PSA 50:1 and 50:2 → PSA 51:title; the same for 52, 54 and 60), as in every map. The unpinned map it replaces had 141 and 191 of these (the collisions bcv-query found).
- Compared with that map: 4,748 of its 5,109 rows are kept with the same target and none are added. Dropped: 202 collision rows, and 159 rows that are now identity, mostly renumberings from the second Greek edition in chapters where the first fits `lxx.vrs` better (DEU, JOB, HAG, SIR, TOB, WIS, HOS, 1ES, ZEC, EXO), plus 15 Prayer of Manasseh rows that mapped verses to themselves.
- Multi-verse: `_vrs/map/lxx-to-eng.multiverse.json` `40dad35a96aa383a0ade94e2fc748a2e25be7a5f108392cd57651d87ab59a93b` (54 relations). Of the 118 Greek verses with no row whose own number is another row's target, they cover 32; 11 fall in passages whose verse order differs (range-to-range, not expressed), and 74 (JER 30/32, LEV 7, EXO 38-40, 1ES) have no TVTMS relation in the sections we read: still open.
- Known gap: Esther 5:1-14 (Addition D, interleaved; varies by edition) has no rows.
- Editions: helloAO `grc_bre`, `eng_boy`.
- `lxx.vrs` has no New Testament.

## Maps to the Hebrew numbering: `<scheme>-to-org` (added 2026-10-12)

One per scheme, for a client whose reference text is the Hebrew Old Testament. Same
shape as the `-to-eng` maps (`map` rows, identity elsewhere, plus a `.multiverse.json`),
and a `no_org_counterpart` list: verses with no Hebrew counterpart (Greek additions,
NEH 7:68). Scope: the 39 books of the Hebrew Bible; New Testament numbering is in
`nt-variants.json`. Built by `pipeline/core/generate_vrs_to_org.py` from the published
`-to-eng` maps (see `doc/vrs-maps.md`), so each inherits its `-to-eng` map's checks and
known gaps.

| Map | sha256 | Rows | Multi-verse | Flagged | No org counterpart |
|---|---|---|---|---|---|
| `eng-to-org.json` | `f90c427336e53c6415d93c441c3415bb183211e875c2cafeacd979465658769a` | 1,964 | 6 | 0 | 1 |
| `orgw-to-org.json` | `24e3ec7e23645e33c0a591198bd23aebc01163585841e43eb4d9577f5a4c5f79` | 715 | 2 | 0 | 1 |
| `catm-to-org.json` | `b16f5e2e1ed8bc16d5cb7d0cc0850eb940693665395a9af3c4d2808e4587ef4d` | 41 | 1 | 0 | 284 |
| `rso-to-org.json` | `e608cfd06f6c5ae3d404f5d723607a35067042a5c06ea82bf6b7e99c5a7e9d37` | 3,330 | 7 | 0 | 119 |
| `vul-to-org.json` | `6735adc65f4b1b29554c181ce40eb41bff695fdd0d8fca6e6fec5f3cd54e098b` | 3,482 | 35 | 0 | 284 |
| `lxx-to-org.json` | `30ad68cf2f77d4f93424a41683fbc503f3b019b5ceca3af89eca99751d96f7a8` | 4,388 | 20 | 69 | 158 |

Checks: `eng-to-org` is exactly `org-to-eng` inverted (PSA 13:6 as a multi-verse relation);
no org verse is the target of two rows in any map. `lxx`'s 69 flagged groups are its known
open passages (EXO 28 and 36–40, JER 25/30/32, LEV 7, 1KI 5/7, Daniel 4), where the Greek
orders verses differently. `orgw`'s one unmatched verse is NEH 7:68.
