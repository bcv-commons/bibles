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
| verse text from USJ and Sofria | — | `js/extract_usj.js`, `js/extract_sofria.js` (rule: `js/rule.js`) | JS done, Python planned |
| route parity (USJ vs Sofria, every published book) | — | `js/parity.mjs` | done: all openbible/audiobiblia chapters identical |
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
