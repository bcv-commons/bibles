# Scheme manifest (2026-10-09)

One entry per published scheme. A client uses this to check that an edition
matches a scheme's shape, and that the map for that scheme is the one we
published. Each entry gives the shape file, the map, the pinned TVTMS
revision and what the checks found. Per-edition assignments live in
`cdn.bibel.wiki/dbt/_vrs/index.json`; its `maps` list names every map file
below.

Checksums are sha256 of the live CDN files, as of 2026-10-09.

## New Testament

The maps cover Old Testament numbering differences, plus one narrow New
Testament exception (2026-10-07). Each row is read from TVTMS's own section
for that chapter:

| Chapter | Schemes | Relation (scheme → eng) | TVTMS lines |
|---|---|---|---|
| 2CO 13 | org, orgw, rso, catm | 13:12 → 13:12-13 (multi-verse); 13:13 → 13:14 | 4080-4082 |
| ACT 19 | org, orgw, rso, catm | 19:40 → 19:40-41 (multi-verse) | 4046-4047 |
| REV 12–13 | rso | 13:1 → 12:18-13:1 (multi-verse) | 4105-4106 |

Every other NT chapter is identity in every map. `vul` has no NT rows. Its
3 John 1:15 difference from eng is not mapped, because `vul` stays
Old Testament only.

## rso (Russian Synodal, reference text: helloAO `rus_syn`)

- Shape: `_vrs/rso.vrs` `56e9042dabaf53017bac48f8e82ff4cfffca91e5f9aba4d0d9caab937a33c761`
- Map: `_vrs/map/rso-to-eng.json` `cf324586456ab280dbc421a08a368f19ddd4fe295f87562ec88d3375f64c4637` (3,004 rows)
- Multi-verse: `_vrs/map/rso-to-eng.multiverse.json` `48defe348e12be6940d0db5cd9e50da5365cdea6d55f83880d44bc90383c81f6` (7 relations: 4 Old Testament, 3 New Testament)
- TVTMS: `902681f77a4a2975b809555ff3c35ffe3c48a1d5`
- Checks: zero collisions outside title rows; no rows in books or chapters where the shape equals English; text-checked against `rus_syn` on the cases listed in the message history (Job 39–41, Proverbs 18, Psalms 12–13 and 50–60, Jeremiah 25/26/30/38, Exodus 36/38, 1 Chronicles 6, Joshua 5–6, Leviticus 14, Daniel 3–4). Audited by lexeme-aligner (0 spine verses unmapped; 8 unreached verses, all expected).
- Not verified against text: the deuterocanon rows (1 Esdras, Sirach, Tobit, Judith, Wisdom, Baruch, the Letter of Jeremiah). Kept because five editions use them. Susanna and Bel (Daniel 13–14) have no rows.
- Not a single layout: ten IBT-family editions share some shape features but differ from `rus_syn`. They are not labelled `rso`.

## org (Hebrew, Masoretic)

- Shape: `_vrs/org.vrs` `bf70cea4115322d4b286206f240e90d12cf16abeec39ba351df1ef8cf9174e23`
- Map: `_vrs/map/org-to-eng.json` `efed1a4ea7e4e4ac5bab19f78a759ba641d0f25af086863c1fb1ff5327b83c98` (2,033 rows)
- Multi-verse: `_vrs/map/org-to-eng.multiverse.json` `814549a9d64256e36a44c59c1106e4b269156a8cf19accdd64a649690771985d` (8 relations: 6 Old Testament, 2 New Testament)
- TVTMS: `902681f77a4a2975b809555ff3c35ffe3c48a1d5`
- Checks: Daniel included (Hebrew numbering in 3–4). Verified against the org baseline and the partner's shape check (clean).

## orgw (Hebrew numbering, English chapters)

- Shape: `_vrs/orgw.vrs` `f272d18468275638c569cc7cdc19dd1b727486b64d245b080b4fb0bc48257950`
- Map: `_vrs/map/orgw-to-eng.json` `f35c76a29779d9a1e93579721493449f680befb6059360def7a98fc84ef79a64` (1,465 rows)
- Multi-verse: `_vrs/map/orgw-to-eng.multiverse.json` `e023051e1ad3ba193d51a8f0a52ec8d3f8c6eb3228be37b130d649fe2e12fc61` (2 relations, both New Testament)
- TVTMS: `902681f77a4a2975b809555ff3c35ffe3c48a1d5`
- Checks: no rows in books where the shape equals English; no Daniel rows; no Numbers 17 or 1 Kings 5 chapter-boundary rows. bcv-query's shape check: 67 defects against `orgw.vrs`, as predicted. Text evidence: Louis Segond (`fra/FRNTLS`) numbers Psalm 51's title as verses 1–2 and keeps English chapters (Malachi 4), checked 2026-10-08.

