# Moving from verse-json to Sofria (openbible, audiobiblia)

For clients that read `cdn.bibel.wiki/openbible/...` or `cdn.bibel.wiki/audiobiblia/...`
chapter files. The verse-json chapters (`<BOOK>/<chapter>.json`) have been removed.
Each chapter is now published as Sofria, and each book as USJ. This page shows how to
switch; it takes one function.

## What is published

Paths are relative to an edition folder, `cdn.bibel.wiki/openbible/<iso>/<edition>/`
(or `cdn.bibel.wiki/audiobiblia/spa/<edition>/`):

| File | What it is |
|---|---|
| `_meta.json` | Unchanged (name, licenses, provider, books), plus a new `formats` field |
| `<BOOK>/<chapter>.sofria.json` | One chapter, Sofria (Proskomma's chapter JSON) |
| `<BOOK>.usj.json` | One book, USJ 3.0 |
| ~~`<BOOK>/<chapter>.json`~~ | verse-json: removed |

`_meta.json` now lists the formats, so you don't need to hard-code the paths:

```json
"formats": {
  "sofria": {"path": "<BOOK>/<chapter>.sofria.json", "granularity": "chapter"},
  "usj": {"path": "<BOOK>.usj.json", "granularity": "book"}
}
```

Example: <https://cdn.bibel.wiki/openbible/eng/ASV/JHN/3.sofria.json>.

## Getting verse text: the drop-in replacement

Sofria keeps the full structure of the chapter (headings, notes, poetry, tables,
figures). To get plain verse text out of it, use `verseList()` from our reference code.
It returns `[{ verse, text }, ...]` in reading order: the same shape as the old
verse-json `verses` array.

The code is two plain JavaScript files with no dependencies, in
[`tools/sofria-render/src/`](https://github.com/bcv-commons/bibles/tree/main/tools/sofria-render/src):
`verses.js` for text, and `render.js` if you also want HTML. Copy them into your project
(they are ES modules and work in the browser and in Node), or import them from a
checkout of this repo.

```ts
import { extractEntries, verseList } from "./sofria/verses.js"

export async function fetchChapter(base: string, book: string, chapter: number) {
  // base: "https://cdn.bibel.wiki/openbible/<iso>/<edition>"
  const r = await fetch(`${base}/${book}/${chapter}.sofria.json`)
  if (!r.ok) return null
  return verseList(extractEntries(await r.json()))
  // -> [{ verse: "1", text: "..." }, { verse: "2-3", text: "..." }, ...]
}
```

For demo-bibel-wiki, `fetchOpenbibleChapter` in `src/lib/bw/openbible-text.ts` becomes:

```ts
import { extractEntries, verseList } from "./sofria/verses.js"

export function fetchOpenbibleChapter(iso: string, edition: string, book: string, chapter: number) {
  const key = `${iso}/${edition}/${book}/${chapter}`
  const cached = chapterCache.get(key)
  if (cached) return cached
  const p = fetch(pkfUrl(`/openbible/${iso}/${edition}/${book}/${chapter}.sofria.json`))
    .then((r) => (r.ok ? r.json() : null))
    .then((doc) => (doc ? verseList(extractEntries(doc)).map((v) => ({ num: v.verse, text: v.text })) : null))
    .catch(() => null)
  chapterCache.set(key, p)
  return p
}
```

`fetchOpenbibleMeta` needs no change.

### What is the same, and what is better

We compared `verseList` on every published chapter against the verse-json it replaces
(128,136 openbible and 1,402 audiobiblia chapters). Verse numbers and text are the same,
except where verse-json was wrong:

- verse-json glued headings, figure captions and some notes onto the verse text; Sofria
  keeps them separate;
- verse-json lost some verses (for example a numbered title such as Habakkuk 3:1, and
  verses inside tables);
- verse-json left out verses that have no text of their own, such as a verse given only
  as a note; `verseList` lists them with empty text.

Things to know:

- `verse` is a string, as it was in verse-json: `"1"`, a range such as `"2-3"` or
  `"17b-23"`, and in some editions the source's own form (a Persian range can contain a
  right-to-left mark: `"9‏-10"`). Parse ranges if you need numbers.
- A verse that the edition gives twice (two endings of Mark 16, for example) comes back
  once, with both texts joined. verse-json kept only one of them.
- Headings, notes and figure captions are not in `verseList`. They are in
  `extractEntries(doc)` as entries of type `heading`, `note` and `other`, if you want them.

## Rendering the whole chapter (optional)

`renderChapter(doc)` from `render.js` turns a Sofria chapter into HTML with the DOM and
class names of SIL's Scripture App Builder, so SAB's own stylesheet styles it:

```js
import { renderChapter } from "./sofria/render.js"
const { html, notes, warnings } = renderChapter(doc)
```

```html
<link rel="stylesheet" href="https://cdn.bibel.wiki/pkf/_styles/sab-scripture.css">
<div id="container" data-color-theme="Normal"><div id="content"><!-- html here --></div></div>
```

Nothing in the chapter is dropped: hidden things stay in the output with `hidden`. See
[`tools/sofria-render/README.md`](https://github.com/bcv-commons/bibles/blob/main/tools/sofria-render/README.md)
for the options (note style, chapter number, verse layout, numerals, and more).

To look at any chapter rendered, open the example page from a checkout
(`tools/sofria-render/example/`) with `?sofria=<url of a .sofria.json>`.

## USJ

`<BOOK>.usj.json` is the whole book in USJ 3.0, as the source gave it. Use it if you want
book-level content or your own conversion. To make per-chapter Sofria from other USJ you
hold, see [`tools/usj-to-sofria/`](https://github.com/bcv-commons/bibles/tree/main/tools/usj-to-sofria).

## More

- [`doc/client-chapter-formats.md`](client-chapter-formats.md): every chapter format we
  publish, including DBT and PKF Sofria.
