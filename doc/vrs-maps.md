# `_vrs/map/<scheme>-to-eng.json` — cross-scheme verse crosswalks

`https://cdn.bibel.wiki/_vrs/map/org-to-eng.json`
`https://cdn.bibel.wiki/_vrs/map/rso-to-eng.json`
(also `lxx`/`vul`/`catm`/`orgw`)

Real, verse-precise crosswalks from each non-`eng` versification scheme to
`eng` (KJV), derived from TVTMS (STEPBible-Data, CC BY 4.0). Answers "given
a verse reference in scheme X, what's the corresponding reference in `eng`
numbering" — precisely, not by reconstructing it from `.vrs` chapter/verse
*counts* (see the note on that below).

The verse rows are in `map`. The `crosswalk` field (empty for most schemes)
is a smaller, different thing: book renames only. See below.

## Shape

```json
{
  "source_scheme": "org",
  "target_scheme": "eng",
  "authority": "TVTMS — Translators Versification Traditions, STEPBible-Data (CC BY 4.0)",
  "note": "Single-verse diffs only; identity elsewhere.",
  "crosswalk": {},
  "map": [
    {"s": "PSA 3:1", "t": "PSA 3:title", "a": "Renumber title"},
    {"s": "PSA 3:2", "t": "PSA 3:1", "a": "Renumber verse"}
  ],
  "exceptions": [...]
}
```

## `map` is the real per-verse crosswalk — this is what you want

A flat list of `{s: source_ref, t: target_ref, a: action}` rows, one per
verse that actually differs between the two schemes. **Only rows for
verses that change are present** — the note's "identity elsewhere" is
literal: if a verse isn't in `map`, its reference is unchanged.

## `crosswalk` is a different, much narrower thing — book-level renames only

Not a smaller or partial version of `map` — a completely separate concern:
whether the *book codes themselves* need renaming/dropping between the two
schemes (e.g. a scheme using non-standard book IDs). For org/rso — and
most scheme pairs here — no book renames are needed at all, so
`crosswalk` is legitimately `{}`. It is **not** where the verse-level data
lives; don't infer anything about map completeness from it being empty.

## The one real gotcha: identity rows at a merge/split chapter boundary

"Identity elsewhere" holds for in-chapter renumbering, but at a
book-structure MERGE or SPLIT point, a verse can keep its **own verse
number** while still needing a **chapter re-assignment** — and that case
is *also* omitted from `map`, since the row format only declares full
`source_ref -> target_ref` changes, and "same verse number, different
chapter" still counts as "no diff to declare" under this convention.

Concrete example (found 2026-09-04, prompted by a client report): `rso PSA
114` is the first half of the Masoretic/`eng` Psalm 116 split. Before
2026-10-05, `map` had no row for `rso PSA 114:9 -> eng PSA 116:9`, because
verse number 9 matches on both sides. The rebuilt `rso` map (2026-10-05)
now declares that row explicitly, so a client that reads `map` gets it
without filling any gap. The gap rule below still applies to any other
identity-number verse that changes chapter.

**How to resolve it as a consumer**: walk `map` in verse order; at any
gap between two consecutive rows, the missing verse(s) belong to the
**same target chapter as the nearest surrounding rows**, with their
original verse number unchanged. In the example above, the gap
(`rso 114:9`) sits between rows ending in `eng 116:8` and starting at
`eng 116:10` — so it belongs to `eng PSA 116`, verse 9. Don't try to
derive this from `.vrs` chapter/verse *counts* alone (summing counts
across a merge/split range accumulates no information about exactly
where the boundary falls verse-by-verse) — `map`'s row sequence already
tells you precisely, you just have to fill the gaps by adjacency rather
than expect an explicit row for every single verse.

## Merged and split verses: `<scheme>-to-eng.multiverse.json`

`map` only holds one verse to one verse. Where the two schemes divide the text
differently (one verse in one scheme is two in the other), the relation is in the
sibling file `https://cdn.bibel.wiki/_vrs/map/<scheme>-to-eng.multiverse.json`, the
same shape with a range on one side:

