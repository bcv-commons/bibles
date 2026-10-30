# verse-text

Client tools for getting the same verse text, the same tokens and the same text
fingerprint from a Bible edition, in Python and in JavaScript. Agreed with
lexeme-aligner (2026-10-12), whose compact alignments address words by their position
in a verse's tokens: both sides use one versioned release of this package, so a
fingerprint means the same text everywhere.

**Version 2.0.0** (`VERSION`; changes in `CHANGELOG.md`). Tokenizer v3, text fingerprint
v1, content fingerprint v1, written tokens v1. CC0 1.0 (the tokenizer and text fingerprint are
lexeme-aligner's, handed over 2026-10-17 and copied verbatim).

Which text to read for an edition, and through which route, is in
[`catalog/text-route.json`](../../doc/catalog-text-route.md).

## Contents

| Part | Python | JS |
|---|---|---|
| helloAO JSON → USJ | `python/helloao_to_usj.py` | `js/helloao_to_usj.mjs` |
| USX → USJ / Sofria (last resort: only where the source has no usable Sofria) | `python/usx_to_usj.py` (usfmtc) | `../usj-to-sofria/usx_to_sofria.mjs` (proskomma-core, `\|` protected) |
| verse text from USJ and Sofria | `python/verse_text.py` | `js/extract_usj.js`, `js/extract_sofria.js` (rule: `js/rule.js`) |
| verse text from plain verse JSON (DBT `text_plain`) | `python/plain_text.py` | `js/extract_plain.js` |
| tokenizer v3 (and its mark stripping) and text fingerprint v1 | `python/bcv_tokenize.py` (`strip_marks`) | `js/tokenize.js` (`stripMarks`), `js/text_fingerprint.mjs` |
| written tokens v1: the tokens with their marks | `python/bcv_written.py` | `js/tokenize_written.js` |
| content fingerprint v1 (diagnosis) | `python/content_fingerprint.py` | `js/content_fingerprint.mjs` |
| conformance suite | `python/conformance.py` | `js/conformance.mjs` |
| route parity (USJ vs Sofria, every published book) | — | `js/parity.mjs` |
| language parity (JS vs Python, every published chapter) | `python/dump.py` | `js/dump.mjs` |

No dependencies, except usfmtc (Python, USX only) and proskomma-core (JS, USX only). The
fingerprints use `hashlib` (Python) and Web Crypto (browsers, Node >= 19).

## helloAO

We don't publish helloAO text. A client fetches helloAO's JSON itself
(`bible.helloao.org/api/<id>/<BOOK>/<chapter>.json`) and converts it with this package's
converter; we do the same, so both describe the same text.

```python
from helloao_to_usj import chapter_to_usj, merge_book_usj
usj = merge_book_usj("RUT", [chapter_json_1, chapter_json_2, ...])  # one book
```

```js
import { chapterToUsj, mergeBookUsj } from './js/helloao_to_usj.mjs';
```

Both have no dependencies and give identical USJ (checked on BSB Ruth, Jonah,
Lamentations and KJV Lamentations, 2026-10-12; since 1.0.0, on all 169 conformance
chapters). The JS converter used to live in `../helloao-to-sofria/`; that path still
re-exports it.

## Verse text

```python
from verse_text import extract_usj, extract_sofria
extract_usj(book_usj)        # {"1": [{"verse": "1", "text": "..."}, ...], ...}
extract_sofria(chapter_doc)  # [{"verse": "1", "text": "..."}, ...]
```

```js
import { extractUsj } from './js/extract_usj.js';
import { extractSofria } from './js/extract_sofria.js';
```

The rule is written out in `js/rule.js` and at the top of `python/verse_text.py`. Both
languages give the same text for every chapter of every edition we publish, from both
formats (2026-10-12: 128,136 openbible and 1,402 audiobiblia chapters):

```
node js/dump.mjs <usj-root> <sofria-root> > js.tsv
python python/dump.py <usj-root> <sofria-root> > py.tsv
diff <(sort js.tsv) <(sort py.tsv)
```

## USX: a last resort

Use the source's own Sofria where it publishes one (DBT: the `text_json` filesets, `-json`
ids). Only where a source has USX and no Sofria (158 DBT editions on 2026-10-17), convert:

