# usj-to-sofria

Converts one book-level USJ file into per-chapter Sofria JSON, using
proskomma-core's own import and `sofria()` path.

```
npm install
node convert.mjs <book.usj.json> <out-dir> [--book-level-too]
```

Writes `<out-dir>/<N>.json` for each chapter. With `--book-level-too` it also
writes `<out-dir>/_book.json`, the whole-book Sofria.

Other entry points in this folder:
- `convert_batch.mjs <usj-dir> <sofria-out-dir>` — the same conversion for every
  `*.json` under `<usj-dir>` in one Node process; each book's relative path
  (minus `.json`) becomes a directory of chapter files.
- `usx_to_sofria.mjs <book.usx> <out-dir>` — USX instead of USJ, for editions
  that publish USX but no Sofria. Also importable as `usxToSofria(usxText)`.
- `whole_book_fallback.mjs` — used by both converters when proskomma-core's
  per-chapter `sofria()` call throws: render the whole book once and cut the
  chapter out of it.

Known behaviour:
- Red-letter (`wj`) is kept as a Sofria `usfm:wj` wrapper, the same way `usfm:w`
  word wrappers are kept. proskomma-core also writes the stray text
  `| marker="wj"` into those wrappers; the converter removes that text after
  output.
- Before import, `prepare_usj.mjs` works around the importer's behaviour, without
  removing any text (each step is documented in the file):
  - each `\fig` is moved into a paragraph of its own, right after its host paragraph
    (one in the introduction goes to the end of the introduction); otherwise the text
    after a figure is nested inside it;
  - USJ `table:row` / `table:cell` become `row` / `cell`, the names the importer's
    handlers use; a table with no text is removed;
  - optional line breaks (`//`) are removed; a `\cp` paragraph that only repeats the
    chapter's `pubnumber` is removed;
  - a `|` in text is kept as text (the importer would turn it into `| default=""`);
  - a heading paragraph holding a verse number is split there, so the verse keeps
    its text;
  - Paratext `\restore` metadata becomes a `\rem` remark.
- Route parity: the verse text of every published book is the same from its USJ and
  from its Sofria chapters (`tools/verse-text/js/parity.mjs`; 2026-10-12: all 128,136
  openbible and 1,402 audiobiblia chapters identical).

Checked: BLL John (`export/audiobiblia-usj/spa/BLL/JHN.json`) produces 21
chapter files. Chapter 3 keeps 17 `usfm:wj` wrappers, has no stray text, and
decodes with `tools/dbt-sofria-decode-py` to 36 verses, all identical to the
published verse-json text.

## Sofria references

There is no standalone Sofria specification. The reference points are:

- **The JSON schema** bundled in `proskomma-core` (its `dist/` folder), which
  comes from `https://github.com/Proskomma/proskomma-json-tools`. It defines
  the node types (`mark`, `wrapper`, `graft`, and so on) and allows wrapper
  subtypes that start with `usfm:`, such as `usfm:w` and `usfm:wj`.
- **The renderer** `SofriaRenderFromJson.js` in the same repository, which turns
  Sofria back into USFM. Use it to check that a round trip keeps the markup.

Under this convention a USFM character marker is a wrapper with subtype
`usfm:<marker>`, and its attributes live in `atts`. Red letter is therefore
`usfm:wj`, the same as `usfm:w` for word-level Strong's tags.
