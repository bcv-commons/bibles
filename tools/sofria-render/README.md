# sofria-render

Reference renderer for Sofria, Proskomma's chapter JSON. It turns a Sofria
chapter into HTML using the same DOM and class names as SIL's Scripture App
Builder PWA (`sillsdev/appbuilder-pwa`, `ScriptureViewSofria.svelte`), so SAB's
own stylesheets style it unchanged. It also extracts plain text as typed entries.

Plain JavaScript (ES modules), no framework. Runs in Node and in the browser.

## The rule: nothing is dropped

Every element type in the Sofria schema has a rendering. That means blocks
(`paragraph`, `graft`, `row`), inline content (text, `mark`, `wrapper`,
`graft`, `start_milestone`, `end_milestone`) and `meta_content` on any element.

When an option hides something (verse numbers, notes, images, videos,
remarks), it is still in the output, with the `hidden` attribute. Anything
the renderer doesn't recognise is rendered with its text, and listed in
`warnings`. Numbers carried in attributes are kept too: the canonical verse
and chapter numbers stay in `data-verse` / `data-v` / `data-c`, even when a
published number (`\vp`, `\cp`) or local numerals are shown instead.

The tests check this on every chapter they render. Every text string, and
every verse and chapter number, in the input must appear in the output.

## Use

```js
import { renderChapter } from './src/render.js';
import { extractEntries, verseList, verseMap } from './src/verses.js';

const { html, introduction, notes, warnings } = renderChapter(sofriaDoc, options);
const entries = extractEntries(sofriaDoc);   // typed text entries, see below
const list = verseList(entries);             // [{ verse: '1', text }, ...] in reading order
const verses = verseMap(entries);            // { '1': '...', '2': '...' }
```

Put the HTML inside `<div id="container"><div id="content">…</div></div>`.
That is the structure SAB's stylesheets expect.

### Sources

| Source | How to get Sofria |
|---|---|
| PKF (`cdn.bibel.wiki/pkf/`) | `loadPkf(bytes).sofria(book, chapter)`, see below |
| DBT `text_json` filesets (ids ending `-json`) | the API's `path` URL is a Sofria chapter: fetch and `JSON.parse` |
| Our own Sofria (USJ → Sofria) | a Sofria chapter file |
| helloAO | `tools/helloao-to-sofria` turns helloAO's JSON into Sofria |

```js
import { pkfLanguage, loadPkf, optionsFromAppConfig } from './src/sources/pkf.js';

const lang = await pkfLanguage('aai');          // collections, stylesheets, app-config
const bytes = new Uint8Array(await (await fetch(lang.collections[0].url)).arrayBuffer());
const pkf = loadPkf(bytes);                      // pkf.books, pkf.chapters(book)
const doc = pkf.sofria('MAT', 1);                // chapter 1 also carries the book title and introduction
const { options } = optionsFromAppConfig(lang.appConfig);
const { html } = renderChapter(doc, options);
// load lang.stylesheets (shared sheet, then delta.css) as <link rel="stylesheet">; see Styles
```

If proskomma-core's chapter query fails (it does on some real content, e.g. a
table that runs across a chapter break: 10 chapters in `nca`), `sofria()` gets
the whole book instead and cuts the chapter out of it (`sliceChapter`), and marks
the result `fallback: 'whole-book'`. Cutting was checked against proskomma's own
chapter output on 1,904 chapters: byte-identical. Proskomma still prints its
own error message when the chapter query fails, before the fallback runs.

`optionsFromAppConfig` maps the language's SAB settings to renderer options.
That covers chapter-number format, `hide-verse-number-1`, red letters,
glossary links, footnote and cross-reference caller rules, footnotes, images
and videos shown or not, verse layout, verse-range separator, numeral system
and text direction. Each language then renders the way its publisher set it
up.

## Options

| Option | Default | |
|---|---|---|
| `notes` | `'collected'` | `'collected'`: a caller link in the text, notes listed after the chapter. `'inline'`: SAB's markup, the note in a hidden div next to its caller |
| `chapterNumber` | `'drop-cap'` | `'drop-cap'`, `'top'` or `'none'` (still in the output, hidden) |
| `direction` | `'ltr'` | sets which side the drop-cap floats on |
| `numerals` | `null` | a 10-digit string (e.g. `'٠١٢٣٤٥٦٧٨٩'`) or a function |
| `showVerseNumbers`, `hideVerseNumberOne` | `true`, `false` | hidden numbers stay in the output |
| `wordsOfJesus` | `true` | `\wj` as `span.wj` (red letters); off: `span.wj-off` |
| `glossaryLinks` | `true` | `\w` as SAB's glossary link, matched on the `lemma` attribute when present |
| `introduction` | `'inline'` | `'separate'` returns it in `introduction` instead |
| `remarks` | `'hidden'` | `\rem` text, kept hidden |
| `callers` | SAB defaults | `{ footnote: {type, symbol, noCallerToAuto}, xref: {…} }`, SAB's `default` / `abc` / `custom-symbol` rules |
| `showNotes`, `showImages`, `showVideos` | `true` | off: still in the output, hidden |
| `verseLayout` | `'paragraphs'` | `'one-per-line'` wraps each verse in `div.verse-block` |
| `verseRangeSeparator` | `'-'` | how `1-3` is printed |
| `figureUrl(src)` | — | returns an image URL for a figure's `src`; without it, a placeholder with `data-src` |
| `video(id)` | — | returns `{ title, url, thumbnailUrl }` for a `\zvideo` id |
| `refLink(text)` | — | returns an href for `\xt` and `\r` references |
| `idPrefix` | `''` | keeps ids unique when several chapters share one page |

