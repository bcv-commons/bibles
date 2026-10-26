// Prepares a book's USJ for proskomma-core@0.11.3's USJ importer. Each step works
// around one importer behaviour; none removes text.
//
// 1. Figures. The importer nests everything that follows an inline \fig inside the
//    figure's graft. Each figure goes in a paragraph of its own, placed right after its
//    host paragraph, which keeps its text whole. (Splitting the host paragraph at the
//    figure put a line break into the text, sometimes mid-word: kde MAT 25:14 "Y esu".)
//    A figure in the introduction is moved to the end of the introduction: there the
//    importer nests the following intro paragraphs into it even when the figure has a
//    paragraph of its own.
// 2. Tables. USJ names table rows and cells "table:row" / "table:cell"; the importer's
//    handlers are named "row" / "cell", so without renaming it fails the whole book
//    ("no openTag handler for table:row"). Renamed, tables import as Sofria rows.
//    A table with no text at all (an empty `\tr \tc1`) is removed: the importer leaves
//    an empty row open across a following \c, which moves the next chapter's opening
//    verses into this chapter (glw/GLW/MRK 2).
// 3. Optional breaks. The importer writes a USJ optbreak (USFM //) into the text as a
//    literal "//". It is a typesetting hint, not text, and the words around it are
//    already separated by a space, so it is removed.
// 4. \cp. usfmtc writes a chapter's published number twice: as the chapter's
//    `pubnumber` and again as a separate \cp paragraph. The importer turns the first
//    into a pub_chapter mark and the second into loose text, which lands after the
//    previous chapter's last verse. The paragraph is removed only when it repeats the
//    pubnumber exactly.
// 5. `|` in text. The importer reads a `|` inside text as the start of attributes and
//    writes `| default=""` into the output (SANHK 1CO 1:2 "likhati|" -> "likhati|
//    default=\"\""). A `|` in a USJ string is always text (USJ keeps attributes as
//    fields), so it is swapped for PIPE_PLACEHOLDER here and put back in the Sofria
//    output by restorePipes().
// 6. A verse number inside a heading paragraph (\s \v 51 text..., a missing paragraph
//    marker in the source). The importer turns the whole paragraph into a heading, so
//    the verse loses its text (bcv LUK 9:51). The paragraph is split at the verse
//    number: the text before stays a heading, the verse and its text become a \p.
//    (\d is left as it is: a \d holding a verse number is a numbered psalm title.)
// 7. \restore paragraphs (Paratext backup metadata, e.g. "01-Sep-2009@09:54, Backup
//    Description=..."). The importer doesn't know the marker and merges its text into
//    the last verse before it (hwo LUK 24:53). It becomes a \rem: kept, but a remark.
// 8. An empty paragraph right before a \c (frasbl SIR 20, after an empty \v 32). The
//    importer keeps the paragraph before it open across the chapter, so the next
//    chapter's first line lands in this chapter's file (frasbl SIR 21:1 "Mon fils, as-tu
//    péché ?"). The empty paragraph has no text and is removed.
// 9. Long runs of letters. The importer cuts a run of letters into words of at most 127
//    characters and then truncates any word over 255 bytes, so text written without
//    spaces loses letters: 127 Thai letters are 381 bytes (thafb 1KI 15:24, EZR 3:5).
//    Every run of 64 letters or more gets BREAK_PLACEHOLDER after each 60 characters,
//    which ends a word for the importer (it is neither a letter nor a separator), and
//    restorePipes() removes it from the Sofria output: 60 characters of up to 4 bytes
//    stay under 255.

export function prepareUsj(usj) {
  let content = splitFigures(usj.content || []);
  content = content.filter((n, i) => !(n && n.type === 'para' && !hasText(n) && !(n.content || []).length
    && content[i + 1]?.type === 'chapter'));
  content = splitHeadingAtVerse(content);
  content = dropDuplicateCp(content);
  content = content.filter((n) => !(n && n.type === 'table' && !hasText(n)));
  content = walk(content);
  return { ...usj, content };
}

