// Real proskomma-core@0.11.3's USJ importer has no handler for USJ
// "table" nodes at all ("USJ walker found no openTag handler for
// table:row") — and since import is atomic, this fails the WHOLE
// document, not just the table (confirmed directly: 38 real openbible
// books — Ezra/Nehemiah/Joshua/1 Chronicles/1 Esdras/Numbers/Mark
// editions carrying a real USFM \tr/\tc table, e.g. Ezra 1's temple-
// vessel inventory — had zero Sofria output at all, not a version
// missing just the table).
//
// Confirmed safe to strip: real USJ tables in this corpus carry no
// "verse" nodes of their own (checked directly) — they're supplementary
// block-level content sitting between verses, not verse-tagged content —
// so removing a table node loses only the table's own data, with no
// verse-numbering gap or other content casualty elsewhere in the book.
// stripTables() removes every "table"-type node found anywhere in a USJ
// content tree (recursive, not just top-level, in case a future source
// ever nests one) and returns both the cleaned USJ and a count of tables
// removed, so callers can log/flag which books were affected rather than
// silently degrading them.
export function stripTables(usj) {
  let removed = 0;
  function walk(node) {
    if (Array.isArray(node)) {
      for (let i = node.length - 1; i >= 0; i--) {
        const item = node[i];
        if (item && typeof item === 'object' && item.type === 'table') {
          node.splice(i, 1);
          removed++;
          continue;
        }
        walk(item);
      }
    } else if (node && typeof node === 'object') {
      for (const v of Object.values(node)) walk(v);
    }
  }
  const cleaned = JSON.parse(JSON.stringify(usj));
  walk(cleaned.content);
  return { usj: cleaned, tablesRemoved: removed };
}
