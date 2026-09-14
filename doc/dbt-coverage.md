# `/dbt/<iso>/coverage.json`

`https://cdn.bibel.wiki/dbt/<iso>/coverage.json`

Real per-fileset book/chapter coverage — companion file to
`/dbt/<iso>/media.json`, for editions that don't cover the full canon
(e.g. `PORALM` — Portuguese, only 4 NT books + 1 OT book). Don't assume
full-canon coverage from an `"nt"`/`"ot"` label and 404 on a book a partial
translation doesn't have; check this file first.

## Shape

```json
{
  "PORALMN1DA": {"MAT": [1, 2, ..., 28], "MRK": [1, ..., 16], "LUK": [...], "ACT": [...]},
  "PORALMO1DA": {"RUT": [1, 2, 3, 4]}
}
```

Keyed by the same fileset id that appears in `media.json`'s `filesets`
entries (`id`/`t`/`a`). Each value is `{book_id: [chapter_numbers]}` — the
real chapters present, not assumed sequential-from-1 (though in practice
they usually are).

Source: DBT's own `GET bibles/{abbr}?key=...&v=4` — bible-level, not
per-fileset (an audio/text-fileset-suffix id like `ENGBERN1DA` 404s on that
endpoint; only the bible abbr works). Filtered per fileset to that
fileset's own testament, so an NT-only audio fileset doesn't inherit OT
books from its bible's aggregate response. Refreshed the same way
`media.json` is — no separate polling needed on your end.
