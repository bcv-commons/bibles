// Hand-built USJ (chapter-level, as produced by helloao_to_usj.mjs) ->
// Sofria renderer — NO proskomma-core, no dependency of any kind. This is
// the "not even hidden" alternative to via-usj.mjs: instead of handing
// USJ to the real library and letting it derive Sofria, this file
// reproduces the exact block/wrapper/mark structure by hand.
//
// The exact shape below (which paragraph gets the chapter_label mark,
// how the verses wrapper reopens across paragraph blocks without a fresh
// verses_label, marker canonicalization s1->s / q1->q, the footnote
// graft's inner note_caller sub-graft) was reverse-engineered from REAL
// output of real proskomma-core@0.11.3 (`doc.sofria(undefined, N)`) on
// real BSB content — captured and diffed directly, not guessed from any
// spec document, and only for the specific node shapes this repo's own
// helloAO->USJ mapping ever actually produces:
//   para markers: d, p, q1-q4, b, s1 (s1 is the one that becomes a
//     detached "heading" graft, not an inline paragraph — everything
//     else stays inline, wrapped in a per-chapter "chapter" wrapper)
//   verse marks, note (footnote) grafts, and "wj" char nodes.
//
// SCOPE LIMIT, stated plainly: this is not a general USJ->Sofria engine.
// It knows exactly the node shapes above and nothing more — an
// unrecognized para marker or node type is passed through inline rather
// than silently dropped, but its Sofria shape is NOT guaranteed to match
// what real Proskomma would produce for it. The "wj" (words-of-Jesus)
// mapping below is a best-effort extrapolation of the one real char-node
// pattern actually observed (footnote text as a "usfm:<marker>" wrapper)
// — not independently confirmed against a live "wj" sample (see
// pipeline/core/helloao_to_usj.py's own docstring: wordsOfJesus hasn't
// been seen in a real sample checked so far either).

// s1 -> s, q1 -> q: real USFM/Proskomma convention, numbered-level-1
// markers canonicalize to their bare form (confirmed directly: real
// Sofria output for our own "s1"/"q1" USJ markers came back "usfm:s"/
// "usfm:q", never "usfm:s1"/"usfm:q1"). q2/q3/q4 are NOT canonicalized.
function canonicalMarker(marker) {
  if (marker === 's1') return 's';
  if (marker === 'q1') return 'q';
  return marker;
}

function renderNote(note) {
  return {
    type: 'graft',
    subtype: 'footnote',
    sequence: {
      type: 'footnote',
      blocks: [
        {
          type: 'paragraph',
          subtype: 'usfm:f',
          content: [
            {
              type: 'graft',
              subtype: 'note_caller',
              sequence: {
                type: 'note_caller',
                blocks: [{ type: 'paragraph', subtype: 'usfm:f', content: [note.caller || '+'] }],
              },
            },
            ...note.content,
          ],
        },
      ],
    },
  };
}

function renderChar(charNode) {
  return { type: 'wrapper', subtype: `usfm:${charNode.marker}`, content: charNode.content, atts: {} };
}

