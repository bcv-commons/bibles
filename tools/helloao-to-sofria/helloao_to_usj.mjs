// Convert helloAO's real per-chapter JSON (bible.helloao.org/api/<id>/<BOOK>/<N>.json,
// or the "chapter" entries inside .../<id>/complete.json) into USJ (Unified
// Scripture JSON) — the only one of the 4 sources this repo tracks with no
// USFM available at all (confirmed live: every real helloAO translation
// reports `availableFormats: ["json"]` only), so this is a bespoke
// JSON->JSON mapping, not a USFM parse.
//
// This is a faithful JS port of this repo's own Python original,
// pipeline/core/helloao_to_usj.py — same mapping decisions, same
// real-content-confirmed edge cases (poem-level state tracking, mid-verse
// inline headings/lineBreaks, footnote refs resolved by id not position,
// the join-space heuristic around footnotes described below). Kept
// dependency-free (no proskomma-core, no anything) on purpose — this file
// alone is a complete, standalone "helloAO -> USJ" client example; see
// this directory's README for how it's used both on its own and as the
// first stage of a full helloAO -> Sofria conversion.
//
// Real schema (confirmed directly against live chapters):
//   chapter.content[] items:
//     {"type": "heading", "content": [str, ...]}
//     {"type": "hebrew_subtitle", "content": [str | {"noteId": int}, ...]}
//     {"type": "line_break"}
//     {"type": "verse", "number": int, "content": [
//         str
//         | {"text": str, "poem": int}       // poetry indent -> \q1/\q2/...
//         | {"text": str, "wordsOfJesus": true}
//         | {"heading": str}                  // rare: inline heading mid-verse
//         | {"lineBreak": true}               // end of a line (between poetry lines)
//         | {"noteId": int}                   // footnote reference
//     ]}
//   chapter.footnotes[]:
//     {"noteId": int, "text": str, "caller": str|null, "reference": {...}}

const POEM_MARKER = { 1: 'q1', 2: 'q2', 3: 'q3', 4: 'q4' };

// helloAO's raw content lists split running text into separate fragments
// around {"noteId": N} refs (and around poem-level changes) with NO
// whitespace of their own at the split points — joining fragments always
// needs an explicit decision, never a bare concatenation. But the
// decision isn't "always insert a space": real English sentence
// punctuation matters (a footnote sitting INSIDE a parenthetical,
// "...phrase(<note>)." must NOT get a space before ").", but a footnote
// mid-sentence between two whole words, "...Jesus,<note>because He...",
// DOES need one). These two sets encode standard no-space-before/
// no-space-after English typesetting rules to make that call correctly.
const NO_SPACE_BEFORE = new Set([',', '.', ';', ':', '!', '?', ')', ']', '}', '’', '”']);
const NO_SPACE_AFTER = new Set(['(', '[', '{', '‘', '“']);

function lastCharOf(content) {
  // Last VISIBLE character already in `content`, skipping over note nodes
  // (a footnote mark renders inline without consuming surrounding space,
  // so it must not block finding the real preceding character).
  for (let i = content.length - 1; i >= 0; i--) {
    const item = content[i];
    if (typeof item === 'string') {
      if (item) return item[item.length - 1];
      continue;
    }
    if (item && typeof item === 'object' && item.type === 'char') {
      const c = lastCharOf(item.content || []);
      if (c !== null) return c;
      continue;
    }
    // "note" and any other node type: skip past, keep looking back
  }
  return null;
}

function firstCharOf(piece) {
  if (typeof piece === 'string') return piece ? piece[0] : null;
  if (piece && typeof piece === 'object' && piece.type === 'char') {
    for (const item of piece.content || []) {
      const c = firstCharOf(item);
      if (c !== null) return c;
    }
  }
  return null;
}

function needsSpace(prevChar, nextChar) {
  if (prevChar === null || nextChar === null) return false;
  if (NO_SPACE_BEFORE.has(nextChar) || NO_SPACE_AFTER.has(prevChar)) return false;
  return true;
}

function prefixSpace(piece) {
  if (typeof piece === 'string') return ' ' + piece;
  if (piece && typeof piece === 'object' && piece.type === 'char') {
    const content = [...(piece.content || [])];
    if (content.length && typeof content[0] === 'string') {
      content[0] = ' ' + content[0];
      return { ...piece, content };
    }
  }
  return piece;
}

function appendPiece(contentList, piece) {
  // Append a text-bearing piece (plain string, or a "char" node like
  // marker "wj"), inserting a joining space first if the real English
  // typesetting rules above call for one. Note nodes bypass this — they
  // have no visible leading/trailing character of their own.
  if (needsSpace(lastCharOf(contentList), firstCharOf(piece))) piece = prefixSpace(piece);
  contentList.push(piece);
}

function flushPara(topContent, state) {
  if (state.para !== null && (state.para.content.length || state.para.marker === 'b')) {
    topContent.push(state.para);
  }
  state.para = null;
  state.paraMarker = null;
}

// An inline {"lineBreak": true} ends the current line, nothing more: helloAO puts one
// between every pair of poetry lines (BSB MAT 1:2, all of Psalms). Close the paragraph
// so the next fragment opens a new one, even at the same poem level; a plain-string
// fragment after it continues at that level. Only the top-level {"type": "line_break"}
// is a blank line (\b).
function endLine(topContent, state) {
  const marker = state.paraMarker;
  flushPara(topContent, state);
  state.lineMarker = marker;
}

