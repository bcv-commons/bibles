#!/usr/bin/env node
// Batch sibling of convert.mjs — one Node process handles many book-level
// USJ files instead of spawning a fresh process per book (process startup
// dominates at corpus scale: thousands of books across hundreds of
// editions). Walks <usj-dir> recursively for *.json files; for each,
// mirrors its relative path (minus .json) as a directory under
// <sofria-out-dir> and writes one Sofria file per chapter into it.
//
// Usage: node convert_batch.mjs <usj-dir> <sofria-out-dir>
//
// Each book's USJ is first prepared for the importer (prepare_usj.mjs: figures,
// tables, optional breaks, duplicate \cp).
import { Proskomma } from 'proskomma-core';
import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync } from 'node:fs';
import { join, relative, dirname } from 'node:path';
import { sofriaForChapterViaWholeBook } from './whole_book_fallback.mjs';
import { prepareUsj } from './prepare_usj.mjs';

// proskomma-core writes stray attribute text such as '| marker="wj"' or '| marker="ft"'
// into node text. Remove it; wrappers are kept (see convert.mjs).
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
    else if (name.endsWith('.json') && name !== '_meta.json') out.push(p); // _meta.json: edition metadata, not a book
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
function convertBook(usjText, usj, abbrKey) {
  const pk = new BiblesPk();
  const doc = pk.importDocument({ lang: 'xx', abbr: abbrKey }, 'usj', usjText);
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
  const [usjDir, sofriaOutDir] = process.argv.slice(2);
  if (!usjDir || !sofriaOutDir) {
    console.error('usage: node convert_batch.mjs <usj-dir> <sofria-out-dir>');
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
      usj = prepareUsj(usj);
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
      console.log('SOFRIA-FAIL', rel, bookCode, e.message);
      booksFailed++;
      continue;
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
