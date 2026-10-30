# `/dbt/<iso>/coverage.json`

`https://cdn.bibel.wiki/dbt/<iso>/coverage.json`

**Being retired (2026-10-26).** Use
[`books.json`](catalog-books.md#dbt-book-coverage-from-a-fileset) instead: it
has the same books and chapters (every one of this file's 332,012 book lists
is reproduced there), one entry per version instead of a copy per fileset,
11 MB less in all. This file stays published, unchanged in shape, until its
users have moved.

Real per-fileset book/chapter coverage — companion file to
`/dbt/<iso>/media.json`, for editions that don't cover the full canon
(e.g. `PORALM` — Portuguese, only 4 NT books + 1 Tanakh book). Don't assume
full-canon coverage from an `"nt"`/`"ot"` label and 404 on a book a partial
translation doesn't have; check this file first.

## Shape

```json
{
  "PORALMN1DA": {"MAT": [1, 2, ..., 28], "MRK": [1, ..., 16], "LUK": [...], "ACT": [...]},
  "PORALMO1DA": {"RUT": [1, 2, 3, 4]}
}
```

Despite the per-fileset keys, the coverage is per version: DBT reports it
per version, and it is copied to each of the version's filesets, filtered
by testament. A fileset can lack a chapter listed here.

Keyed by DBT fileset id: the ids in `media.json`'s `filesets` entries
(`t`/`a`) plus the variants `media.json` doesn't list (`-opus16`, `-usx`,
`-json`, ...). Each value is `{book_id: [chapter_numbers]}` — the
real chapters present, not assumed sequential-from-1 (though in practice
they usually are).

Source: DBT's own `GET bibles/{abbr}?key=...&v=4` — bible-level, not
per-fileset (an audio/text-fileset-suffix id like `ENGBERN1DA` 404s on that
endpoint; only the bible abbr works). Filtered per fileset to that
fileset's own testament, so an NT-only audio fileset doesn't inherit Tanakh
books from its bible's aggregate response. Refreshed the same way
`media.json` is — no separate polling needed on your end.
