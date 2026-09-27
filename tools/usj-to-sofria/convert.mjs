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
// Usage: node convert.mjs <usj-file> <out-dir> [--book-level-too]
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
    console.error('usage: node convert.mjs <usj-file> <out-dir> [--book-level-too]');
    process.exit(2);
  }
  const bookLevelToo = rest.includes('--book-level-too');

  let usjText = readFileSync(usjPath, 'utf-8');
  let usj = JSON.parse(usjText);
  const bookNode = (usj.content || []).find(n => n && n.type === 'book');
  const bookCode = bookNode ? bookNode.code : 'XXX';

  let pk = new BiblesPk();
  let doc;
  try {
    doc = pk.importDocument({ lang: 'xx', abbr: bookCode }, 'usj', usjText);
  } catch (e) {
    if (!/table/i.test(e.message)) throw e;
    // Real proskomma-core@0.11.3 has no USJ "table" handler — import
    // fails the WHOLE document, not just the table (see
    // strip_tables.mjs). Confirmed safe to strip: these tables carry no
    // verse content of their own.
    const stripped = stripTables(usj);
    usj = stripped.usj;
    usjText = JSON.stringify(usj);
    pk = new BiblesPk();
    doc = pk.importDocument({ lang: 'xx', abbr: bookCode }, 'usj', usjText);
    console.log(`TABLE-STRIPPED tables=${stripped.tablesRemoved}`);
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
    writeFileSync(`${outDir}/${chNum}.json`, sofriaJson);
    written++;
  }

  if (bookLevelToo) {
    const wholeBook = doc.sofria();
    writeFileSync(`${outDir}/_book.json`, wholeBook);
  }

  console.log(JSON.stringify({ bookCode, chapters: written, outDir }));
}

main();
