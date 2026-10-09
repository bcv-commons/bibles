# openbible text (Biblica's Open Bible)

Biblica publishes its Open Bible editions only as whole-edition USFM/USX zips. We parse
those zips (with [`usfmtc`](https://pypi.org/project/usfmtc/)) and publish each edition
per chapter and per book:

| File | What it is |
|---|---|
| `cdn.bibel.wiki/openbible/<iso>/<edition>/_meta.json` | the edition: name, licenses, provider, books, formats |
| `cdn.bibel.wiki/openbible/<iso>/<edition>/<BOOK>/<chapter>.sofria.json` | one chapter, Sofria |
| `cdn.bibel.wiki/openbible/<iso>/<edition>/<BOOK>.usj.json` | one book, USJ 3.0 |

e.g. <https://cdn.bibel.wiki/openbible/yal/YALUNKA/JHN/21.sofria.json>

The per-chapter verse-json files (`<BOOK>/<chapter>.json`) were removed on 2026-10-09;
[`migrating-to-sofria.md`](migrating-to-sofria.md) shows how to get the same verse list
from the Sofria chapter. Rendering and text extraction: `tools/sofria-render/`, see
[`client-chapter-formats.md`](client-chapter-formats.md).

## Choosing an edition: `catalog/openbible-editions.json`

`cdn.bibel.wiki/catalog/openbible-editions.json` lists every Biblica project we can
name, keyed by Biblica's project id (the `o:` ids in `catalog/overlap.json`):

```json
{
  "formats": {
    "sofria": {"path": "<BOOK>/<chapter>.sofria.json", "granularity": "chapter"},
    "usj": {"path": "<BOOK>.usj.json", "granularity": "book"}
  },
  "entries": {
    "65174ecae3ab186d581e98ff": {
      "abbr": "OECV", "iso": "ekk",
      "published": true,
      "books": ["1CO", "1JN", "..."],
      "canon": ["nt"],
      "licenses": [{"type": "CC BY-SA", "url": "..."}],
      "path": "openbible/ekk/OECV/"
    },
    "<project id>": {"abbr": "...", "iso": "...", "published": false, "reason": "nd_license"}
  }
}
```

- `published`: the edition's Sofria and USJ are on the CDN. As of 2026-10-09: 274 of
  307 editions, in 213 languages.
- `books`: the book codes published (books with at least one chapter). Not every
  edition has a full NT, let alone a full Bible.
- `canon`: `nt` / `ot` for a complete testament, `ntp` / `otp` for part of one.
- `licenses`: Biblica's own per-version license list, as in `_meta.json`.
- `path`: the edition folder, relative to `https://cdn.bibel.wiki/`; combine with
  `formats` for file URLs.
- `reason`, when not published: `nd_license` (only no-derivatives licenses: we don't
  republish those), `no_source` (Biblica's text isn't cached here), `not_built`.

## What is covered

1. **Only projects with a yaapi.bible edition abbreviation.** Biblica's catalog has no
   human-readable edition id, so the `<edition>` path segment comes from yaapi.bible's
   `abbreviation`, matched on the USFM artifact id (never on a name). A raw Biblica
   project id is never used as a path. `catalog/index.json`'s
   `pending_openbible_coverage` counts the Biblica projects not mapped yet.
2. **Only editions with at least one non-ND license.** An edition with an ND tag next to
   a non-ND alternative (e.g. CC BY-SA and CC BY-NC-ND) is included; ND-only editions
   are listed with `published: false`, `reason: "nd_license"`.

`CC BY-NC` editions are included but carry a non-commercial restriction you must respect.

## `_meta.json`

```json
{
  "name": "<edition name>",
  "licenses": [{"type": "CC BY-SA", "url": "https://creativecommons.org/licenses/by-sa/4.0/"}],
  "provider": "<rights holder>",
  "source": "biblica",
  "openbible_link": "https://openbible-api-1.biblica.com/projects/<project_id>",
  "books": ["1TH", "1TI", "..."],
  "formats": {"sofria": {...}, "usj": {...}}
}
```

`licenses[]` is an array: some editions carry more than one license, and all are kept.

## Attribution

Credit Biblica (the edition's `provider`) as the source of the text. The conversion is
ours; the content and its rights are Biblica's.

## `<iso>`

From yaapi.bible's `language.iso639p3`: ISO 639-3, as everywhere in this repo. It can
differ from Biblica's own `languageCode` for the same project (e.g. `ort` vs `ory`).
