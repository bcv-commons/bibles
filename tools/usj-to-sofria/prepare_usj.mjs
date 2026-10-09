// Prepares a book's USJ for proskomma-core@0.11.3's USJ importer. Each step works
// around one importer behaviour; none removes text.
//
// 1. Figures. The importer nests everything that follows an inline \fig inside the
//    figure's graft. Each figure goes in a paragraph of its own, split out of its host
//    paragraph. A figure in the introduction is moved to the end of the introduction:
//    there the importer nests the following intro paragraphs into it even when the
//    figure has a paragraph of its own.
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

export function prepareUsj(usj) {
  let content = splitFigures(usj.content || []);
  content = dropDuplicateCp(content);
  content = content.filter((n) => !(n && n.type === 'table' && !hasText(n)));
  content = walk(content);
  return { ...usj, content };
}

function walk(x) {
  if (Array.isArray(x)) return x.filter((n) => !(n && n.type === 'optbreak')).map(walk);
  if (x && typeof x === 'object') {
    const o = { ...x };
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
      let cur = { ...node, content: [] };
      for (const c of node.content) {
        if (c && c.type === 'figure') {
          if (cur.content.length) out.push(cur);
          const own = { ...node, content: [c] };
          if (isIntro(node)) introFigs.push(own); else out.push(own);
          cur = { ...node, content: [] };
        } else {
          cur.content.push(c);
        }
      }
      if (cur.content.length) out.push(cur);
    } else {
      out.push(node);
    }
  }
  flushIntro();
  return out;
}