```json
{"s": "1SA 20:42-21:1", "t": "1SA 20:42"}   // two org verses are one eng verse
{"s": "PSA 13:6", "t": "PSA 13:5-6"}       // one org verse is two eng verses
{"s": "ISA 63:19", "t": "ISA 63:19-64:1"}  // the second half of org 63:19 is eng 64:1
```

Read both files. For a verse inside a multiverse relation, the relation is the
answer, and it overrides identity: without it, org `1SA 21:1` would keep its number
and collide with org `21:2 → 21:1`. A verse can also have a `map` row (org `PSA 13:6 →
PSA 13:5`): that row gives the first verse of the range only, for a client that wants
a single verse; the multiverse relation is the full answer.

For `org`, these are the six Old Testament places where Hebrew and English split a
verse differently: NUM 25:19 / 26:1, 1SA 20:42 / 21:1, 1KI 22:43-44, 1CH 12:4-5,
PSA 13:5-6 and ISA 63:19 / 64:1, plus two in the New Testament (ACT 19:40-41,
2CO 13:12-13). `orgw`, `catm` and `rso` have the ones that hold in their own
numbering (e.g. `orgw` puts Hebrew 1SA 21:1 at 20:43, so its relation is
`1SA 20:42-43 → 1SA 20:42`); `vul` and `lxx` have their own, from TVTMS's Latin and
Greek sections. Each file lists TVTMS's own evidence (line and action) per relation,
and any relation it couldn't express (`flagged_not_published`; for `org`, NEH 7:68,
which most Hebrew manuscripts lack). The `data/vrs/tvtms-*-to-eng.derived.tsv` files
in this repo are the single-verse rows only: use the published JSON.

## Maps to the Hebrew numbering: `_vrs/map/<scheme>-to-org.json` (added 2026-10-12)

`https://cdn.bibel.wiki/_vrs/map/<scheme>-to-org.json` and `.multiverse.json`, for
`eng`, `orgw`, `catm`, `rso`, `vul` and `lxx`: a scheme's verse in the Hebrew (`org`)
numbering, for a client whose reference text is the Hebrew Old Testament. Read them like
the `-to-eng` maps: a `map` row where the number changes, identity elsewhere, merged and
split verses in the multiverse file.

```json
{"s": "PSA 51:1", "t": "PSA 51:3"}            // eng-to-org: eng doesn't number the title
{"s": "1SA 20:43", "t": "1SA 21:1"}           // orgw-to-org
{"s": "PSA 13:5-6", "t": "PSA 13:6"}          // eng-to-org.multiverse
```

Two differences from the `-to-eng` maps:

- `no_org_counterpart` lists the scheme's verses that have no Hebrew verse (the Greek
  additions in Daniel and Esther, Psalm 151, eng NEH 7:68). Check it before taking a
  missing row as identity.
- Scope is the 39 books of the Hebrew Bible. Deuterocanonical books have no rows, and
  the New Testament is in `nt-variants.json`. Where a scheme names a Hebrew book
  differently (`lxx` DAG = Daniel, `lxx` EZR 11–23 = Nehemiah), every verse has a row.

They're built from the published maps: X → eng, then eng → org with org's map inverted.
Going through eng verse by verse would lose information where several verses meet in one
English verse (a two-verse Psalm title is one eng "title"), so verses are matched in
groups that share English verses, in order. `pipeline/core/generate_vrs_to_org.py`
documents the rule. Each map carries its `-to-eng` map's checks and known gaps (see
`doc/scheme-manifest.md`).

## Deuterocanon rows in `rso` (added 2026-10-06)

The `rso` map includes rows for 1 Esdras, Sirach, Tobit, Baruch and the
Letter of Jeremiah. Judith and Wisdom have none. They come from TVTMS's Greek sections
and are kept because five editions use those books. Nobody has checked them
against deuterocanon text yet, so treat them as unverified. Susanna and Bel
(Daniel 13–14) have no rows. See `doc/scheme-manifest.md` for the full list
of what was and wasn't verified.
