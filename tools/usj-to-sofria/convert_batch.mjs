#!/usr/bin/env node
// Batch sibling of convert.mjs — one Node process handles many book-level
// USJ files instead of spawning a fresh process per book (process startup
// dominates at corpus scale: thousands of books across hundreds of
// editions). Walks <usj-dir> recursively for *.json files; for each,
// mirrors its relative path (minus .json) as a directory under
// <sofria-out-dir> and writes one Sofria file per chapter into it.
//
// Usage: node convert_batch.mjs <usj-dir> <sofria-out-dir> [--usfm-dir <dir>]
//
// --usfm-dir: the books' original USFM, at the same relative paths as the USJ
// (<rel>.usfm). proskomma-core's USJ importer can't handle tables at all, but its
// USFM importer can, so a book with a table is converted from its USFM. Without it,
// such a book's tables are stripped (logged as TABLE-STRIPPED, tables lost).
import { Proskomma } from 'proskomma-core';
import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, dirname } from 'node:path';
import { sofriaForChapterViaWholeBook } from './whole_book_fallback.mjs';
import { stripTables } from './strip_tables.mjs';

// proskomma-core writes stray attribute text such as '| marker="wj"' or '| marker="ft"'
// into node text. Remove it; wrappers are kept (see convert.mjs).
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

function walk(dir, out) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (name.endsWith('.json')) out.push(p);
  }
  return out;
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

// See whole_book_fallback.mjs for why this fallback exists (a real,
// confirmed proskomma-core@0.11.3 crash on a narrow chapter-boundary
// case) and why it's safe to use.

// Converts one book. Returns { chapterJson: Map<chNum, sofriaJsonString> }.
// Throws on a genuine, unrecoverable failure.
function convertBook(usjText, usj, abbrKey, format = 'usj') {
  const pk = new BiblesPk();
  const doc = pk.importDocument({ lang: 'xx', abbr: abbrKey }, format, usjText);
  const chapterNumbers = collectChapterNumbers(usj);

  const chapterJson = new Map();
  let wholeBookJson = null; // lazily rendered only if a per-chapter call fails
  let usedFallback = false;
  for (const chNum of chapterNumbers) {
    let sofriaJson;
    try {
      sofriaJson = doc.sofria(undefined, chNum);
    } catch (e) {
      if (!wholeBookJson) {
        wholeBookJson = JSON.parse(doc.sofria());
        usedFallback = true;
      }
      sofriaJson = sofriaForChapterViaWholeBook(wholeBookJson, chNum);
    }
    chapterJson.set(chNum, sofriaJson);
  }
  return { chapterJson, usedFallback };
}

function main() {
  const args = process.argv.slice(2);
  const usfmAt = args.indexOf('--usfm-dir');
  const usfmDir = usfmAt !== -1 ? args.splice(usfmAt, 2)[1] : null;
  const [usjDir, sofriaOutDir] = args;
  if (!usjDir || !sofriaOutDir) {
    console.error('usage: node convert_batch.mjs <usj-dir> <sofria-out-dir> [--usfm-dir <dir>]');
    process.exit(2);
  }

  const files = walk(usjDir, []);
  let booksOk = 0, booksFailed = 0, chaptersWritten = 0;

  for (const usjPath of files) {
    const rel = relative(usjDir, usjPath).replace(/\.json$/, '');
    const outDir = join(sofriaOutDir, rel);
    let usjText, usj;
    try {
      usjText = readFileSync(usjPath, 'utf-8');
      usj = JSON.parse(usjText);
      usj = { ...usj, content: splitFigures(usj.content || []) };
      usjText = JSON.stringify(usj);
    } catch (e) {
      console.log('READ-FAIL', usjPath, e.message);
      booksFailed++;
      continue;
    }
    const bookNode = (usj.content || []).find(n => n && n.type === 'book');
    const bookCode = bookNode ? bookNode.code : 'XXX';

    const abbrKey = rel.replace(/[\\/]/g, '_');
    let result;
    try {
      result = convertBook(usjText, usj, abbrKey);
    } catch (e) {
      if (/table/i.test(e.message)) {
        // proskomma-core@0.11.3 has no USJ "table" handler: the import fails the whole
        // book. Its USFM importer handles tables (\tr/\tc become Sofria rows), so use
        // the book's original USFM when it is there.
        const usfmPath = usfmDir ? join(usfmDir, `${rel}.usfm`) : null;
        if (usfmPath && existsSync(usfmPath)) {
          try {
            result = convertBook(readFileSync(usfmPath, 'utf-8'), usj, abbrKey, 'usfm');
            console.log('TABLE-VIA-USFM', rel, bookCode);
          } catch (e2) {
            console.log('SOFRIA-FAIL', rel, bookCode, `USFM import: ${e2.message}`);
            booksFailed++;
            continue;
          }
        } else {
          // Last resort only: strip the tables and keep the rest of the book.
          const { usj: strippedUsj, tablesRemoved } = stripTables(usj);
          try {
            result = convertBook(JSON.stringify(strippedUsj), strippedUsj, abbrKey);
            console.log('TABLE-STRIPPED (no USFM source: tables lost)', rel, bookCode, `tables=${tablesRemoved}`);
          } catch (e2) {
            console.log('SOFRIA-FAIL', rel, bookCode, e2.message);
            booksFailed++;
            continue;
          }
        }
      } else {
        console.log('SOFRIA-FAIL', rel, bookCode, e.message);
        booksFailed++;
        continue;
      }
    }

    mkdirSync(outDir, { recursive: true });
    for (const [chNum, sofriaJson] of result.chapterJson) {
      writeFileSync(join(outDir, `${chNum}.json`), stripWjLeak(sofriaJson));
      chaptersWritten++;
    }
    if (result.usedFallback) console.log('WHOLE-BOOK-FALLBACK', rel, bookCode);
    booksOk++;
  }

  console.log(JSON.stringify({ booksOk, booksFailed, chaptersWritten, totalFiles: files.length }));
}

main();