```python
from usx_to_usj import usx_to_usj          # usfmtc
chapters = extract_usj(usx_to_usj(usx_text))
```

```js
import { usxToSofria } from '../usj-to-sofria/usx_to_sofria.mjs';   // proskomma-core
const verses = extractSofria(JSON.parse(usxToSofria(usxText)['3']));
```

proskomma-core's USX importer reads a `|` in text as the start of attributes (and then
truncates long values); `usx_to_sofria.mjs` protects every `|` in text nodes before import,
as our USJ route does. Checked 2026-10-17 on 8 DBT editions (LUGLUG, KNKBSL, RAWBIB, BIVWBT,
and the `|` editions CARBSS, HLBMSS, YBBCAB, SXNLAI): both routes give identical verse text,
and the same as DBT's own Sofria wherever it exists, except where DBT's Sofria itself lost a
space before a `|` (CARBSS REV 15:3; not recoverable from the Sofria).

### `|` in source text

`|` reaches verse text in several ways; the shared rule (`js/rule.js`,
`python/verse_text.py`) handles them all:

- Inside `\w`, text from a `|` on is an unparsed attribute and is dropped (HLBMSS
  `<char style="w">word|lemma</char>`).
- `| default="X"` is proskomma's rendering of a text `|` (DBT's Sofria) and reads as `|X`,
  also when proskomma truncated the value and lost the closing quote.
- Legacy formatting codes are dropped: `|i` and `|sc` (opening, before a space, a capital
  or an opening quote or punctuation mark) and `|r` and `|d` (closing, before a space,
  punctuation or the end). Anything else is text: a Sanskrit danda before a lowercase
  letter (`cAvarA|isrAyel`), or SXNLAI's mid-word `|u`.

None of these rules changes any text we publish (checked on every openbible, audiobiblia
and eBible file, 2026-10-17).

## Plain text: a last resort

Only where an edition has no structured text at all (DBT editions with only `text_plain`):

```python
from plain_text import extract_plain
extract_plain(dbt_chapter["data"])   # [{"verse": "1", "text": "..."}, ...]
```

```js
import { extractPlain } from './js/extract_plain.js';
```

A verse is keyed by its first number (a bridged 4-5 is verse 4), `~` (no-break space) and
a literal `//` (optional line break) read as spaces, then the shared `clean()`. Python and
JS agree on all 558 verses of 15 sampled DBT plain chapters. Plain text can't be read
exactly like structured text: DBT's plain export keeps `\rq` references and `\w`
lemmas as running text (`conformance/dbt-cases.json`: BVZYSS, BIVWBT, HLBMSS). That's why
it comes last.

## Tokens and fingerprints

```python
from bcv_tokenize import tokenize, fingerprints, file_hash
tokens = tokenize(text)
book_fp, chapter_fps = fingerprints({(chapter, verse): text, ...})   # SHA-256 hex
file_hash(book_fp)                                                   # 8 hex, <BOOK>_<hash>.json
```

```js
import { tokenize } from './js/tokenize.js';
import { fingerprints, fileHash } from './js/text_fingerprint.mjs';
const { book, chapters } = await fingerprints(new Map([['3:16', text], ...]));
```

The tokenizer first strips combining marks (NFC, then every mark with a combining class,
except the Myanmar virama and asat, and variation selectors). The same step is exported on
its own, in both languages:

```python
from bcv_tokenize import strip_marks
strip_marks("سَلَامٌ")      # 'سلام'
```

```js
import { stripMarks } from './js/tokenize.js';
stripMarks("سَلَامٌ");      // 'سلام'
```

Text fingerprint v1:

1. Verses in the edition's own numbering. A bridged verse uses its first number, and a
   verse with no tokens is left out.
