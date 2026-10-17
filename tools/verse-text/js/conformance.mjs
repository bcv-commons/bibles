// Conformance suite, JS side: the same checks as ../python/conformance.py on ../conformance/
// (rules.json and the helloAO chapters). The DBT cases need a DBT API key: run them in Python.
// Usage: node conformance.mjs
import { readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { clean } from './rule.js';
import { extractUsj } from './extract_usj.js';
import { extractPlain } from './extract_plain.js';
import { chapterToUsj } from './helloao_to_usj.mjs';
import { tokenize } from './tokenize.js';
import { fingerprints, verseLine, TEXT_FP_VERSION } from './text_fingerprint.mjs';
import { content, contentFingerprints, CONTENT_FP_VERSION } from './content_fingerprint.mjs';

const SUITE = join(dirname(fileURLToPath(import.meta.url)), '..', 'conformance');
const read = (p) => JSON.parse(readFileSync(p, 'utf8'));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
let bad = 0;
const fail = (...m) => { bad++; console.log('FAIL', ...m); };
const chapterMap = (verses) => new Map(verses.filter((v) => /^\d+$/.test(v.verse)).map((v) => [`1:${Number(v.verse)}`, v.text]));

const fns = { clean, plain: extractPlain, usj: extractUsj, content };
let rules = 0;
for (const [kind, cases] of Object.entries(read(join(SUITE, 'rules.json'))))
  for (const c of cases) { rules++; if (!same(fns[kind](c.in), c.out)) fail(kind, c.why); }

const contentExpected = read(join(SUITE, 'content.expected.json'));
let chapters = 0;
for (const ed of readdirSync(join(SUITE, 'helloao')).sort())
  for (const f of readdirSync(join(SUITE, 'helloao', ed)).filter((x) => x.endsWith('.expected.json')).sort()) {
    const e = read(join(SUITE, 'helloao', ed, f)), src = e.source, name = `${ed}/${f.replace('.expected.json', '')}`;
    const raw = read(join(SUITE, 'helloao', ed, f.replace('.expected.', '.input.')));
    const verses = extractUsj(chapterToUsj(raw, src.book))[String(src.chapter)] || [];
    const got = new Map(verses.map((v) => [v.verse, v.text]));
    for (const v of e.verses) {
      if (got.get(String(v.verse)) !== v.text) fail('text', name, v.verse);
      if (!same(tokenize(v.text), v.tokens) || verseLine(v.verse, v.text) !== v.line) fail('tokens', name, v.verse);
    }
    const m = chapterMap(verses);
    if ((await fingerprints(m)).chapters[1] !== e.chapter_fp) fail('text fp', name);
    if ((await contentFingerprints(m)).chapters[1] !== contentExpected[name]) fail('content fp', name);
    chapters++;
  }

console.log(`tokenizer v2, text fingerprint v${TEXT_FP_VERSION}, content fingerprint v${CONTENT_FP_VERSION}`);
console.log(`rules: ${rules} cases\nhelloAO: ${chapters} chapters\n${bad} failures`);
process.exit(bad ? 1 : 0);
