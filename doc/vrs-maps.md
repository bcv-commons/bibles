# `_vrs/map/<scheme>-to-eng.json` — cross-scheme verse crosswalks

`https://cdn.bibel.wiki/_vrs/map/org-to-eng.json`
`https://cdn.bibel.wiki/_vrs/map/rso-to-eng.json`
(also `lxx`/`vul`/`catm`/`orgw`)

Real, verse-precise crosswalks from each non-`eng` versification scheme to
`eng` (KJV), derived from TVTMS (STEPBible-Data, CC BY 4.0). Answers "given
a verse reference in scheme X, what's the corresponding reference in `eng`
numbering" — precisely, not by reconstructing it from `.vrs` chapter/verse
*counts* (see the note on that below).

Not documented anywhere until now — if you were looking at these files and
only found the `crosswalk` field (empty for org/rso), you found a smaller,
different thing than what you wanted. Read on.

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

Concrete, real example (confirmed 2026-09-04, prompted by a client
report): `rso PSA 114` is the first half of the Masoretic/`eng` Psalm 116
split (a well-known LXX/Masoretic irregular point). `map` has explicit
rows for `rso PSA 114:1`-`114:8 -> eng PSA 116:1`-`116:8`, then jumps
straight to `rso PSA 115:1 -> eng PSA 116:10`. **`rso PSA 114:9 -> eng PSA
116:9` has no row at all** — verse number 9 is identical on both sides,
so by the "diffs only" rule there's nothing to declare, even though the
book/chapter context (which `eng` chapter this verse belongs to) isn't
independently stated anywhere else.

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
