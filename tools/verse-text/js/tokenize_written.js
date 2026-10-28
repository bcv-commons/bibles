// Written tokens: the tokenizer's tokens with the marks it drops put back. Same rule as python/bcv_written.py:
// the same tokens at the same positions (len equal, stripMarks(written[i]) === tokenize(text)[i]), each as written in
// the NFC text, its combining marks kept; variation selectors stay dropped. Positions, fingerprints and published
// alignments don't change.
import { tokenize, stripMarks } from './tokenize.js';

export const WRITTEN_VERSION = 1;

const isVariationSelector = (cp) => (cp >= 0xfe00 && cp <= 0xfe0f) || (cp >= 0xe0100 && cp <= 0xe01ef);
const kept = (ch) => stripMarks(ch) !== '';
const droppedMark = (ch) => !kept(ch) && !isVariationSelector(ch.codePointAt(0));

export function tokenizeWritten(text) {
  const nfc = Array.from(text.normalize('NFC'));
  const stripped = [], at = [];
  nfc.forEach((ch, i) => { if (kept(ch)) { stripped.push(ch); at.push(i); } });
  at.push(nfc.length);
  const out = [];
  let cur = 0;
  for (const t of tokenize(text)) {
    const tc = Array.from(t);
    let k = cur;
    while (!tc.every((c, j) => stripped[k + j] === c)) {     // the tokens are substrings of its text, in order
      if (++k > stripped.length - tc.length) throw new Error(`token not in text: ${t}`);
    }
    cur = k + tc.length;
    const a = at[k];
    let b = at[cur - 1] + 1;
    while (b < at[cur] && droppedMark(nfc[b])) b++;          // the marks after the token's last letter
    out.push(nfc.slice(a, b).filter((c) => !isVariationSelector(c.codePointAt(0))).join(''));
  }
  return out;
}
