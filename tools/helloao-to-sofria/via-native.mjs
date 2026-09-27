#!/usr/bin/env node
// Sample client solution #2: helloAO -> Sofria, hand-built — NO
// proskomma-core, no library dependency of any kind (see
// usj_to_sofria_native.mjs's own docstring for the scope limit: this
// knows exactly the node shapes this repo's own helloAO mapping
// produces, not a general USJ/Sofria engine). Reuses the same shared
// helloao_to_usj.mjs mapping module as via-usj.mjs — the only real
// difference between the two examples is the LAST step: handing the USJ
// tree to a real library vs. rendering it by hand.
//
// Usage: node via-native.mjs <helloAO-complete.json> <out-dir>
//   Writes <out-dir>/sofria/<BOOK>/<N>.json — no intermediate USJ file,
//   since the whole point here is not touching any USJ/Proskomma tooling.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { chapterToUsj } from './helloao_to_usj.mjs';
import { usjChapterToSofriaNative } from './usj_to_sofria_native.mjs';

function main() {
  const [, , completePath, outDir] = process.argv;
  if (!completePath || !outDir) {
    console.error('usage: node via-native.mjs <helloAO-complete.json> <out-dir>');
    process.exit(2);
  }

  const complete = JSON.parse(readFileSync(completePath, 'utf-8'));
  const sofriaDir = `${outDir}/sofria`;

  let booksOk = 0, chaptersWritten = 0;
  for (const book of complete.books || []) {
    if (!book.id || !book.chapters || !book.chapters.length) continue;

    const bookSofriaDir = `${sofriaDir}/${book.id}`;
    mkdirSync(bookSofriaDir, { recursive: true });
    for (const chapterJson of book.chapters) {
      const usj = chapterToUsj(chapterJson, book.id);
      const sofria = usjChapterToSofriaNative(usj, { lang: 'xx', abbr: book.id });
      const chNum = sofria.metadata.document.properties.chapters;
      writeFileSync(`${bookSofriaDir}/${chNum}.json`, JSON.stringify(sofria));
      chaptersWritten++;
    }
    booksOk++;
  }

  console.log(JSON.stringify({ booksOk, chaptersWritten, sofriaDir }));
}

main();
