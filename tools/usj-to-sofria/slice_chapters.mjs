// Splits one book-level USJ document into standalone, single-chapter USJ
// documents — one real "book" id node + (for chapter 1 only) any real
// front matter that precedes the first "chapter" node (\ide/\rem/\h/
// \toc*/\mt*/\imt*/\ip*/\iot/\io* etc.) + exactly that chapter's own
// content, nothing else.
//
// Why this exists: the OBVIOUS way to get per-chapter Sofria is to
// import the WHOLE book once and call doc.sofria(undefined, chapterNum)
// per chapter — that's what this repo did until 2026-09-19. But that
// approach has two real, confirmed problems, both eliminated by
// importing each chapter as its own independent document instead:
//   1. A chapter whose leading content is entirely heading text (nothing
//      before the first verse) loses that heading when isolated from a
//      multi-chapter import via the chapter filter — confirmed directly
//      (real BSB Psalm 1, "The Two Paths"). Importing that SAME chapter
//      standalone keeps the heading, and produces byte-identical
//      sequence.blocks to the filtered approach for every chapter that
//      DIDN'T have this problem (confirmed directly, full diff).
//   2. The real outputContentStack crash (see whole_book_fallback.mjs)
//      — triggered by state carried across a chapter boundary from a
//      still-open verse in the PREVIOUS chapter — cannot happen at all
//      when there is no previous chapter in the document (confirmed
//      directly: the exact real content that crashed via chapter-filter
//      imports and renders cleanly as a standalone single-chapter doc).
//
// So this is a strict improvement, not a workaround: same real content
// for every chapter that already worked, MORE correct content for the
// chapters that didn't, and the crash class simply doesn't arise.
// whole_book_fallback.mjs is kept as a defensive fallback in case some
// other real content hits a still-undiscovered case, but is not expected
// to fire in normal operation any more.
// Proskomma promotes certain USJ front-matter para markers to
// DOCUMENT-level Sofria metadata (metadata.document.ide/h/toc/toc2/toc3),
// not to a content block — confirmed directly: a real book's chapter 6,
// rendered via the OLD whole-book+chapter-filter approach, carries
// ide/h/toc/toc2/toc3 in its metadata even though chapter 6's own USJ slice
// (per this module) contains none of the \h/\toc1-3 nodes that produced
// them (those sit in chapter 1's front matter only). Content-blocks
// (title/introduction grafts from \mt/\imt/\ip etc.) correctly stay
// chapter-1-only — confirmed directly too (sequence.blocks byte-
// identical between old and new for a non-chapter-1 book with real
// front matter) — only these specific metadata-only fields need
// carrying to every chapter. "cl" is a genuine Proskomma quirk, kept for
// drop-in compatibility: it isn't a stable per-book value at all — it's
// always whichever \cl paragraph (front-matter OR any later per-chapter
// one) was LAST encountered during a whole-document import, confirmed
// directly (a real book's chapter 6 metadata carries chapter 150's own
// \cl text, not chapter 6's or the book's front-matter one).
const _METADATA_MARKER_FIELD = { ide: 'ide', h: 'h', toc1: 'toc', toc2: 'toc2', toc3: 'toc3' };

export function bookLevelMetadataFields(usj) {
  // "Last wins" for every one of these fields, not just "cl" — confirmed
  // directly on real content that legitimately has more than one \toc1
  // in its front matter (a translator/digitization quirk, but real): old
  // per-chapter output kept the LATER value, not the first.
  const fields = {};
  for (const node of usj.content || []) {
    if (!node || typeof node !== 'object' || node.type !== 'para') continue;
    const field = _METADATA_MARKER_FIELD[node.marker] || (node.marker === 'cl' ? 'cl' : null);
    if (field && node.content && node.content[0]) {
      fields[field] = node.content[0];
    }
  }
  return fields;
}

export function sliceIntoChapters(usj) {
  const content = usj.content || [];
  const bookNode = content.find(n => n && n.type === 'book');
  const chapterPositions = [];
  content.forEach((n, i) => {
    if (n && n.type === 'chapter') chapterPositions.push(i);
  });

  const slices = [];
  for (let k = 0; k < chapterPositions.length; k++) {
    const startIdx = chapterPositions[k];
    const endIdx = k + 1 < chapterPositions.length ? chapterPositions[k + 1] : content.length;
    const chapterNumber = String(content[startIdx].number);
    const ownContent = content.slice(startIdx, endIdx);
    const sliceContent = k === 0
      ? [bookNode, ...content.slice(1, startIdx).filter(n => n !== bookNode), ...ownContent]
      : [bookNode, ...ownContent];
    slices.push({ chapterNumber, usj: { type: 'USJ', version: usj.version || '3.0', content: sliceContent } });
  }
  return slices;
}
