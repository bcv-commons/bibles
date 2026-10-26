// USX -> Sofria with proskomma-core, for editions whose source publishes USX but no Sofria
// (158 DBT editions, 2026-10-17). A last resort: where the source publishes Sofria, use it.
//
// proskomma-core's USX importer reads a `|` in text as the start of attributes, as its USJ
// importer does (DBT's own Sofria shows it: CARBSS REV 15:3 `...Jopotory."| default="r"`).
// So every `|` in a USX text node is swapped for PIPE_PLACEHOLDER before import and put back
// after, the same as prepare_usj.mjs does for USJ. With that, this route gives the same verse
// text as usfmtc's USX -> USJ (tools/verse-text/python/usx_to_usj.py).
//
//   import { usxToSofria } from './usx_to_sofria.mjs';
//   const chapters = usxToSofria(usxText);   // { "1": sofriaJsonString, ... }
//
// CLI: node usx_to_sofria.mjs <book.usx> <out-dir>   -> <out-dir>/<chapter>.json
import { Proskomma } from 'proskomma-core';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { PIPE_PLACEHOLDER, finishSofria } from './prepare_usj.mjs';

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

/** A USX book with every `|` in text nodes (not in tags or attributes) protected. */
export function protectUsxPipes(usx) {
  return usx.replace(/>([^<]*)</g, (_, text) => `>${text.replaceAll('|', PIPE_PLACEHOLDER)}<`);
}

export function usxToSofria(usxText) {
  const usx = protectUsxPipes(usxText.replace(/^﻿/, ''));
  const book = (usx.match(/<book[^>]*code="([^"]+)"/) || [])[1] || 'XXX';
  const pk = new BiblesPk();
  const doc = pk.importDocument({ lang: 'xx', abbr: book }, 'usx', usx);
  const chapters = [...usx.matchAll(/<chapter[^>]*number="(\d+)"/g)].map((m) => m[1]);
  const out = {};
  for (const ch of chapters) out[ch] = finishSofria(doc.sofria(undefined, Number(ch)));
  return out;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [, , usxPath, outDir] = process.argv;
  if (!usxPath || !outDir) {
    console.error('usage: node usx_to_sofria.mjs <book.usx> <out-dir>');
    process.exit(2);
  }
  mkdirSync(outDir, { recursive: true });
  const chapters = usxToSofria(readFileSync(usxPath, 'utf8'));
  for (const [ch, json] of Object.entries(chapters)) writeFileSync(`${outDir}/${ch}.json`, json);
  console.log(JSON.stringify({ chapters: Object.keys(chapters).length, outDir }));
}
