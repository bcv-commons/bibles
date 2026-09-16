# openbible per-chapter text

`https://cdn.bibel.wiki/openbible/<iso>/<edition>/<book>/<chapter>.json`

e.g. `https://cdn.bibel.wiki/openbible/yal/YALUNKA/JHN/21.json`

A lightweight, per-chapter-fetchable derived endpoint for Biblica's Open
Bible text (see [`sources.md`](sources.md)'s openbible section) —
requested by a client 2026-09-16 (real content in that source is only
available as whole-edition USFM/USX zips, a bigger lift than the
per-chapter access this repo's other three sources already give).

## Extracted locally from this repo's own cached zips, via `usfmtc`

Real per-verse text, extracted directly from this repo's own persistent
USFM zip cache (`internal-data/api-cache/openbible/text-zips/`,
~380MB) — `pipeline/core/usfm_to_verses.py`, backed by
[`usfmtc`](https://pypi.org/project/usfmtc/), a real, actively maintained
USFM parser (not a second hand-rolled parser here).

This was originally built as a caching layer in front of
[`yaapi.bible`](https://yaapi.bible/)'s own `/verses/` API instead — that
approach was replaced 2026-09-19 after `usfmtc` proved a 100% real
success rate parsing this repo's own zips (vs. thousands of failures
across 30+ distinct real marker types from this repo's own narrower,
vendored USFM tokenizer, `tools/pkf-encode-py`'s `usfm_lexer.py`, which
was tried first). Extracting locally removed a real operational problem
too — the yaapi-based fetch repeatedly failed to complete due to
rate-limited, real per-page pagination against a third-party API.

**yaapi.bible's `/versions/` catalog is still used, but only for the
edition id** — see `catalog/openbible-editions.json`'s own doc.
Biblica's own catalog has no human-readable edition id at all (confirmed
2026-09-16), so the `<edition>` path segment (e.g. `YALUNKA`) still comes
from yaapi.bible's own `abbreviation` field — that part of the
coordination with yaapi.bible's owner is unchanged. Only the *content*
no longer depends on their API.

## Scope: not all Biblica editions — two independent gates

1. **Must have a resolved yaapi.bible abbreviation** — only Biblica
   projects present in `catalog/openbible-editions.json` get a
   client-facing id at all (see that file's own doc for why a raw
   Biblica hex project id is deliberately never published). Check
   `catalog/index.json`'s `pending_openbible_coverage` field for how
   many more exist but aren't mapped yet.
2. **Must have at least one non-ND license** — checked against Biblica's
   own real per-version `licenses[]` array (not yaapi's single-string
   field), same lenient rule used elsewhere this session: an edition
   carrying an ND tag *alongside* a real non-ND alternative (e.g. dual
   CC BY-SA + CC BY-NC-ND) is still included — only ND-only editions are
   excluded (33 of 307 mapped editions, as of 2026-09-19).

Both gates are independent — an edition can fail either one. Check an
edition's own `_meta.json` `licenses` field before assuming coverage —
`CC BY-NC` editions are included but still carry a real non-commercial
restriction a client must respect.

## Shape

Per-chapter file:

```json
{
  "book": "1TH",
  "chapter": 1,
  "verses": [
    {"verse": "1", "text": "..."},
    {"verse": "2", "text": "..."}
  ]
}
```

`book` — standard USFM/Paratext 3-letter code. `chapter` — bare int.
`verses[]` — sequential, `verse` is a **string, not always a bare
integer** — real verse bridges (e.g. `"28-29"`, two verses combined
under one marker in the source itself) are preserved as-is, not split
or renumbered. `text` is the real verse text (plain, footnotes/
cross-references stripped, USFM markup removed).

Per-edition metadata (one per edition, sibling to its chapter files, not
repeated per chapter):

`https://cdn.bibel.wiki/openbible/<iso>/<edition>/_meta.json`

```json
{
  "name": "<edition name>",
  "licenses": [
    {"type": "CC BY-SA", "url": "https://creativecommons.org/licenses/by-sa/4.0/"}
  ],
  "provider": "<rights holder>",
  "source": "biblica",
  "openbible_link": "https://openbible-api-1.biblica.com/projects/<project_id>",
  "books": ["1TH", "1TI", "..."]
}
```

`licenses[]` — a real **array**, not a single value: some editions carry
more than one license tag at once (e.g. dual CC BY-SA + CC BY-NC-ND) and
both are kept, never collapsed to "the more permissive one." `books[]` —
the real book codes this edition actually has chapter files for (check
before assuming a book exists; not every edition covers the full Bible
or even the full NT). `openbible_link` — the real Biblica project URL
this content was extracted from (queryable directly against
`openbible-api-1.biblica.com/projects/{id}`).

## Attribution

Credit Biblica (the edition's own `provider` field) as the content
source when displaying this text — the extraction pipeline is this
repo's own, but the content and its rights remain Biblica's.

## `<iso>` note

Derived from `catalog/openbible-editions.json` (itself sourced from
yaapi.bible's own `language.iso639p3` field) — real ISO 639-3, same
convention every other file in this repo uses.
