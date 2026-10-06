# Scheme manifest (draft, 2026-10-06)

One entry per published scheme. A client uses this to check that an edition
matches a scheme's shape, and that the map for that scheme is the one we
published. Each entry gives the shape file, the map, the pinned TVTMS
revision and what the checks found. Per-edition assignments live in
`cdn.bibel.wiki/dbt/_vrs/index.json`.

Checksums are sha256 of the published files, as of 2026-10-06.

## rso (Russian Synodal, reference text: helloAO `rus_syn`)

- Shape: `_vrs/rso.vrs` `56e9042dabaf53017bac48f8e82ff4cfffca91e5f9aba4d0d9caab937a33c761`
- Map: `_vrs/map/rso-to-eng.json` `cf324586456ab280dbc421a08a368f19ddd4fe295f87562ec88d3375f64c4637` (3,004 rows)
- Multi-verse: `_vrs/map/rso-to-eng.multiverse.json` `c712b0efcee7a04190a11c02272b8f6dabac3b9843a28238e0fa9757ecb62602` (4 relations)
- TVTMS: `902681f77a4a2975b809555ff3c35ffe3c48a1d5`
- Checks: zero collisions outside title rows; no rows in books or chapters where the shape equals English; text-checked against `rus_syn` on the cases listed in the message history (Job 39–41, Proverbs 18, Psalms 12–13 and 50–60, Jeremiah 25/26/30/38, Exodus 36/38, 1 Chronicles 6, Joshua 5–6, Leviticus 14, Daniel 3–4). Audited by lexeme-aligner (0 spine verses unmapped; 8 unreached verses, all expected).
- Not verified against text: the deuterocanon rows (1 Esdras, Sirach, Tobit, Judith, Wisdom, Baruch, the Letter of Jeremiah). Kept because five editions use them. Susanna and Bel (Daniel 13–14) have no rows.
- Not a single layout: ten IBT-family editions share some shape features but differ from `rus_syn`. They are not labelled `rso`.

## org (Hebrew, Masoretic)

- Shape: `_vrs/org.vrs` (from `data/vrs/org.vrs`, sha256 `bf70cea4…`)
- Map: `_vrs/map/org-to-eng.json` `459a4cced2c4e220fb9ebf556e5caff981eb6726cff259f38976d70895e40635` (2,032 rows)
- Multi-verse: `_vrs/map/org-to-eng.multiverse.json` `c0a6fbf9f6bf10d34cab2e291acace92b835126fb04ed558a4eb888ee68da1c1` (6 relations)
- TVTMS: `902681f77a4a2975b809555ff3c35ffe3c48a1d5`
- Checks: Daniel included (Hebrew numbering in 3–4). Verified against the org baseline and the partner's shape check (clean).

## orgw (Hebrew numbering, English chapters)

- Shape: `_vrs/orgw.vrs` (sha256 `f272d184…`)
- Map: `_vrs/map/orgw-to-eng.json` `b8c1b92238bb0cf2db9fe8f7900cea8d593cf524f84d1a0f4fc07fafc7f680c1` (1,464 rows)
- TVTMS: `902681f77a4a2975b809555ff3c35ffe3c48a1d5`
- Checks: no rows in books where the shape equals English; no Daniel rows; no Numbers 17 or 1 Kings 5 chapter-boundary rows. bcv-query's shape check: 67 defects against `orgw.vrs`, as predicted. Structural evidence only (no text follows orgw numbering).

## catm (Catholic Masoretic)

- Map: `_vrs/map/catm-to-eng.json` `bcbad82659b46e3b7700a118a7d83f48d8a77aa86364d282dd88f2a3d5b84693` (2,032 rows)
- Built from the same derived org rows, compared against `org.vrs`: 50 shape exceptions recorded in the map file (chapter-level divergences from org).

## Not in the manifest

- `vul`, `lxx`: not published as part of this work. `vul` is paused (no edition yet). `lxx` is later.
- NT: out of scope for these maps.
