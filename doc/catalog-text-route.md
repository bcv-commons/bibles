# `text-route.json`

`https://cdn.bibel.wiki/catalog/text-route.json`

For every edition and testament: the **one canonical text** to read for verse
text, and the route to read it through. Reading it through
[`tools/verse-text`](../tools/verse-text/) gives every client the same verse
text for the same edition. The tokens and text fingerprint are computed over
that text, so they match too.

Source ids are the ones [`catalog-overlap.json`](catalog-overlap.md) and
[`catalog-index.json`](catalog-index.md) use (`d:` DBT, `h:` helloAO, `p:` PKF,
`o:` openbible / audiobiblia, `e:` eBible, `c:` CrossWire, `g:` Door43).

## Shape

```json
{"schema_version":1,"base":"https://cdn.bibel.wiki/","routes":{"sofria":"…"},
 "entries":{
  "car:nt":{"d:CARBSS":{"route":"usx","id":"CARBSSN_ET-usx","why":"sofria_damaged"}},
  "ceb:nt":{"d:CEBCBV":{"route":"plain","id":"CEBCBV"},
            "d:CEBRPV":{"route":"sofria","id":"CEBRPVN_ET-json"},
            "o:OCCB-CEB":{"route":"sofria","path":"openbible/ceb/OCCB-CEB/"}},
  "eng:nt":{"e:engoebus":{"route":"usj","path":"ebible/eng/engoebus/"},
            "h:eng_kjv":{"route":"helloao"}}
 }}
```

`entries["<iso>:<canon>"]["<source id>"] = {route, id | path, why?}`

- **`canon`**: `nt` or `ot`. Partial (`ntp`/`otp`) DBT versions are filed
  under the plain testament here. Book coverage is in
  [`/dbt/<iso>/coverage.json`](dbt-coverage.md).
- **`id`**: a DBT fileset id (fetch through DBT's API), or a PKF file name
  (under `pkf/<iso>/`).
- **`path`**: an edition folder under `base`.

## Routes

The order is the order of preference. An edition gets the first route its
source supports:

| route | what | read with |
|---|---|---|
| `sofria` | DBT: the `text_json` fileset (Sofria, per chapter). Ours (openbible, audiobiblia, CrossWire, Door43): `<BOOK>/<ch>.sofria.json` under `path` (the same text is also there as `<BOOK>.usj.json`) | `extract_sofria` |
| `usj` | our USJ, where it's the only form we publish (eBible): `<BOOK>.usj.json` under `path` | `extract_usj` |
| `usx` | DBT's `text_usx` fileset (per book; fetch with chapter 1) | `usx_to_usj.py` (Python) / `usx_to_sofria.mjs` (JS), then the extractor |
| `helloao` | helloAO's chapter JSON | tools/verse-text's helloAO converter, then `extract_usj` |
| `plain` | DBT's `text_plain` fileset (verse JSON) | the plain reader, `extract_plain` |
| `pkf` | a PKF collection | not settled yet |

USX is a last resort. Where a source publishes Sofria, use that. There is no
conversion from Sofria to USJ, and none is needed.

## `why`

Present only where the route isn't the one the source's formats would give:

- **`sofria_damaged`**: DBT builds its Sofria with proskomma, which mangles a
  `|` in text and drops whole verses containing a literal `//`. For these
  editions that changed the tokens of real verses, so the USX is canonical.
  The editions and the evidence for each (verses affected, examples) are in
  [`data/text-route-overrides.toml`](../data/text-route-overrides.toml):
  CARBSS, RELBTL, BGTNEW, FFMWBT, MZWNVS (2026-10-17). Editions where the
  Sofria differs from the USX only by a lost space before punctuation, with
  identical tokens, stay on Sofria: COEWBT, LAMABT, MDAWBT.
- **`not_in_fileset_listing`**: DBT's own fileset listing
  ([`catalog-text.json`](catalog-text.md)) has no text for the version, but
  `dbt/_catalog.json` does, and the comparison read it as plain text.

## What's not here

- Editions with no route we can read: a DBT version with only a generic
  download format (`f` in `catalog-text.json`), and openbible editions we
  don't publish (licence). `catalog-overlap.json` rows marked `r: false` are
  unreachable anyway.
- Whether a given chapter actually exists. That's coverage
  (`/dbt/<iso>/coverage.json`, each edition's `_meta.json` `books`).

Built by `pipeline/comparison/generate_text_route.py` (`make text-route`), from
`catalog-text.json`, `dbt/_catalog.json`, helloAO's book completeness, our
staged `_meta.json` files, the PKF manifest and `catalog-overlap.json`.