export const PIPE_PLACEHOLDER = '\uE000';
export const BREAK_PLACEHOLDER = '\uE001';
const LONG_RUN = /[\p{L}\p{N}\p{M}\u2060]{64,}/gu;

/** Put `|` back in a Sofria JSON string (after the importer), and remove the word breaks. */
export const restorePipes = (json) => json.replaceAll(PIPE_PLACEHOLDER, '|').replaceAll(BREAK_PLACEHOLDER, '');

// The chapter as published: placeholders restored, and metadata.translation dropped. Proskomma
// needs a lang and abbr to import a document and writes them there, but ours are placeholders
// (lang 'xx'; DBT's own Sofria has 'xxx') that no reader uses: the language and edition are in
// the path and in _meta.json. Dropped from 2026-10-26; files converted before keep it.
export function finishSofria(json) {
  const doc = JSON.parse(restorePipes(json));
  if (doc.metadata) delete doc.metadata.translation;
  return JSON.stringify(doc);
}

const breakLongRuns = (s) => s.replace(LONG_RUN, (run) => {
  const chars = [...run];
  const parts = [];
  for (let i = 0; i < chars.length; i += 60) parts.push(chars.slice(i, i + 60).join(''));
  return parts.join(BREAK_PLACEHOLDER);
});

function walk(x) {
  if (typeof x === 'string') return breakLongRuns(x.replaceAll('|', PIPE_PLACEHOLDER));
  if (Array.isArray(x)) return x.filter((n) => !(n && n.type === 'optbreak')).map(walk);
  if (x && typeof x === 'object') {
    const o = { ...x };
    if (o.type === 'para' && o.marker === 'restore') o.marker = 'rem';
    if (o.type === 'table:row') o.type = 'row';
    else if (o.type === 'table:cell') o.type = 'cell';
    if (o.content) o.content = walk(o.content);
    return o;
  }
  return x;
}

const hasText = (n) => (typeof n === 'string' ? n.trim() !== '' : (n?.content || []).some(hasText));
const textOf = (n) => (n.content || []).filter((c) => typeof c === 'string').join('').trim();

function dropDuplicateCp(content) {
  return content.filter((n, i) => {
    if (!(n && n.type === 'para' && n.marker === 'cp')) return true;
    const prev = content[i - 1];
    return !(prev && prev.type === 'chapter' && prev.pubnumber && prev.pubnumber.trim() === textOf(n));
  });
}

function splitFigures(content) {
  const out = [];
  let introFigs = [];
  const isIntro = (n) => n && n.type === 'para' && /^i/.test(n.marker || '');
  const flushIntro = () => { out.push(...introFigs); introFigs = []; };
  for (const node of content) {
    if (!isIntro(node) && introFigs.length) flushIntro();
    if (node && node.type === 'para' && (node.content || []).some((c) => c && c.type === 'figure')) {
      const figures = node.content.filter((c) => c && c.type === 'figure').map((c) => ({ ...node, content: [c] }));
      const rest = node.content.filter((c) => !(c && c.type === 'figure'));
      if (rest.length) out.push({ ...node, content: rest });
      if (isIntro(node)) introFigs.push(...figures); else out.push(...figures);
    } else {
      out.push(node);
    }
  }
  flushIntro();
  return out;
}

const HEADING_SPLIT = /^(s\d*|ms\d*|mr|r|sr|sp|qa|cl)$/;

function splitHeadingAtVerse(content) {
  const out = [];
  for (const node of content) {
    const at = node && node.type === 'para' && HEADING_SPLIT.test(node.marker || '')
      ? (node.content || []).findIndex((c) => c && c.type === 'verse') : -1;
    if (at === -1) {
      out.push(node);
      continue;
    }
    const head = node.content.slice(0, at);
    if (head.some(hasText)) out.push({ ...node, content: head });
    out.push({ type: 'para', marker: 'p', content: node.content.slice(at) });
  }
  return out;
}