// Walk one USJ paragraph's `content` array, wrapping it in the real
// "chapter" wrapper (with the chapter_label mark only the first time
// this document emits ANY paragraph) and, wherever a "verse" node
// starts, a nested "verses" wrapper (with a verses_label mark only the
// first time THAT verse number appears — a verse's text can legitimately
// span multiple paragraph blocks, e.g. poetry \q1/\q2 lines, and only
// the very first block carries the label; later blocks just reopen a
// bare "verses" wrapper with the same atts.number, confirmed directly).
//
// A verse's "open" state also persists PAST a paragraph block boundary
// for any content that appears BEFORE the next fresh verse marker
// (confirmed directly against real output, two distinct cases):
//   - A "b" blank-line paragraph sitting between two verses reopens an
//     EMPTY "verses" wrapper for whatever verse was still open (real 1
//     Chronicles 1, `\v 1 Adam, Seth, Enosh,\b \v 2 ...` renders the `\b`
//     block as `{"wrapper","verses",content:[],atts:{number:"1"}}`).
//   - A verse's continuation text that leads a later paragraph block
//     BEFORE that block's own next verse starts also reopens the prior
//     verse's wrapper first (real 1 Chronicles 1:29, "Nebaioth the
//     firstborn of Ishmael..." sits at the START of a block whose next
//     item is verse 30's marker — it renders wrapped in verse 29's
//     reopened wrapper, not as a bare string).
// But a block whose very FIRST item is itself a fresh verse marker does
// NOT also emit a leading empty wrapper for whatever was open before it
// (confirmed the same way: the paragraph starting verse 2 as its first
// item shows only verse 2's wrapper, no residual verse-1 one). So the
// reopen decision is based on the block's first item only, not whether a
// verse marker appears anywhere in the block.
function buildChapterWrapperContent(paraContent, docState) {
  const chapterInner = [];
  if (!docState.chapterLabelEmitted) {
    chapterInner.push({ type: 'mark', subtype: 'chapter_label', atts: { number: String(docState.chapterNumber) } });
    docState.chapterLabelEmitted = true;
  }

  const firstItem = paraContent[0];
  const startsWithVerseMarker = !!(firstItem && typeof firstItem === 'object' && firstItem.type === 'verse');
  let currentVerse = null; // { number, content: [] }
  if (!startsWithVerseMarker && docState.currentVerseNumber !== null) {
    currentVerse = { number: docState.currentVerseNumber, content: [] };
  }

  const flushVerse = () => {
    if (currentVerse) {
      chapterInner.push({ type: 'wrapper', subtype: 'verses', content: currentVerse.content, atts: { number: currentVerse.number } });
      currentVerse = null;
    }
  };
  const target = () => (currentVerse ? currentVerse.content : chapterInner);

  for (const item of paraContent) {
    if (item && typeof item === 'object' && item.type === 'verse') {
      flushVerse();
      const num = item.number;
      const content = [];
      if (!docState.verseLabelEmitted.has(num)) {
        content.push({ type: 'mark', subtype: 'verses_label', atts: { number: String(num) } });
        docState.verseLabelEmitted.add(num);
      }
      currentVerse = { number: num, content };
      docState.currentVerseNumber = num;
      continue;
    }
    if (item && typeof item === 'object' && item.type === 'note') {
      target().push(renderNote(item));
      continue;
    }
    if (item && typeof item === 'object' && item.type === 'char') {
      target().push(renderChar(item));
      continue;
    }
    if (typeof item === 'string') {
      // Merge with an immediately-preceding plain string rather than
      // pushing a separate array entry — confirmed directly: real
      // Proskomma output combines two adjacent plain-text USJ content
      // items (e.g. helloAO's own Amos 1:5, "...Kir,”" then a separate
      // trailing "says the LORD." fragment with no note between them)
      // into one single string, while helloao_to_usj.mjs's own
      // appendPiece() (correctly) only prefixes the joining space onto
      // the new piece, never merges it into the array — that merge step
      // belongs here, in the Sofria-shaped output, not the USJ tree.
      const arr = target();
      const last = arr[arr.length - 1];
      if (typeof last === 'string') {
        arr[arr.length - 1] = last + item;
      } else {
        arr.push(item);
      }
      continue;
    }
    // Unrecognized node type: pass through as-is rather than drop it —
    // see the module docstring's scope-limit note.
    target().push(item);
  }
  flushVerse();
  return chapterInner;
}

