# Chapter text formats: what's available and how to use it

Draft, 2026-10-06. This describes what is published today. Anything not yet
published is listed under **Planned** and is not available.

## What is published today

| Source | Format | Granularity | URL pattern |
|---|---|---|---|
| openbible (Biblica) | verse-json | chapter | `cdn.bibel.wiki/openbible/...` |
| audiobiblia (BLL) | verse-json | chapter | `cdn.bibel.wiki/audiobiblia/spa/BLL/<BOOK>/<chapter>.json` |
| openbible, audiobiblia | USJ | book | **not yet published** (the USJ trees exist locally) |
| DBT `-json` filesets | Sofria | chapter | from the DBT API, `type=text_json`: the row's `path` field links to the Sofria document. Coverage varies; see below |

**Verse-json** is one file per chapter: `{"book", "chapter", "verses": [{"verse", "text"}]}`.
It needs no conversion.

**USJ** is one file per book, in the USJ 3.0 format. Use it when you want book-level content. It is not yet published for openbible or audiobiblia; until it is, use the verse-json files.

**Sofria** is Proskomma's native format, one document per chapter from DBT. It keeps the
verse markers that decoders read.

## DBT Sofria: coverage

Checked 2026-10-06 across all 1,305 `-json` filesets, for John 3:

- **1,015 return a Sofria document** for John 3.
- **286 return 404** for John. Most have no John at all: 160 have Genesis (so they're likely Old Testament only), and 126 have neither Genesis nor John.
- **3 are blocked by key permissions**, and one more lets its plain text through but refuses the Sofria download.

So a 404 means the book is absent from that fileset, and a 403 means the key can't read it. Neither means the Sofria format is missing. Check the book first, and handle a 403 as a permission issue, not a format issue. The check covered one chapter of each fileset, not every chapter.

## Converting a book to Sofria locally

If you hold a book in USJ and want per-chapter Sofria, convert it yourself. (USJ is not yet on the CDN, so this applies to USJ you already have.) This is a
stopgap until sources publish Sofria directly.

```
cd tools/usj-to-sofria && npm install
node convert.mjs <book.usj.json> <out-dir>
```

This writes `<out-dir>/<N>.json` for each chapter. Red-letter (`wj`) is kept as a Sofria
`usfm:wj` wrapper, the same way word wrappers are kept. The converter removes a stray
attribute string that proskomma-core writes into those wrappers.

Example, verified against the published BLL John:

```
node convert.mjs export/audiobiblia-usj/spa/BLL/JHN.json out/JHN
```

Chapter 3 keeps its 17 red-letter wrappers, gives 36 verses, and all 36 match the published verse-json text exactly.

## Reading verses from Sofria

```python
import json
from decode import extract_verses_from_sofria   # tools/dbt-sofria-decode-py/decode.py

chapters = extract_verses_from_sofria(json.load(open("out/JHN/3.json")))
# {3: {"1": "...", "2": "...", ...}}
```

The decoder reads `verses_label` marks wherever they sit in the document. Verses are
joined across paragraph breaks with a single space.

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
