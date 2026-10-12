// Verse text from a book's USJ, by the rule in rule.js.
//   extractUsj(usj) -> { "<chapter>": [{ verse, text }, ...], ... }
import { HEADING, SKIP_CHAR, SKIP_PARA, collector } from './rule.js';

export function extractUsj(usj) {
    const chapters = {};
    const st = { chapter: null, verse: null, out: null, seen: null };

    const setVerse = (number) => {
        const key = String(number);
        if (st.verse !== key && st.seen.has(key.split(/[-,]/)[0].trim())) st.out.restart(key);
        st.verse = key;
        st.seen.add(key.split(/[-,]/)[0].trim());
    };

    // heading: text only counts after a verse number inside the same paragraph
    const inline = (items, ctx) => {
        for (const it of items || []) {
            if (typeof it === 'string') {
                if (!ctx.heading || ctx.verseHere) st.out?.add(st.verse, it);
                continue;
            }
            if (!it || typeof it !== 'object') continue;
            switch (it.type) {
                case 'verse':
                    if (st.out) {
                        setVerse(it.number);
                        ctx.verseHere = true;
                    }
                    break;
                case 'note':
                case 'figure':
                case 'ms':
                case 'optbreak':
                    break;
                case 'char':
                    if (!SKIP_CHAR.has(it.marker)) inline(it.content, ctx);
                    break;
                default:
                    inline(it.content, ctx);
            }
        }
    };

    const block = (node) => {
        if (!node || typeof node !== 'object') return;
        if (node.type === 'chapter') {
            st.chapter = String(node.number);
            st.verse = null;
            st.out = collector();
            st.seen = new Set();
            chapters[st.chapter] = st.out;
            return;
        }
        if (!st.out) return; // before the first chapter: book title, introduction
        if (node.type === 'para') {
            const marker = node.marker || '';
            if (SKIP_PARA.test(marker)) return;
            inline(node.content, { heading: HEADING.test(marker), verseHere: false });
            st.out.add(st.verse, ' '); // a paragraph ends a line
            return;
        }
        if (node.type === 'table' || node.type === 'table:row' || node.type === 'row') {
            for (const c of node.content || []) block(c);
            return;
        }
        if (node.type === 'table:cell' || node.type === 'cell') {
            inline(node.content, { heading: false, verseHere: false });
            st.out.add(st.verse, ' ');
            return;
        }
        if (node.type === 'note' || node.type === 'figure') return;
        inline(node.content, { heading: false, verseHere: false });
    };

    for (const node of usj.content || []) block(node);
    return Object.fromEntries(Object.entries(chapters).map(([c, col]) => [c, col.result()]));
}
