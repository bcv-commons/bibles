#!/usr/bin/env node
// Sample client solution #1: helloAO -> USJ -> Sofria, USING real
// proskomma-core for the second hop (the same real, working path already
// built at tools/usj-to-sofria/convert.mjs — this file just wires a
// helloAO complete.json into it). Produces real, library-verified Sofria
// — the intermediate USJ is also written out, since it's independently
// useful (portable to any other USJ-consuming tool, not just Sofria).
//
// See ./via-native.mjs for the alternative that skips proskomma-core
// entirely (hand-built Sofria, no dependency) — both are equally valid
// starting points; which one fits depends on whether the client already
// has proskomma-core available (see this directory's README).
//
// Usage: node via-usj.mjs <helloAO-complete.json> <out-dir>
//   Writes <out-dir>/usj/<BOOK>.json and <out-dir>/sofria/<BOOK>/<N>.json
import { Proskomma } from 'proskomma-core';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { mergeBookUsj } from './helloao_to_usj.mjs';

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
  return (usj.content || [])
    .filter(n => n && n.type === 'chapter' && n.number != null)
    .map(n => String(n.number));
}

function main() {
  const [, , completePath, outDir] = process.argv;
  if (!completePath || !outDir) {
    console.error('usage: node via-usj.mjs <helloAO-complete.json> <out-dir>');
    process.exit(2);
  }

  const complete = JSON.parse(readFileSync(completePath, 'utf-8'));
  const usjDir = `${outDir}/usj`;
  const sofriaDir = `${outDir}/sofria`;
  mkdirSync(usjDir, { recursive: true });

  let booksOk = 0, chaptersWritten = 0;
  for (const book of complete.books || []) {
    if (!book.id || !book.chapters || !book.chapters.length) continue;

    const usj = mergeBookUsj(book.id, book.chapters);
    const usjText = JSON.stringify(usj);
    writeFileSync(`${usjDir}/${book.id}.json`, usjText);

    const pk = new BiblesPk();
    const doc = pk.importDocument({ lang: 'xx', abbr: book.id }, 'usj', usjText);
    const bookSofriaDir = `${sofriaDir}/${book.id}`;
    mkdirSync(bookSofriaDir, { recursive: true });
    for (const chNum of collectChapterNumbers(usj)) {
      writeFileSync(`${bookSofriaDir}/${chNum}.json`, doc.sofria(undefined, chNum));
      chaptersWritten++;
    }
    booksOk++;
  }

  console.log(JSON.stringify({ booksOk, chaptersWritten, usjDir, sofriaDir }));
}

main();