## What it renders

| Sofria | HTML |
|---|---|
| paragraph `usfm:X` | `div.X` (level 1 without the digit: `div.q`, `div.s`, `div.mt`); `\b` gets a real blank line |
| verses | phrase `div#{v}{a,b…}.txs.seltxt.scroll-item[data-verse][data-phrase]`, number as `span.v` + `span.vsp` |
| chapter number | `div.c-drop` (floats by direction) or `div.c`; the paragraph holding a drop-cap becomes `m`, original in `data-usfm` |
| `\vp` / `\cp` | the published number is shown; a lone `\vp` is the verse number |
| `\va` / `\ca` | `span.va` / `span.ca`, in parentheses |
| title graft | SAB's title block (`div.scroll-item[data-verse=title]`) |
| heading graft | `div.s > div#s1` (anchor ids per marker); `\r` can link via `refLink` |
| introduction graft | `div.introduction`, phrases `div#+N.txs` |
| footnote / cross-ref | `sup.footnote` caller (SAB caller rules), body collected or inline |
| character styles | `span.X`, nested (SAB keeps only one at a time) |
| `\w` | `span.glossary > a.glossary[match]`, attributes as `data-*` |
| `\jmp` | `a.web-link` / `a.email-link` / `a.tel-link`; only `http(s)`, `mailto`, `tel`, anything else stays text |
| `\xt` | `span.xt.reflink` |
| figure (wrapper or graft) | `div.image-block`, caption `div.caption > span.caption` |
| table rows and cells | `<table>`, `th`/`td.tcN`, colspan and alignment from the cell |
| milestones | lists (`zon`/`zoli`/`zuli`), `zvideo` (`div.video-block`), `zaudioc`, `zreflink` (`a.ref-link`), `zstyle`/`zcstyle`; others kept as an empty marker and reported |

## Plain text: `extractEntries`

The output is an ordered list. Headings stay headings and are never added to
verse text:

```
{ type: 'verse',   verse: '9', text, title?: true, display?, alt?, published? }
{ type: 'heading', marker: 'd' | 's' | 'mt' | …, text, verse, beforeVerse }
{ type: 'intro',   marker, text }
{ type: 'note',    kind: 'footnote' | 'xref', caller, verse, text }
{ type: 'other',   marker, text }
```

In a heading-type paragraph (`\d`, `\s`, `\ms`, `\mt`, `\r`, `\sp`, `\sr`,
`\mr`, `\cl`, `\qa`), text before a verse number is a heading. Text after it
is that verse, marked `title: true` (as in `\d \v 1 (Of David)`). `\b` is not
a heading: its text is verse text.

## Styles

Every source uses SAB's shared scripture stylesheet,
`https://cdn.bibel.wiki/pkf/_styles/sab-scripture.css`. A PKF language adds its
own `pkf/<iso>/styles/delta.css`, for fonts, base size, direction and the
Normal/Sepia/Dark colours. `pkfLanguage()` returns both, in load order, from the
language's `info.json` (`style_shared`, `style_delta`).

```html
<link rel="stylesheet" href="https://cdn.bibel.wiki/pkf/_styles/sab-scripture.css">
<link rel="stylesheet" href="https://cdn.bibel.wiki/pkf/<iso>/styles/delta.css">
<link rel="stylesheet" href="example/example.css">
<div id="container" data-iso="<iso>" data-color-theme="Normal"><div id="content">…</div></div>
```

`data-color-theme` has to be set: SAB's colour variables (verse numbers, links,
titles, notes) are defined inside its theme blocks. The example always uses
`Normal`, with a white background. `delta.css` also has SAB's `Sepia` and `Dark`
app themes, which a client can offer by changing `data-color-theme`.

`example/example.css` goes last. It complements the shared sheet. It sets the
white background, the Normal colours for sources with no `delta.css` (a delta
always overrides them), and rules for what render.js adds beyond SAB's markup:
collected notes, the introduction wrapper, kept-but-hidden items, and the list
and link classes SAB styles in its app framework. Both CDN files have a short
cache time (5 minutes) on purpose. Don't cache them longer.

## Example page

`example/index.html` loads a PKF language from the CDN (`?iso=aai&book=MAT&chapter=1`),
or a Sofria JSON from a local file or `?sofria=<url>`. Serve this folder over
HTTP (`python3 -m http.server`) and open `/example/`.

## Tests

```
npm install && npm test
```

The unit tests use small synthetic fixtures, one for each element type and
option. Checked separately with the same no-drop rule:
- all 128,136 chapters of our openbible Sofria
- six PKF collections in five languages (`aai`, `niy`×2, `hui`, `agd`, `nca`), 4,271 chapters, in both note modes; this includes the 10 `nca` chapters that need the whole-book fallback
- DBT `text_json` (Tibetan Psalms 23 and 119)
- helloAO `eng_kjv` through both routes of `tools/helloao-to-sofria`, 1,189 chapters each
