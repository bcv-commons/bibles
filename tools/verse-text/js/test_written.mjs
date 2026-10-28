// tokenizeWritten against conformance/written.expected.json. Run: node js/test_written.mjs
import { readFileSync } from 'node:fs';
import { tokenize, stripMarks } from './tokenize.js';
import { tokenizeWritten } from './tokenize_written.js';

const cases = JSON.parse(readFileSync(new URL('../conformance/written.expected.json', import.meta.url), 'utf8'));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
let bad = 0;
for (const c of cases) {
  const t = tokenize(c.input), w = tokenizeWritten(c.input);
  if (!same(t, c.tokens) || !same(w, c.written) || !same(w.map(stripMarks), t)) { bad++; console.log('FAIL', c.name, w); }
}
console.log(bad ? `${bad} failing` : `ok ${cases.length}`);
process.exit(bad ? 1 : 0);
