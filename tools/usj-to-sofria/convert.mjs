#!/usr/bin/env node
// Convert one book-level USJ file into per-chapter Sofria JSON files, using
// the real proskomma-core import+sofria() path (not a hand-rolled mapping —
// Sofria has no independent spec/library outside proskomma-core itself, so
// going through a real Proskomma import is the only faithful way to produce
// it). This is the shared core piece of the USJ(book)+Sofria(chapter)
// reduced publish scheme: every source that can produce book-level USJ
// (openbible via usfmtc, helloAO via helloao_to_usj.py, PKF's own USFM if
// ever needed) reuses this one converter rather than each re-deriving
// Sofria independently.
//
// Usage: node convert.mjs <usj-file> <out-dir> [--book-level-too] [--usfm <usfm-file>]
//   --usfm: the book's original USFM. proskomma-core can't import USJ tables, so a
//   book with a table is converted from this instead (tables kept). Without it, the
//   tables are stripped and the run says so (TABLE-STRIPPED).
//   Writes <out-dir>/<N>.json for each chapter number found in the USJ
//   (matching cdn.bibel.wiki/dbt/<iso>/timing/<BOOK>.json's own per-book-dir,
//   per-chapter-file convention). With --book-level-too also writes
//   <out-dir>/_book.json (the whole-book Sofria, doc.sofria() with no
//   chapter arg) — off by default since the reduced scheme's whole point is
//   chapter granularity; whole-book Sofria is bigger on the wire for
//   partial reads (see the size analysis already done this session).
import { Proskomma } from 'proskomma-core';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { sofriaForChapterViaWholeBook } from './whole_book_fallback.mjs';
import { stripTables } from './strip_tables.mjs';

class BiblesPk extends Proskomma {
  constructor() {
    super();
    this.selectors = [
      { name: 'lang', type: 'string', regex: '^[A-Za-z0-9-]{2,30}$' },
      { name: 'abbr', type: 'string', regex: '^[A-Za-z0-9 _.-]+$' },
    ];
    this.validateSelectors();
  }
}

function splitFigures(content) {
  // proskomma-core nests everything after an inline \fig inside the figure's graft.
  // Each figure goes in a paragraph of its own, split out of its host paragraph.
  // A figure inside the introduction is moved to the end of the introduction:
  // there, proskomma nests the following intro paragraphs into it even when the
  // figure has a paragraph of its own.
  const out = [];
  let introFigs = [];
  const isIntro = (n) => n && n.type === 'para' && /^i/.test(n.marker || '');
  const flushIntro = () => { out.push(...introFigs); introFigs = []; };
  for (const node of content) {
    if (!isIntro(node) && introFigs.length) flushIntro();
    if (node && node.type === 'para' && (node.content || []).some(c => c && c.type === 'figure')) {
      let cur = { ...node, content: [] };
      for (const c of node.content) {
        if (c && c.type === 'figure') {
          if (cur.content.length) out.push(cur);
          const own = { ...node, content: [c] };
          if (isIntro(node)) introFigs.push(own); else out.push(own);
          cur = { ...node, content: [] };
        } else {
          cur.content.push(c);
        }
      }
      if (cur.content.length) out.push(cur);
    } else {
      out.push(node);
    }
  }
  flushIntro();
  return out;
}

// proskomma-core writes stray attribute text such as '| marker="wj"' or '| marker="ft"'
// into node text. Remove it from the output; the wrapper itself is kept (red letter
// is preserved as a usfm:wj wrapper).
const STRAY_MARKER = /\| marker="[^"]*"/g;
function stripWjLeak(json) {
  const walk = (x) => {
    if (typeof x === 'string') return x.replace(STRAY_MARKER, '');
    if (Array.isArray(x)) return x.map(walk);
    if (x && typeof x === 'object') return Object.fromEntries(Object.entries(x).map(([k, v]) => [k, walk(v)]));
    return x;
  };
  return JSON.stringify(walk(JSON.parse(json)));
}

function collectChapterNumbers(usj) {
  const numbers = [];
  for (const node of usj.content || []) {
    if (node && node.type === 'chapter' && node.number != null) {
      numbers.push(String(node.number));
    }
  }
  return numbers;
}

function main() {
  const [, , usjPath, outDir, ...rest] = process.argv;
  if (!usjPath || !outDir) {
    console.error('usage: node convert.mjs <usj-file> <out-dir> [--book-level-too] [--usfm <usfm-file>]');
    process.exit(2);
  }
  const bookLevelToo = rest.includes('--book-level-too');
  const usfmPath = rest.includes('--usfm') ? rest[rest.indexOf('--usfm') + 1] : null;

  let usjText = readFileSync(usjPath, 'utf-8');
  let usj = JSON.parse(usjText);
  usj = { ...usj, content: splitFigures(usj.content || []) };
  usjText = JSON.stringify(usj);
  const bookNode = (usj.content || []).find(n => n && n.type === 'book');
  const bookCode = bookNode ? bookNode.code : 'XXX';

  let pk = new BiblesPk();
  let doc;
  try {
    doc = pk.importDocument({ lang: 'xx', abbr: bookCode }, 'usj', usjText);
  } catch (e) {
    if (!/table/i.test(e.message)) throw e;
    // proskomma-core@0.11.3 has no USJ "table" handler: the import fails the whole
    // book. Its USFM importer handles tables, so use the original USFM when given.
    pk = new BiblesPk();
    if (usfmPath) {
      doc = pk.importDocument({ lang: 'xx', abbr: bookCode }, 'usfm', readFileSync(usfmPath, 'utf-8'));
      console.log('TABLE-VIA-USFM');
    } else {
      // Last resort only: strip the tables and keep the rest of the book.
      const stripped = stripTables(usj);
      usj = stripped.usj;
      usjText = JSON.stringify(usj);
      doc = pk.importDocument({ lang: 'xx', abbr: bookCode }, 'usj', usjText);
      console.log(`TABLE-STRIPPED (no --usfm given: tables lost) tables=${stripped.tablesRemoved}`);
    }
  }

  mkdirSync(outDir, { recursive: true });

  const chapterNumbers = collectChapterNumbers(usj);
  let written = 0;
  let wholeBookJson = null; // lazily rendered only if a per-chapter call fails — see whole_book_fallback.mjs
  for (const chNum of chapterNumbers) {
    let sofriaJson;
    try {
      sofriaJson = doc.sofria(undefined, chNum);
    } catch (e) {
      if (!wholeBookJson) wholeBookJson = JSON.parse(doc.sofria());
      sofriaJson = sofriaForChapterViaWholeBook(wholeBookJson, chNum);
    }
    writeFileSync(`${outDir}/${chNum}.json`, stripWjLeak(sofriaJson));
    written++;
  }

  if (bookLevelToo) {
    const wholeBook = doc.sofria();
    writeFileSync(`${outDir}/_book.json`, wholeBook);
  }

  console.log(JSON.stringify({ bookCode, chapters: written, outDir }));
}

main();