// Post-processing correction pass for one known, precisely-shaped defect:
// when a verse's own USJ paragraph ends right at the verse mark (its
// first real content starts in the NEXT usj "para" — e.g. a poem-level
// change exactly at a verse boundary), the per-block walk above (which
// mirrors USJ paragraph boundaries 1:1) leaves the verses_label mark
// stranded alone in the ending block, with the verse's real text
// starting unlabeled in the next block's reopened wrapper. Real
// Proskomma does NOT do this — it groups a verse mark with its own first
// real content regardless of which USJ paragraph textually holds it,
// something the per-block walk here can't replicate without
// reimplementing that grouping algorithm from scratch. Confirmed
// directly against real proskomma-core@0.11.3 output (BSB 1 Peter 1:24-25)
// that the defect has one exact, mechanical shape: a trailing "verses"
// wrapper whose content is ONLY the label mark (nothing else), followed
// by the next paragraph block's chapter-wrapper leading with an
// unlabeled "verses" wrapper for that same verse number — so instead of
// reimplementing the grouping, this pass detects that exact shape and
// moves the stranded mark forward into the following wrapper, deleting
// the now-empty one. This is real content correction, not a heuristic
// guess — confirmed to reproduce real Proskomma output byte-for-byte on
// every case found in a full 1,189-chapter BSB corpus run (2026-09-19).
function fixStrandedVerseLabels(blocks) {
  const paragraphIdx = blocks
    .map((b, i) => ({ b, i }))
    .filter(({ b }) => b.type === 'paragraph')
    .map(({ i }) => i);

  for (let k = 0; k < paragraphIdx.length - 1; k++) {
    const curr = blocks[paragraphIdx[k]];
    const next = blocks[paragraphIdx[k + 1]];
    const currWrapper = curr.content[0]; // the "chapter" wrapper
    const nextWrapper = next.content[0];
    if (!currWrapper || currWrapper.subtype !== 'chapter') continue;
    if (!nextWrapper || nextWrapper.subtype !== 'chapter') continue;

    const currInner = currWrapper.content;
    const last = currInner[currInner.length - 1];
    if (!last || last.type !== 'wrapper' || last.subtype !== 'verses') continue;
    if (last.content.length !== 1 || last.content[0].type !== 'mark') continue;

    const nextFirst = nextWrapper.content[0];
    if (!nextFirst || nextFirst.type !== 'wrapper' || nextFirst.subtype !== 'verses') continue;
    if (nextFirst.atts.number !== last.atts.number) continue;

    nextFirst.content.unshift(last.content[0]);
    currInner.pop();
  }

  // A paragraph block can end up holding NOTHING but bare "mark" items
  // (chapter_label and/or, after the migration above, nothing at all) —
  // e.g. a chapter's very first USJ paragraph, created solely to carry
  // verse 1's own marker node, whose real poetry text lands in the NEXT
  // usj paragraph (a poem-level change right at the chapter's first
  // verse). Confirmed directly (BSB Ecclesiastes 3:1): real Proskomma
  // doesn't leave a scaffolding-only block behind — it merges ALL of the
  // block's marks (in order) onto the FRONT of the next paragraph
  // block's chapter-wrapper content, and drops the block entirely. This
  // also correctly covers the simpler "genuinely empty" case (an empty
  // mark list is trivially "every item is a mark"). A real "\b"
  // blank-line paragraph is exempt — its legitimately empty content IS
  // kept as its own block in real output.
  for (let i = blocks.length - 1; i >= 0; i--) {
    const block = blocks[i];
    if (block.type !== 'paragraph' || block.subtype === 'usfm:b') continue;
    const wrapper = block.content[0];
    if (!wrapper || wrapper.subtype !== 'chapter') continue;
    if (!wrapper.content.every(item => item && item.type === 'mark')) continue;

    let j = i + 1;
    while (j < blocks.length && blocks[j].type !== 'paragraph') j++;
    if (j >= blocks.length) continue; // nothing to merge into — leave as a safe fallback

    const nextWrapper = blocks[j].content[0];
    if (!nextWrapper || nextWrapper.subtype !== 'chapter') continue;

    nextWrapper.content.unshift(...wrapper.content);
    blocks.splice(i, 1);
  }
}

/**
 * One chapter-level USJ document (as produced by
 * helloao_to_usj.mjs#chapterToUsj) -> real Sofria JSON, hand-built with
 * no proskomma-core dependency. `translation` supplies the `{lang, abbr}`
 * pair Sofria's metadata.translation.selectors expects (any stable
 * string pair is fine — it only needs to be consistent, not registered
 * anywhere).
 */
export function usjChapterToSofriaNative(usj, translation) {
  const bookNode = usj.content.find(n => n && n.type === 'book');
  const chapterNode = usj.content.find(n => n && n.type === 'chapter');
  const bookCode = bookNode ? bookNode.code : 'XXX';
  const chapterNumber = chapterNode ? chapterNode.number : null;

  const docState = {
    chapterNumber,
    chapterLabelEmitted: false,
    verseLabelEmitted: new Set(),
    currentVerseNumber: null,
  };

  const blocks = [];
  for (const node of usj.content) {
    if (!node || typeof node !== 'object') continue;
    if (node.type === 'book' || node.type === 'chapter') continue;
    if (node.type !== 'para') continue;

    if (node.marker === 's1') {
      // Detached heading graft — not wrapped in chapter/verses at all
      // (confirmed directly: real Sofria positions a heading as its own
      // top-level "heading" sequence graft, separate from the
      // chapter-wrapper scaffolding the surrounding paragraphs use).
      blocks.push({
        type: 'graft',
        sequence: {
          type: 'heading',
          blocks: [{ type: 'paragraph', subtype: 'usfm:s', content: [...node.content] }],
        },
      });
      continue;
    }

    const chapterWrapperContent = buildChapterWrapperContent(node.content, docState);
    blocks.push({
      type: 'paragraph',
      subtype: `usfm:${canonicalMarker(node.marker)}`,
      content: [
        { type: 'wrapper', subtype: 'chapter', content: chapterWrapperContent, atts: { number: String(chapterNumber) } },
      ],
    });
  }

  fixStrandedVerseLabels(blocks);

  return {
    schema: {
      structure: 'nested',
      structure_version: '0.2.1',
      constraints: [{ name: 'sofria', version: '0.2.1' }],
    },
    metadata: {
      translation: {
        id: `${translation.lang}_${translation.abbr}`,
        selectors: { lang: translation.lang, abbr: translation.abbr },
        properties: {},
        tags: [],
      },
      document: {
        id: bookCode,
        bookCode,
        properties: { chapters: String(chapterNumber) },
        tags: [],
      },
    },
    sequence: { type: 'main', blocks },
  };
}
