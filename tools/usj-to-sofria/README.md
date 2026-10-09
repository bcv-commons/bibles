# usj-to-sofria

Converts one book-level USJ file into per-chapter Sofria JSON, using
proskomma-core's own import and `sofria()` path.

```
npm install
node convert.mjs <book.usj.json> <out-dir>
```

Writes `<out-dir>/<N>.json` for each chapter, plus nothing else unless
`--book-level-too` is given.

Known behaviour:
- Red-letter (`wj`) is kept as a Sofria `usfm:wj` wrapper, the same way `usfm:w`
  word wrappers are kept. proskomma-core also writes the stray text
  `| marker="wj"` into those wrappers; the converter removes that text after
  output.
- Before import, `prepare_usj.mjs` works around four importer behaviours, without
  removing any text:
  - each `\fig` is moved into a paragraph of its own (one in the introduction goes to
    the end of the introduction); otherwise the text after a figure is nested inside it;
  - USJ `table:row` / `table:cell` nodes are renamed `row` / `cell`, the names the
    importer's handlers use; otherwise a book with a table fails to import at all;
  - optional line breaks (USFM `//`, USJ `optbreak`) are removed; the importer would
    write them into the text as a literal `//`;
  - a `\cp` paragraph that only repeats its chapter's `pubnumber` is removed; the
    importer would add it as loose text after the previous chapter's last verse.

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
