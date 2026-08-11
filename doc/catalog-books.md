# `books.json` (per-language)

`https://cdn.bibel.wiki/catalog/<iso[0]>/<iso>/books.json`

e.g. `https://cdn.bibel.wiki/catalog/a/aai/books.json`,
`https://cdn.bibel.wiki/catalog/e/eng/books.json`

Per-language **edition metadata** — vernacular book names, license/year
attribution, script direction, and font hints — merged across DBT, PKF,
and helloAO. A different axis from
[`catalog-text.md`](catalog-text.md)/[`catalog-audio.md`](catalog-audio.md)
(fileset *routing*) and [`catalog-overlap.md`](catalog-overlap.md)
(cross-source text *identity*): this file answers "what is this edition
actually called, in its own language, and what does its book list look
like" — nothing here is about which fileset to fetch or whether two
sources have the same translation.

Published **per language**, not as one combined file — this data is
heavier than the flat catalog files (PKF's per-chapter verse-count arrays
alone can run 20-70 integers per book), so bundling every language into
one file the way `catalog-index.json` does would make it far bigger than
any catalog file published so far, for data most clients only need one
language of at a time. Sharded by the language's first letter
(`<iso[0]>/<iso>/books.json`) so `/catalog/` itself doesn't end up with
~2,000 iso-named subdirectories.

## Discoverability

Not indexed anywhere else — `catalog-index.json` already tells you which
sources (`d`/`p`/`h`) have *some* content for a language; if a source is
listed there, its `books.json` entry exists here too (same convention
`/dbt/<iso>/media.json` already uses: fetch the per-language file
directly rather than checking a central flag first).

## Shape

```json
{"iso":"aai","entries":{
"d:AAIWBT":{
  "n":"Tur Gewasin O Baibasit Boubun",
  "license":{"mark":"© 2009 Wycliffe Bible Translators, Inc."},
  "year":2009,
  "dir":"ltr",
  "books":[
    {"code":"MAT","n":"Matthew","ns":"Matthew","t":"nt","c":28}
  ]
},
"p:C01":{
  "n":"Arifama-Miniafia",
  "license":{"license":"CC-BY-NC-ND-4.0","holder":"2009, Wycliffe Bible Translators, Inc., Orlando, FL 35862-8200 USA (","source":"https://scriptureearth.org/data/aai/sab/aai","noticeUrl":"aai/license-notice.html"},
  "year":2009,
  "dir":"ltr",
  "font":[{"name":"CharisSILCompact-R.DN016Jc-.ttf","url":"https://scriptureearth.org/data/aai/sab/aai/_app/immutable/assets/CharisSILCompact-R.DN016Jc-.ttf"}],
  "books":[
    {"code":"MAT","n":"Matthew","ns":"Mat","toc2":"Matthew","t":"nt","c":28,"v":[25,23,17,25,48,34,29,34,38,42,30,50,58,36,39,28,27,35,30,34,46,46,39,51,46,75,66,20]}
  ]
},
"h:aai_wbt":{
  "n":"Minaifia NT",
  "license":{"licenseUrl":"https://ebible.org/Scriptures/details.php?id=aai"},
  "books":[
    {"code":"MAT","n":"...","ns":"...","t":"nt","c":28,"verses":1071}
  ]
}
}}
```
(Every value shown is real, from the live `aai` and `eng` entries — not
constructed. `aai`'s three source rows above are its actual complete
source list; `eng` alone has 74.)

## Row format

`entries["<d:|p:|h:><version_id>"] = { n, license, year, dir, font, books }`

- **`<source>:<version_id>`** — same `d:`/`p:`/`h:` source-prefix
  convention as `catalog-index.json`/`catalog-overlap.json`. `d:` uses
  DBT's `abbr`; `p:` uses PKF's collection id (e.g. `C01`); `h:` uses
  helloAO's translation id.
- **`n`** — the edition's own title.
  - DBT: **`vname`** preferred over `name` — confirmed against real data
    that DBT's `name` field is consistently publisher/year attribution
    text (e.g. `"2009 Wycliffe Bible Translators, Inc."`), a near-
    duplicate of `mark`, not the version's actual title; `vname` (when
    present) is the real vernacular title. `name` is only used as a
    fallback when `vname` is genuinely absent from DBT's data.
  - PKF: the language's manifest name.
  - helloAO: the translation's English name.
