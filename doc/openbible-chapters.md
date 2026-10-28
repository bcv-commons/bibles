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

## Choosing an edition

For a language's openbible editions, read:

- [`catalog/<iso[0]>/<iso>/edition-struct.json`](catalog-edition-struct.md): every
  edition of the language, with its name, licence holder, script and Biblica project
  (`biblica_project`). An edition we don't publish has `published: false` and a `reason`:
  `nd_license` (only no-derivatives licenses: we don't republish those), `no_source`
  (Biblica's text isn't cached here) or `not_built`.
- [`catalog/text-route.json`](catalog-text-route.md): the folder of each published edition
  (`path`, relative to `https://cdn.bibel.wiki/`).
- The edition's `_meta.json` in that folder: its books, licence list and formats.

Until 2026-10-26 one file, `catalog/openbible-editions.json`, listed every Biblica project
we can name, with the same information. It is no longer generated; the copy still on the
CDN is frozen at 2026-10-09.

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