## catm (Catholic Masoretic)

- Shape: `_vrs/catm.vrs` `9c76c19ed695b65704d81b6d7eca285e98961ce8c90c372543ecf9223da5bf68`
- Map: `_vrs/map/catm-to-eng.json` `9d55b6a53b04b26b81badf07c8ece51d1e5fc110d7650a5064f6c668be0d638c` (2,033 rows)
- Multi-verse: `_vrs/map/catm-to-eng.multiverse.json` `4bc201a472ee7c02bd86e82e91c66a1998f09a4290deca5f5150d6401958e706` (2 relations, both New Testament)
- Built from the same derived org rows, compared against `org.vrs`: 50 shape exceptions recorded in the map file (chapter-level divergences from org).

## vul (Vulgate)

- Shape: `_vrs/vul.vrs` `0b8f8ea8d07e5f3bf990434b070aa50e3870fde224c4d440daa142af6c40706b`
- Map: `_vrs/map/vul-to-eng.json` `44025661ff5a6afbddac8559bc46ece29ddc661691a05f14ce0b94baa2e46dd7` (4,098 rows, 0 shape exceptions)
- TVTMS: `902681f77a4a2975b809555ff3c35ffe3c48a1d5` (pinned 2026-10-09). Derived by `pipeline/core/derive_tvtms_org_eng.py` from TVTMS's Latin sections: Old Testament and deuterocanon, every source valid in `vul.vrs`, every target valid in `eng.vrs`, one-to-one (no source or target used twice).
- Replaces the unpinned strongs-aligner baseline: all 2,845 of its rows are kept with the same target. Added: 1,253 rows, nearly all deuterocanon (SIR, DAN additions, TOB, JDT, WIS, BAR, 2MA).
- Editions: helloAO `lat_clv`, `eng_dra`.
- Old Testament only; no New Testament rows.

## lxx (Septuagint)

- Shape: `_vrs/lxx.vrs` `abfcbfa86f888598f06cb3797cb9fe0b3854ded674e372e03d39ca9d6e6761e2`
- Map: `_vrs/map/lxx-to-eng.json` `04b561ba4d99037fa9332a6d5348e4a66f4a71107abe63addff1067a34f7abb9` (4,748 rows, including 28 Greek Esther rows; 28 rows outside our shapes, kept and listed in the map file)
- TVTMS: `902681f77a4a2975b809555ff3c35ffe3c48a1d5` (pinned 2026-10-09). Derived by `pipeline/core/derive_tvtms_org_eng.py` from TVTMS's `Greek` sections, with its second Greek edition (`Greek2`) for MAL 3, JER 34 and 4MA 7, 8, 12, the chapters where it fits `lxx.vrs` better. Book codes are mapped by `data/vrs/crosswalk-lxx.toml` (DAN → DAG, NEH → EZR chapter + 10, 2CH 37 → MAN). Greek Esther comes from the hand-curated supplement `data/vrs/esg-lxx-to-eng.tsv`.
- One-to-one: no source maps to two verses and no English verse is the target of two. Psalm titles are the one intended exception: a two-verse superscription maps both verses to the title (PSA 50:1 and 50:2 → PSA 51:title; the same for 52, 54 and 60), as in every map. The unpinned map it replaces had 141 and 191 of these (the collisions bcv-query found).
- Compared with that map: 4,748 of its 5,109 rows are kept with the same target and none are added. Dropped: 202 collision rows, and 159 rows that are now identity, mostly renumberings from the second Greek edition in chapters where the first fits `lxx.vrs` better (DEU, JOB, HAG, SIR, TOB, WIS, HOS, 1ES, ZEC, EXO), plus 15 Prayer of Manasseh rows that mapped verses to themselves.
- Known gap: Esther 5:1-14 (Addition D, interleaved; varies by edition) has no rows.
- Editions: helloAO `grc_bre`, `eng_boy`.
- `lxx.vrs` has no New Testament.
