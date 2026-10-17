# verse-text

Client tools for getting the same verse text, the same tokens and the same text
fingerprint from a Bible edition, in Python and in JavaScript. Agreed with
lexeme-aligner (2026-10-12), whose compact alignments address words by their position
in a verse's tokens: both sides use one versioned release of this package, so a
fingerprint means the same text everywhere.

## Contents

| Part | Python | JS | Status |
|---|---|---|---|
| helloAO JSON → USJ | `python/helloao_to_usj.py` | `../helloao-to-sofria/helloao_to_usj.mjs` | done |
| USX → USJ / Sofria (last resort: only where the source publishes no Sofria) | `python/usx_to_usj.py` (usfmtc) | `../usj-to-sofria/usx_to_sofria.mjs` (proskomma-core, `\|` protected) | done: same verse text both ways, and as DBT's own Sofria |
| verse text from USJ and Sofria | `python/verse_text.py` | `js/extract_usj.js`, `js/extract_sofria.js` (rule: `js/rule.js`) | done |
| route parity (USJ vs Sofria, every published book) | — | `js/parity.mjs` | done: all openbible/audiobiblia chapters identical |
| language parity (JS vs Python) | `python/dump.py` | `js/dump.mjs` | done: identical for every openbible/audiobiblia chapter, both routes |
| tokenizer (lexeme-aligner's version 2, unchanged) | — | — | planned |
| text fingerprint (verse, chapter, book) | — | — | planned |
| conformance suite (all four routes give identical output) | — | — | planned |

## helloAO

We don't publish helloAO text. A client fetches helloAO's JSON itself
(`bible.helloao.org/api/<id>/<BOOK>/<chapter>.json`) and converts it with this package's
converter; we do the same, so both describe the same text.

```python
from helloao_to_usj import chapter_to_usj, merge_book_usj
usj = merge_book_usj("RUT", [chapter_json_1, chapter_json_2, ...])  # one book
```

```js
import { chapterToUsj, mergeBookUsj } from '../helloao-to-sofria/helloao_to_usj.mjs';
```

Both have no dependencies and give identical USJ (checked on BSB Ruth, Jonah,
Lamentations and KJV Lamentations, 2026-10-12). The JS converter moves into this
package's `js/` when the rest of it is built.

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

Two rules in the shared extraction (`js/rule.js`, `python/verse_text.py`) handle `|` in
source text: inside `\w`, text from a `|` on is an unparsed attribute and is dropped
(HLBMSS `<char style="w">word|lemma</char>`); `| default="X"`, proskomma's rendering of a
text `|` (DBT's Sofria), reads as `|X`. Every other `|` is text. Neither rule changes any
text we publish (checked on all openbible, audiobiblia and eBible files).
