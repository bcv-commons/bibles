# `catalog-index.json`

`https://cdn.bibel.wiki/catalog/index.json`

Thin existence/availability index across all seven sources (DBT, PKF,
helloAO and the four `bibles` republishes: `o`, `e`, `c`, `g`). Answers "what
exists, from whom, for this language, complete or partial" — nothing else.
No comparison data here; see [`catalog-overlap.json`](catalog-overlap.md)
for that.

## Shape

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "sources": [
    {"d": "https://cdn.bibel.wiki/dbt/_catalog.json"},
    {"p": "https://cdn.bibel.wiki/pkf/manifest.json"},
    {"h": "https://bible.helloao.org/api/available_translations.json"},
    {"o": "self-republished by bibles, wherever license permits and the original source isn't directly/bulk-usable — see each edition's own _meta.json"},
    {"e": "self-republished by bibles from eBible.org: editions helloAO doesn't carry, ... — see each edition's _meta.json"},
    {"c": "self-republished by bibles from CrossWire SWORD modules: ... — see each edition's _meta.json"},
    {"g": "self-republished by bibles from Door43 (git.door43.org) aligned Bibles at a pinned commit: ... — see each edition's _meta.json"}
  ],
  "pending_openbible_coverage": 246,
  "pending_ebible_coverage": 7,
  "entries": [
    ["aai", "nt", "d"],
    ["aai", "nt", "h"],
    ["aai", "nt", "p"],
    ["aau", "ntp", "d"],
    ["xyz", "nt", "h", 2],
    ["yal", "nt", "o"]
  ]
}
```

`schema_version` (added 2026-08-26) — an integer, bumped only on a breaking
change to `entries`'/row shape (never on data changes — new languages,
count changes, etc. never bump it). Check this before parsing if you want
to fail loudly on a future shape change instead of hitting a confusing
runtime error. Currently `1`; this file's row shape hasn't changed since
it was first published.

`pending_openbible_coverage` (added 2026-09-19) — a real, live count of
Biblica text projects that exist but aren't in `entries` at all yet,
purely because they don't have a resolved yaapi.bible abbreviation to
publish under (see the `o` row note below). This is a machine-detectable
signal, not just a documentation footnote — a client can watch this
number and know real content exists beyond what's currently listed,
without silently assuming completeness. Expected to shrink over time as
yaapi.bible's own catalog coverage grows (`0` once fully closed); never
expect it to explain a gap in any other source.

`pending_ebible_coverage` (added 2026-09-27) — the analogous signal for a
different gap: a real count of isos where DBT's own catalog points to real
text at eBible.org (`t:ebible:<id>`) that isn't independently fetchable
from DBT itself and isn't also a real helloAO translation (eBible content
isn't always mirrored there), and that no source row covers. Since 2026-10-15
the `e` source covers the eBible editions we republish; this count is what's
left (eBible text DBT points to that we don't republish, e.g. because of an ND
licence), so that absence reads as "known, counted" rather than silently
dropped. Found via a real
client cross-check (2026-09-27): of 376 isos a client reported as entirely
absent from `entries`, 369 were confirmed genuinely audio-only in DBT's
own catalog (a real absence, not a bug — no code-mapping mismatch either,
these are the correct iso codes), and only these 7 were this specific,
fixable gap.

## Row format

`[iso, canon, source, count?]`

- **`iso`** — ISO 639-3 language code.
- **`canon`** — one of `nt` / `ntp` / `ot` / `otp`. The `p` suffix means
  **Portions** (partial coverage), matching DBT's own convention exactly.
  A language with a complete Bible gets **two rows** — one `nt`, one
  `ot` — never a combined "full bible" flag. Testament coverage is always
  assessed independently.
- **`source`** — single letter: `d` = DBT, `p` = PKF, `h` = helloAO, `o` =
  self-republished (redefined 2026-10-02 — see [`sources.md`](sources.md)), `e` =
  self-republished from eBible.org (added 2026-10-15, see below), `c` = self-republished
  from CrossWire (added 2026-10-21, see below), `g` = self-republished from Door43
  (added 2026-10-22, see below).
  **`o`** means content `bibles` itself fetched, verified, and
  republishes, wherever the license permits AND the original source's own
  format isn't directly/bulk-usable — currently openbible/Biblica
  (added 2026-09-16; its catalog API is metadata-only, real text needs
  several more API hops) and audiobiblia.org (its own site is
  HTML-page/PDF-only, no bulk text endpoint at all). Real per-edition
  provenance (which original site, real license/copyright text) lives in
  each edition's own `_meta.json`, not in `sources`' one `"o"` entry — a
  single URL stopped being meaningful once more than one real origin
  shared the letter. **`o` openbible rows only count Biblica text
  projects with a real, resolved yaapi.bible abbreviation** (decided
  2026-09-19 — publishing a raw Biblica hex project id was judged a bad
  long-term precedent, since a client depending on it makes migrating
  away later costly; see [`openbible-chapters.md`](openbible-chapters.md)). A project with
  no abbreviation yet is temporarily excluded here entirely, not shown
  under a hex id — see `pending_openbible_coverage` above for how many.
  **`e`** (added 2026-10-15; this settles the question left open on 2026-10-02 of
  whether eBible shares `o`): eBible.org editions `bibles` republishes
  (`generate_ebible_chapters.py`): editions helloAO doesn't already carry, whose
  copyright page gives a public-domain or non-ND Creative Commons licence, and whose
  text isn't already reachable from another source (compared before publishing,
  never assumed). eBible's own format is clean and bulk-usable, unlike `o`'s "had to
  rescue it" sources, so it has its own letter.
  **`c`** (added 2026-10-21): CrossWire SWORD modules `bibles` republishes
  (`generate_crosswire_usj.py`), on the same three conditions as `e`: a public-domain or
  non-NC/ND Creative Commons licence (the module's own `DistributionLicense`), plain text,
  and text not already reachable from another source. The first is the Vamvas modern Greek
  Bible (`c:GreVamvas`).
  **`g`** (added 2026-10-22): Door43 aligned Bibles `bibles` republishes
  (`generate_door43_usj.py`), each at a pinned commit: the nine Gateway Language texts
  lexeme-aligner's Door43 word alignments refer to, CC BY-SA 4.0.
  **`d`**: a `d` row means DBT's catalog has
  **independently fetchable text of its own** for this `(iso, canon)` —
  not just a catalog entry. Some DBT rows are external-source *pointers*
  (their text tag references helloAO's or eBible's text rather than
  hosting DBT's own) and are deliberately excluded, even though DBT's
  catalog technically lists them. Fixed 2026-07-28 after a client hit a
  real cross-file contradiction: 22 languages showed "2 sources" here
  (`d` + `h`) while [`catalog-overlap.json`](catalog-overlap.md) correctly
  had nothing at all for them, because DBT's listing never contributed
  anything independently comparable — only the pointed-to source
  (helloAO/eBible) did. If `d` appears here, `compare_all.py` can
  genuinely fetch something from it; that's now a real guarantee, not
  just usually true. `o` rows are classified from Biblica's own real,
  whole-edition text zip contents (a real per-book listing, not a claimed
  scope) — same no-guessing discipline.
- **`count`** — how many distinct versions from that source exist for this
  `(iso, canon)` pair. **Omitted when exactly 1** (the overwhelming
  majority of rows) — treat a missing 4th element as `count == 1`.

## What it doesn't tell you

Whether multiple rows for the same `(iso, canon)` are actually the *same*
translation or genuinely different ones. That's exactly what
[`catalog-overlap.json`](catalog-overlap.md) is for — check there before
assuming two sources are redundant or that you're missing a real option.
