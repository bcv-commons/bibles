// Content fingerprint v1: for diagnosis only. Mirrors ../python/content_fingerprint.py; the
// definition is written out there. Same shape as text_fingerprint.mjs. Web Crypto (browsers,
// Node >= 19), no dependencies.
//
//   content(text) -> string
//   contentFingerprints(Map "chapter:verse" -> text) -> {book, chapters: {chapter: fp}}

export const CONTENT_FP_VERSION = 1;

// ' ’ ʼ ʻ ꞌ ´ ` ′ ＇ -> ʼ (U+02BC). Not ‘ (U+2018): almost always an opening quote.
export const APOSTROPHES = "'’ʼʻꞌ´`′＇";
const TO_ONE = new RegExp(`[${APOSTROPHES.replace(/[\]\\^-]/g, '\\$&')}]`, 'g');
const NOT_LM = /[^\p{L}\p{M}]/gu;

export function content(text) {
  const s = text.normalize('NFC').toLowerCase().replaceAll('ς', 'σ').replace(TO_ONE, 'ʼ');
  return s.normalize('NFC').replace(NOT_LM, '');
}

async function sha256(s) {
  const buf = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('');
}

export async function contentFingerprints(verses) {
  const keys = [...verses.keys()].map((k) => k.split(':').map(Number)).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const lines = new Map();
  for (const [c, v] of keys) {
    const t = content(verses.get(`${c}:${v}`));
    if (t) { if (!lines.has(c)) lines.set(c, []); lines.get(c).push(`${v}:${t}`); }
  }
  const chapters = {};
  for (const [c, ls] of lines) chapters[c] = await sha256(ls.join('\n'));
  const order = [...lines.keys()].sort((a, b) => a - b);
  const book = await sha256(order.map((c) => `${c}:${chapters[c]}`).join('\n'));
  return { book, chapters };
}
