# Chapter text formats: what's available and how to use it

Draft, updated 2026-10-08. This describes what is published today. Anything not yet
published is listed under **Planned** and is not available.

## What is published today

| Source | Format | Granularity | URL pattern |
|---|---|---|---|
| openbible (Biblica) | Sofria | chapter | `cdn.bibel.wiki/openbible/<iso>/<abbr>/<BOOK>/<chapter>.sofria.json` |
| openbible (Biblica) | USJ | book | `cdn.bibel.wiki/openbible/<iso>/<abbr>/<BOOK>.usj.json` |
| audiobiblia (BLL) | Sofria | chapter | `cdn.bibel.wiki/audiobiblia/spa/BLL/<BOOK>/<chapter>.sofria.json` |
| audiobiblia (BLL) | USJ | book | `cdn.bibel.wiki/audiobiblia/spa/BLL/<BOOK>.usj.json` |
| openbible, audiobiblia | verse-json | chapter | **Removed**, replaced by Sofria. See [migrating-to-sofria.md](migrating-to-sofria.md) |
| DBT `-json` filesets | Sofria | chapter | from the DBT API, `type=text_json`: the row's `path` field links to the Sofria document. Coverage varies; see below |

**Sofria** is Proskomma's native format, one document per chapter. It keeps the full
structure: headings, notes, poetry, tables, figures, red letter. Render it, or read its
verse text, with `tools/sofria-render/` (below). The openbible and audiobiblia Sofria is
converted from the books' USJ with `tools/usj-to-sofria/`. Every published chapter has
been checked with the renderer: no text and no verse or chapter number is dropped.

**USJ** is one file per book, in the USJ 3.0 format, as the source gave it. Use it when
you want book-level content.

Each openbible and audiobiblia edition's `_meta.json` (`.../<iso>/<abbr>/_meta.json`) lists
its formats, with paths relative to the edition folder:

```json
"formats": {
  "sofria": {"path": "<BOOK>/<chapter>.sofria.json", "granularity": "chapter"},
  "usj": {"path": "<BOOK>.usj.json", "granularity": "book"},
  "verse-json": {"path": "<BOOK>/<chapter>.json", "granularity": "chapter", "deprecated": "..."}
}
```

**Verse-json** (one file per chapter, `{"book", "chapter", "verses": [{"verse", "text"}]}`)
was removed. `verseList(extractEntries(doc))` on the Sofria chapter gives the same
`[{verse, text}]` list; [migrating-to-sofria.md](migrating-to-sofria.md) shows the switch.

## DBT Sofria: coverage

Checked 2026-10-06 across all 1,305 `-json` filesets, for John 3:

- **1,015 return a Sofria document** for John 3.
- **286 return 404** for John. Most have no John at all: 160 have Genesis (so they're likely Old Testament only), and 126 have neither Genesis nor John.
- **3 are blocked by key permissions**, and one more lets its plain text through but refuses the Sofria download.

So a 404 means the book is absent from that fileset, and a 403 means the key can't read it. Neither means the Sofria format is missing. Check the book first, and handle a 403 as a permission issue, not a format issue. The check covered one chapter of each fileset, not every chapter.

## Converting a book to Sofria locally

The openbible and audiobiblia Sofria is already published. For other USJ you hold, convert
it yourself:

```
cd tools/usj-to-sofria && npm install
node convert.mjs <book.usj.json> <out-dir>
```

This writes `<out-dir>/<N>.json` for each chapter. Red-letter (`wj`) is kept as a Sofria
`usfm:wj` wrapper, the same way word wrappers are kept. The converter removes a stray
attribute string that proskomma-core writes into those wrappers. Before import it prepares
the USJ (`prepare_usj.mjs`): figures, tables, optional line breaks and duplicate `\cp`
numbers; see `tools/usj-to-sofria/README.md`.

Example, verified against the published BLL John:

```
node convert.mjs export/audiobiblia-usj/spa/BLL/JHN.json out/JHN
```

Chapter 3 keeps its 17 red-letter wrappers, gives 36 verses, and all 36 match the published verse-json text exactly.

## Rendering Sofria, and reading its text

The reference implementation is `tools/sofria-render/` (JavaScript, Node or browser). It
works the same for PKF, DBT `text_json` and our own Sofria:

```js
import { renderChapter } from './tools/sofria-render/src/render.js';
import { extractEntries, verseList, verseMap } from './tools/sofria-render/src/verses.js';

const { html, notes, warnings } = renderChapter(doc);  // HTML in SAB's DOM and class names
const entries = extractEntries(doc);                     // typed: verse, heading, intro, note
const list = verseList(entries);                         // [{ verse: "1", text }, ...] in order
const verses = verseMap(entries);                        // { "1": "...", "2": "...", ... }
```

`renderChapter` uses the class names SIL's Scripture App Builder uses, so SAB's own
stylesheets apply. For PKF languages, those stylesheets are on the CDN. Nothing in the
input is dropped: hidden things stay in the output with `hidden`, unknown elements are
rendered with their text and listed in `warnings`. See `tools/sofria-render/README.md`.

`extractEntries` keeps headings separate from verse text. A `\d` title between two
paragraphs is a heading, not part of the verse. A `\d \v 1 (Of David)` title is verse 1,
marked as a title. Text in a `\b` paragraph is verse text. Verses are joined across
paragraph breaks with a single space.

The older Python decoder (`tools/dbt-sofria-decode-py/decode.py`) adds `\d` heading text to
the verse that is open at that point. Use `extractEntries` for correct verse text.

## Checking the result

Before you trust a chapter, check its verse count against the versification map for the
edition's scheme. The scheme is in the edition's index entry (`cdn.bibel.wiki/dbt/_vrs/index.json`).

- If the edition is labelled, check the verse count against that scheme's shape file.
- If the edition is `undetermined`, the index doesn't know its scheme. Use the verse numbers
  the text itself gives, and say so in your output. Don't assume a scheme.

## Planned, not available

These are requests we intend to make to helloAO. None is published yet, so don't build on them:

- helloAO book-level content in USFM or USJ.
- helloAO chapter-level content in Sofria, alongside their current `.json` format.

When any of these is published, this section will move to the table above.
