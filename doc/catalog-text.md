# `catalog-text.json`

`https://cdn.bibel.wiki/catalog/text.json`

DBT's own text fileset routing, compact and per-version — "given a DBT
`(iso, distinct_id, canon)`, which fileset id(s) actually carry its text,
and in what format(s)." Companion file: [`catalog-audio.md`](catalog-audio.md)
(same source, same shape, audio instead of text).

This is DBT-only, single-source — it does **not** tell you whether two
different sources have the same text (that's
[`catalog-overlap.json`](catalog-overlap.md)), and it does **not** confirm
the text actually fetches successfully today (that's
[`text-availability.json`](catalog-overlap.md), a separate, narrower
confirmation pass over a specific language subset).

Built entirely from DBT's own raw paginated catalog listing — no other
DBT input. In particular, this file **never** claims a DBT id has
matching text on another source (no eBible/helloAO naming-guess fallback)
— if DBT's own catalog doesn't independently carry text for a version,
this file simply has nothing for it. Guessing a naming-convention match to
another source would violate the same "verified only, never inferred"
principle `catalog-overlap.json` enforces everywhere else — check
`catalog-overlap.json` instead if you need a real, verified cross-source
answer.

## Shape

```json
{"entries":{
"aai:nt":{"AAIWBT":[{"id":"t:","fmt":["pl"]}]},
"aak:nt":{"AAKWBT":[{"id":"t:","fmt":["f","pl"]}]},
"spa:nt":{"SPABDA":[
{"id":"T:SPNBDA","fmt":["f"]},
{"id":"T:SPNBDAN_ET","fmt":["pl"]},
{"id":"T:SPNBDAN_ET-json","fmt":["j"]},
{"id":"T:SPNBDAN_ET-usx","fmt":["u"]}
]}
}}
```

## Row format

`entries["<iso>:<canon>"]["<distinct_id>"] = [variant, ...]`

- **`iso`** — ISO 639-3 code, same as `catalog-index.json`.
- **`canon`** — `nt`/`ot`, with a trailing `p` (`ntp`/`otp`) when the
  fileset's own `size` code doesn't certify whole-testament coverage —
  the book being present is DBT's optimistic claim, not confirmed. Same
  convention `catalog-index.json` already uses. **Unlike**
  `catalog-index.json`, this file always uses the plain `nt`/`ot` grouping
  for the base testament even when mixing certain/uncertain versions —
  the `p` suffix lives entirely on the canon key, not as a separate flag.
- **`distinct_id`** — DBT's own version abbreviation (the `abbr` field in
  its raw catalog).
- **`variant.id`** — source-fetchable, DBT-native fileset id, compactly
  encoded: `t:<suffix>` means "append `<suffix>` to `distinct_id` to
  reconstruct the real id" (the common case — most fileset ids share
  `distinct_id`'s prefix); `T:<literal>` means "this is the real id
  verbatim" — a real, confirmed-common case (a meaningful minority of
  filesets don't share the prefix), not a rare exception a client can
  skip handling. Verified by direct round-trip check against the full
  real catalog on every generation run: 0 failures across every id in
  this file.
- **`variant.fmt`** — always a list, even for a single format:
  `pl`=plain verse text (the inline, directly-fetchable shape most
  clients want), `u`=USX, `j`=JSON, `f`=a generic downloadable format.
  Always a list because DBT sometimes lists the exact same fileset id
  under two different format tags at once (confirmed real — `AAKWBT`
  above is a genuine case, not a contrived example) — if that weren't
  merged into one variant, `id` would silently stop being a unique key
  within the list for exactly those cases. It's never *not* a list, so a
  client never needs to special-case the single-format case separately.

## Why this replaces the old combined DBT catalog concept

An earlier design (MONO's own, never published by this repo) combined
audio and text into one row with a shared `a:`/`A:`/`t:`/`T:` encoding and
resolved each down to a single "best" fileset. This repo publishes two
separate, single-purpose files instead (matching the project's existing
pattern — `catalog-index.json` and `catalog-overlap.json` are each
single-concern too), and lists every real variant rather than
pre-resolving one "best" answer — a client choosing a specific text
format (plain text vs. structured USX/JSON) can see all its real options
here instead of only whichever one got picked for them.
