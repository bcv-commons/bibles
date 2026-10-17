// bcv text fingerprint v1, on top of tokenize.js (tokenizer v2). Reference implementation handed over by bcv-commons/lexeme-aligner
// to bcv-commons/bibles on 2026-10-17, CC0 1.0; mirrors python/bcv_tokenize.py. Verse text comes from bibles' extraction rule
// (tools/verse-text), not from this file. Uses Web Crypto (globalThis.crypto.subtle): browsers and Node >= 19. No dependencies.
import { tokenize } from "./tokenize.js";

export const TEXT_FP_VERSION = 1;
export const NAME_HEX = 8;

async function sha256(s) {
  const buf = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
}

// The hashed line for one verse, or null when the verse has no tokens (left out of the fingerprint).
export function verseLine(verse, text) {
  const toks = tokenize(text);
  return toks.length ? `${verse}:${toks.join(" ")}` : null;
}

// verses: Map "chapter:verse" -> verse text (numbers, a bridge under its first verse).
// Returns {book, chapters: {chapter: fp}}: 64-hex SHA-256 digests.
export async function fingerprints(verses) {
  const keys = [...verses.keys()].map((k) => k.split(":").map(Number)).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const lines = new Map();
  for (const [c, v] of keys) {
    const line = verseLine(v, verses.get(`${c}:${v}`));
    if (line !== null) { if (!lines.has(c)) lines.set(c, []); lines.get(c).push(line); }
  }
  const chapters = {};
  for (const [c, ls] of lines) chapters[c] = await sha256(ls.join("\n"));
  const order = [...lines.keys()].sort((a, b) => a - b);
  const book = await sha256(order.map((c) => `${c}:${chapters[c]}`).join("\n"));
  return { book, chapters };
}

// The hash in a compact-alignments file name: <BOOK>_<fileHash>.json
export const fileHash = (bookFp) => bookFp.slice(0, NAME_HEX);