- **`license`** — **source-shaped, never normalized across sources** — DBT's
  free-text `mark` and PKF's structured license block are different
  enough that forcing a common shape would mean guessing a structured
  code out of DBT's prose, which this project's "verified only, never
  inferred" principle doesn't allow (see `doc/catalog-overlap.md`).
  - DBT: `{"mark": "<raw text>"}`.
  - PKF: `{"license", "holder", "source", "noticeUrl"}` — PKF's own
    structured copyright block, field names kept close to source.
  - helloAO: `{"licenseUrl": "<url>"}`.
  - Omitted entirely when the source has nothing.
- **`year`** — bare int. DBT's `date` (string) and PKF's `copyright.year`
  (already int) both normalize cleanly. helloAO has no year field at all
  in its data — omitted, not guessed.
- **`dir`** — `"ltr"`/`"rtl"`, from whichever source has it (DBT
  `alphabet.direction`, PKF `app-config.json`'s `collection.textDirection`,
  helloAO `textDirection`).
- **`font`** — source-shaped:
  - DBT: `{"requiresFont": bool, "primaryFont": "<name>"}` — a hint, not a
    real file. `primaryFont` omitted when null.
  - PKF: array of `{"name", "url"}` — **real, downloadable font files**
    (confirmed real: PKF's `info.json` lists actual `.ttf` assets with
    working URLs, not just a boolean flag).
  - helloAO: omitted — no font data of any kind in helloAO's API.
- **`books[]`** — one entry per book DBT/PKF/helloAO's own data lists (not
  cross-validated against this repo's versification schemes):
  - **`code`** — USFM/Paratext book code.
  - **`n`**/**`ns`** — full/short localized book name.
    DBT: `name`/`name_short`. PKF: `h`/`toc3`. helloAO: `name`/`commonName`.
  - **`toc2`** — **PKF only**, its third, distinct title tier
    (`documents[].toc2`) — kept rather than dropped just because DBT and
    helloAO only have two tiers each; real extra richness one source has
    is never discarded for uniformity with the others.
  - **`title`** — **helloAO only**, same reasoning: its own third tier
    (`books[].title`), included only when it actually differs from `n`/`ns`.
  - **`t`** — `"nt"`/`"ot"`, derived from the book code against a fixed
    canonical list. **Omitted** for deuterocanon/peripheral books rather
    than guessed.
  - **`c`** — chapter count (bare int; all three sources have this).
  - **`v`** — **PKF only**, array of verse counts per chapter (`v[0]` =
    chapter 1's count, etc.) — PKF is the only source with real
    per-chapter granularity; not faked from a bare chapter count for the
    other two.
  - **`verses`** — **helloAO only**, a single aggregate verse count for
    the whole book (`totalNumberOfVerses`) — a third, different
    granularity from PKF's per-chapter array; kept as its own field
    rather than forced into `v`'s shape.

## Source data, and its real limits

Purely a local merge of already-fetched, cached data — no live query
happens in the generator itself
(`pipeline/core/generate_catalog_books.py`); two separate fetch scripts
populate the caches it reads:

- `pipeline/core/fetch_pkf_book_data.py` → `internal-data/api-cache/pkf-books/<iso>/`
- `pipeline/core/fetch_helloao_book_data.py` → `internal-data/api-cache/helloao-books/<id>.json`
- DBT's `bible_details/` cache (`internal-data/api-cache/bibles/bible_details/`)
  is shared with the rest of the pipeline — no separate fetch step needed.

Coverage in the current build: 2,288 languages with a DBT entry, 585 with
PKF, 1,003 with helloAO (2,513 `books.json` files total — a language with
entries from more than one source still gets exactly one file). Not every
DBT/PKF/helloAO language is guaranteed to appear — this reflects whatever
was actually fetched, not a promise of full coverage; re-run both fetch
scripts (they're resumable, skip already-cached files) to pick up new
languages as sources add them.
