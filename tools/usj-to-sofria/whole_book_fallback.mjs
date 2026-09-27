// Fallback for a real, confirmed proskomma-core@0.11.3 crash: calling
// doc.sofria(undefined, chapterNumber) throws "outputContentStack is
// empty before pushing to its first element" for any chapter whose
// \cl (chapter label) paragraph contains a footnote AND whose PRECEDING
// chapter ends with a still-open, unclosed verse (no trailing \b or new
// verse to close it) — confirmed by bisection against real content
// (openbible Swahili Psalms, 2026-09-19). Real USFM has no obligation to
// close a chapter's last verse with a blank line, so this combination is
// rare but real — it only actually surfaces where translators added a
// footnote to \cl, essentially only the acrostic Psalms (3, 9, 25, 34,
// 37, 111, 112, 119, 145).
//
// Confirmed real fix: doc.sofria() with NO chapter filter (whole book)
// renders the exact same content cleanly — extracting one chapter's
// blocks from that whole-book render byte-for-byte matches what a
// working doc.sofria(undefined, N) call produces for a chapter that
// doesn't hit the bug (verified directly against real output). So
// callers should try the fast per-chapter path first and only fall back
// to this (re-rendering the WHOLE book once, then re-extracting every
// chapter from it for consistency, not just the one that failed) when a
// per-chapter call throws.
export function extractChapterFromWholeBook(blocks, chapterNumber) {
  const extracted = [];
  let pendingGrafts = [];
  let collecting = false;
  for (const b of blocks) {
    if (b.type === 'graft') {
      pendingGrafts.push(b);
      continue;
    }
    const num = b.content[0].atts.number;
    if (num === chapterNumber) {
      extracted.push(...pendingGrafts, b);
      pendingGrafts = [];
      collecting = true;
    } else {
      pendingGrafts = [];
      if (collecting) break;
    }
  }
  return extracted;
}

export function sofriaForChapterViaWholeBook(wholeBookJson, chapterNumber) {
  const blocks = extractChapterFromWholeBook(wholeBookJson.sequence.blocks, chapterNumber);
  return JSON.stringify({
    schema: wholeBookJson.schema,
    metadata: {
      translation: wholeBookJson.metadata.translation,
      document: {
        ...wholeBookJson.metadata.document,
        properties: { ...wholeBookJson.metadata.document.properties, chapters: chapterNumber },
      },
    },
    sequence: { type: 'main', blocks },
  });
}