function ensurePara(topContent, state, marker) {
  if (state.paraMarker !== marker) {
    flushPara(topContent, state);
    state.para = { type: 'para', marker, content: [] };
    state.paraMarker = marker;
  }
  // A verse's number goes into the paragraph its first content opens, so a verse that
  // starts with poetry doesn't leave its number alone in a \p of its own.
  if (state.pendingVerse) {
    state.para.content.push(state.pendingVerse);
    state.pendingVerse = null;
  }
  return state.para;
}

function resolveNote(footnotesById, noteId) {
  const fn = footnotesById.get(noteId);
  if (!fn) return null;
  const caller = fn.caller || '+';
  const text = (fn.text || '').trim();
  const node = { type: 'note', marker: 'f', caller, content: [] };
  if (text) {
    // Deliberately a bare string, NOT {"type":"char","marker":"ft",...} —
    // real Proskomma (proskomma-core@0.11.3) confirmed live: a "char"
    // node with marker "ft" nested inside a "note" node, imported via its
    // own USJ importer, corrupts the text with a stray literal
    // `| marker="ft"` prefix (see internal-docs/pkf-encode-decode-bugs-found.md
    // #8 — a real Proskomma bug, reproduced in isolation, not our data).
    // A bare string imports clean; \ft is USFM's implicit default
    // footnote-text marker right after the caller anyway, so nothing is
    // lost by omitting the explicit char wrapper.
    node.content.push(text);
  }
  return node;
}

function appendHeading(topContent, state, marker, items, footnotesById) {
  // Build a heading/subtitle paragraph from a real content list — not
  // always plain strings: hebrew_subtitle in particular can interleave
  // {"noteId": N} footnote refs between text fragments.
  flushPara(topContent, state);
  const content = [];
  for (const item of items) {
    if (typeof item === 'string') {
      const text = item.trim();
      if (text) appendPiece(content, text);
    } else if (item && typeof item === 'object' && 'noteId' in item) {
      const note = resolveNote(footnotesById, item.noteId);
      if (note) content.push(note);
    }
  }
  if (content.length) topContent.push({ type: 'para', marker, content });
}

function appendBlank(topContent, state) {
  flushPara(topContent, state);
  state.lineMarker = null;
  topContent.push({ type: 'para', marker: 'b', content: [] });
}

function walkVerseContent(item, topContent, state, footnotesById) {
  // Append one verse-content item into the currently-open paragraph
  // (opening/switching paragraphs as needed for poem-level changes).
  if (typeof item === 'string') {
    const para = ensurePara(topContent, state, state.paraMarker || state.lineMarker || 'p');
    appendPiece(para.content, item);
    return;
  }
  if (!item || typeof item !== 'object') return;

  if ('noteId' in item) {
    const para = ensurePara(topContent, state, state.paraMarker || state.lineMarker || 'p');
    const note = resolveNote(footnotesById, item.noteId);
    if (note) para.content.push(note);
    return;
  }
  if ('lineBreak' in item) {
    endLine(topContent, state);
    return;
  }
  if ('heading' in item) {
    appendHeading(topContent, state, 's1', [item.heading], footnotesById);
    return;
  }
  if ('text' in item) {
    const poem = item.poem;
    const marker = poem ? (POEM_MARKER[poem] || 'p') : (state.paraMarker || state.lineMarker || 'p');
    const para = ensurePara(topContent, state, marker);
    const text = item.text;
    if (item.wordsOfJesus) {
      appendPiece(para.content, { type: 'char', marker: 'wj', content: [text] });
    } else {
      appendPiece(para.content, text);
    }
  }
}

/**
 * helloAO's real per-chapter API response (the full JSON, with a
 * "chapter" key) -> a real USJ 3.0 document for that one chapter,
 * including a real \id/book node so the result is independently valid
 * (not just a content fragment).
 */
export function chapterToUsj(chapterJson, bookCode) {
  const chapter = chapterJson.chapter;
  const footnotesById = new Map((chapter.footnotes || []).map(fn => [fn.noteId, fn]));

  const topContent = [
    { type: 'book', marker: 'id', code: bookCode, content: [] },
    { type: 'chapter', marker: 'c', number: String(chapter.number) },
  ];
  const state = { para: null, paraMarker: null, lineMarker: null, pendingVerse: null };

  for (const item of chapter.content || []) {
    const kind = item && typeof item === 'object' ? item.type : null;
    if (kind === 'heading') {
      appendHeading(topContent, state, 's1', item.content || [], footnotesById);
    } else if (kind === 'hebrew_subtitle') {
      appendHeading(topContent, state, 'd', item.content || [], footnotesById);
    } else if (kind === 'line_break') {
      appendBlank(topContent, state);
    } else if (kind === 'verse') {
      state.pendingVerse = { type: 'verse', marker: 'v', number: String(item.number) };
      for (const sub of item.content || []) {
        walkVerseContent(sub, topContent, state, footnotesById);
      }
      if (state.pendingVerse) ensurePara(topContent, state, state.paraMarker || state.lineMarker || 'p'); // a verse with no content
    }
    // Any other/unknown top-level type is skipped, not guessed at.
  }

  flushPara(topContent, state);
  return { type: 'USJ', version: '3.0', content: topContent };
}

/**
 * Concatenate a book's real per-chapter USJ docs (each produced by
 * chapterToUsj()) into one book-level USJ — keep the first doc's "book"
 * node, then append every doc's "chapter"+content nodes after it.
 */
export function mergeBookUsj(bookCode, chaptersJson) {
  const mergedContent = [];
  chaptersJson.forEach((cj, i) => {
    const usj = chapterToUsj(cj, bookCode);
    const nodes = usj.content;
    if (i === 0) {
      mergedContent.push(...nodes);
    } else {
      mergedContent.push(...nodes.filter(n => n.type !== 'book'));
    }
  });
  return { type: 'USJ', version: '3.0', content: mergedContent };
}
