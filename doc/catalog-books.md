# `books.json` (per-language)

`https://cdn.bibel.wiki/catalog/<iso[0]>/<iso>/books.json`

e.g. `https://cdn.bibel.wiki/catalog/a/aai/books.json`,
`https://cdn.bibel.wiki/catalog/e/eng/books.json`

Per-language **edition metadata** — vernacular book names, license/year
attribution, script direction, and font hints — merged across DBT, PKF,
helloAO, and openbible (Biblica, added 2026-09-16). A different axis from
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
sources (`d`/`p`/`h`/`o`) have *some* content for a language; if a source is
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

`entries["<d:|p:|h:|o:><version_id>"] = { n, license, year, dir, font, books }`

- **`<source>:<version_id>`** — same `d:`/`p:`/`h:`/`o:` source-prefix
  convention as `catalog-index.json`/`catalog-overlap.json`. `d:` uses
  DBT's `abbr`; `p:` uses PKF's collection id (e.g. `C01`); `h:` uses
  helloAO's translation id; `o:` uses Biblica's real project id (queryable
  directly against `openbible-api-1.biblica.com/projects/{id}`).
- **`n`** — the edition's own title.
  - DBT: **`vname`** preferred over `name` — confirmed against real data
    that DBT's `name` field is consistently publisher/year attribution
    text (e.g. `"2009 Wycliffe Bible Translators, Inc."`), a near-
    duplicate of `mark`, not the version's actual title; `vname` (when
    present) is the real vernacular title. `name` is only used as a
    fallback when `vname` is genuinely absent from DBT's data.
  - PKF: the language's manifest name.
  - helloAO: the translation's English name.
  - openbible: the project's `titleEnglish` (falls back to `title`) —
    note this is the *edition's* title, in English; per-book titles
    (below) are the real vernacular ones.
- **`license`** — **source-shaped, never normalized across sources** — DBT's
  free-text `mark` and PKF's structured license block are different
  enough that forcing a common shape would mean guessing a structured
  code out of DBT's prose, which this project's "verified only, never
  inferred" principle doesn't allow (see `doc/catalog-overlap.md`).
  - DBT: `{"mark": "<raw text>"}`.
  - PKF: `{"license", "holder", "source", "noticeUrl"}` — PKF's own
    structured copyright block, field names kept close to source.
  - helloAO: `{"licenseUrl": "<url>"}`.
  - openbible: `{"licenses": [{"type", "url"}, ...]}` — a real array, not
    a single value: some editions carry more than one license tag at once
    (e.g. dual CC BY-SA + CC BY-NC-ND) and both are kept, never collapsed
    to "the more permissive one" or similar.
  - Omitted entirely when the source has nothing.
- **`year`** — bare int. DBT's `date` (string) and PKF's `copyright.year`
  (already int) both normalize cleanly. openbible uses the project's
  `originalArchiveDate` (year only). helloAO has no year field at all in
  its data — omitted, not guessed.
- **`dir`** — `"ltr"`/`"rtl"`, from whichever source has it (DBT
  `alphabet.direction`, PKF `app-config.json`'s `collection.textDirection`,
  helloAO `textDirection`, openbible `scriptDirection` lowercased).
- **`font`** — source-shaped:
  - DBT: `{"requiresFont": bool, "primaryFont": "<name>"}` — a hint, not a
    real file. `primaryFont` omitted when null.
  - PKF: array of `{"name", "url"}` — **real, downloadable font files**
    (confirmed real: PKF's `info.json` lists actual `.ttf` assets with
    working URLs, not just a boolean flag).
  - helloAO, openbible: omitted — no font data fetched for either.
- **`books[]`** — one entry per book DBT/PKF/helloAO/openbible's own data
  lists (not cross-validated against this repo's versification schemes):
  - **`code`** — USFM/Paratext book code.
  - **`n`**/**`ns`** — full/short localized book name.
    DBT: `name`/`name_short`. PKF: `h`/`toc3`. helloAO: `name`/`commonName`.
    openbible: real, per-book USFM header markers read directly out of
    the (already locally cached) text zip — `\toc1` (falls back to
    `\mt1`, then `\h`) for `n`, `\h` (falls back to `\toc3`) for `ns`. Not
    derived from anything this repo fetched separately — the same zip
    already cached for book-coverage classification (see
    [`sources.md`](sources.md)) is read a second time, locally, for this.
  - **`toc2`** — PKF's third, distinct title tier (`documents[].toc2`),
    and now also openbible's own `\toc2` USFM marker when it differs from
    `n`/`ns` — kept rather than dropped just because DBT and helloAO only
    have two tiers; real extra richness one source has is never discarded
    for uniformity with the others.
  - **`title`** — **helloAO only**, same reasoning: its own third tier
    (`books[].title`), included only when it actually differs from `n`/`ns`.
  - **`t`** — `"nt"`/`"ot"`, derived from the book code against a fixed
    canonical list. **Omitted** for deuterocanon/peripheral books rather
    than guessed.
  - **`c`** — chapter count (bare int; DBT/PKF/helloAO have this;
    **openbible does not** — book-level coverage is confirmed real via
    `text-book-coverage.json`, but no chapter-count field is populated,
    since nothing here parses that deep into the USFM).
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
- openbible: `pipeline/core/fetch_openbible_cache.py` (projects + per-project
  detail) and `pipeline/core/fetch_openbible_book_coverage.py` (real book
  coverage + the persistent zip cache this generator reads a second time
  for per-book titles) — both already run for `catalog-index.json`'s `o`
  rows, no separate fetch needed here either.

Coverage reflects whatever was actually fetched into those caches, not a
promise of full coverage — not every DBT/PKF/helloAO language is
guaranteed to have a `books.json` yet (the two fetch scripts are
resumable and get re-run periodically to pick up new languages as sources
add them). Rather than a snapshot count here (this file gets regenerated
independently of this doc and would go stale the next time it does),
derive current coverage from [`catalog-index.json`](catalog-index.md)
instead — it's published alongside `books.json` from the same pipeline
run and already lists every `(iso, canon, source)` combination, so
counting distinct isos per source letter (`d`/`p`/`h`/`o`) there gives you a
live answer instead of a fixed-in-time one.