2. Per verse, the line `"{verse}:{tokens joined by one space}"`.
3. Chapter fingerprint: SHA-256 (hex) of that chapter's lines joined by `\n`.
4. Book fingerprint: SHA-256 of one line per chapter, `"{chapter}:{chapter fingerprint}"`,
   joined by `\n`. Its first 8 hex digits go in file names.

The **content fingerprint** (`content_fingerprint.py` / `.mjs`) has the same shape, over
each verse's letters only: NFC, lowercase (then ς → σ), apostrophe-like characters
mapped to one (ʼ), letters and marks (Unicode L, M) kept. It's for diagnosis: when two
texts' text fingerprints differ but their content fingerprints match, they differ only in
spacing, word joins, punctuation, case or apostrophe form. Example: FFMWBT MRK 7, where
DBT's Sofria joins "yo Korbaan" into one word. It's lowercase and not Unicode case
folding, because JavaScript has no case folding and both languages must agree.

Tokenizer v3 (2.0.0) differs from v2 only in Myanmar script: logical-order Burmese keeps
its syllables whole (သော, ကောင်း), and in S'gaw Karen the asat is a tone mark. No text
without Myanmar script tokenizes differently (bcv-commons/bibles#1).

## Written tokens

The tokenizer drops combining marks, so that Arabic harakat and Hebrew points don't split
words. Where a letter has no precomposed form, the mark is gone: tone on ø, æ, ɨ, the
rising tone U+1DC4, Yoruba's tone under a dot below, the virama in Devanagari, Tamil and
Malayalam. `tokenize_written(text)` gives the same tokens at the same positions, each as
written (NFC), its marks kept: `strip_marks(written[i]) == tokenize(text)[i]`. Positions,
fingerprints and published alignments are unchanged; a client that needs the marks (a
reader, search, a segmenter) reads the written form at the same position.

```python
from bcv_written import tokenize_written
tokenize_written("Mø̀ndæ qá")      # ['Mø̀ndæ', 'qá']; tokenize() gives ['Møndæ', 'qá']
```

```js
import { tokenizeWritten } from './js/tokenize_written.js';
```

Contributed by bcv-commons/make-tanakh (then named bsb-add-books). On 2026-10-28 the invariant held for every verse
we publish (9,806 books, 4,051,985 verses; 10.9% of tokens get a mark back), and Python and
JS agree on all 47,655 Myanmar-script verses. Tests: `python/test_written.py`,
`js/test_written.mjs` (both on `conformance/written.expected.json`).

## Conformance

```
cd python && python conformance.py [--dbt]
cd js && node conformance.mjs
```

- `conformance/rules.json`: the extraction rules, the plain reader and the content
  fingerprint on short synthetic inputs (30 cases).
- `conformance/helloao/`: 169 helloAO chapters from lexeme-aligner's handover (23
  editions, about 20 scripts). The whole chain runs from the raw helloAO JSON: converter,
  extraction, tokens, lines, chapter text fingerprint, content fingerprint
  (`content.expected.json`). The input texts keep their editions' licences (public domain
  or CC BY-SA 4.0, in each expected file's `source.licence`).
- `conformance/dbt-cases.json`: 11 DBT chapters, referenced by fileset id with only their
  fingerprints per route, since DBT text can't be republished. `--dbt` fetches them live
  (needs a DBT API key and this repo's `pipeline/core`). Covers DBT's damaged Sofria
  (CARBSS, RELBTL, BGTNEW, FFMWBT, MZWNVS), a harmless difference (COEWBT), and plain
  versus structured (BVZYSS, BIVWBT, HLBMSS, YBBCAB, KIAWBT).

Language parity on everything we publish, with the fingerprints:

```
node js/dump.mjs <usj-root> <sofria-root> --fp > js.tsv
python python/dump.py <usj-root> <sofria-root> --fp > py.tsv
diff <(sort js.tsv) <(sort py.tsv)
```

On 2026-10-17 (1.0.0): verse text, text fingerprint and content fingerprint identical in
both languages for every chapter we publish: openbible 128,136 and audiobiblia 1,402
chapters (USJ and Sofria each), eBible 8,774 chapters (USJ).
