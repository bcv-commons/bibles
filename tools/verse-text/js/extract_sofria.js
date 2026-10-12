// Verse text from one Sofria chapter document, by the rule in rule.js.
//   extractSofria(doc) -> [{ verse, text }, ...]
import { HEADING, SKIP_CHAR, SKIP_PARA, collector } from './rule.js';

const usfm = (subtype) => (subtype && subtype.startsWith('usfm:') ? subtype.slice(5) : subtype || '');
const one = (v) => (Array.isArray(v) ? v[0] : v);
// block grafts that hold no verse text
const SKIP_GRAFT = new Set(['heading', 'title', 'introduction', 'end_title', 'remark', 'fig', 'footnote', 'xref', 'note_caller']);

export function extractSofria(doc) {
    const out = collector();
    const st = { verse: null, seen: new Set(), chapter: null };

    const setVerse = (number, label) => {
        const key = String(one(number));
        const first = key.split(/[-,]/)[0].trim();
        if (label && st.verse !== key && st.seen.has(first)) out.restart(key);
        st.verse = key;
        st.seen.add(first);
    };

    const inline = (items, ctx) => {
        for (const it of items || []) {
            if (typeof it === 'string') {
                if (!ctx.heading || ctx.verseHere) out.add(st.verse, it);
                continue;
            }
            if (!it || typeof it !== 'object') continue;
            if (it.type === 'mark') {
                if (it.subtype === 'verses_label') {
                    setVerse(it.atts?.number, true);
                    ctx.verseHere = true;
                }
                continue; // other marks (chapter label, \vp, \va, \ca) carry no text
            }
            if (it.type === 'graft' || it.type === 'start_milestone' || it.type === 'end_milestone') continue;
            if (it.type === 'wrapper') {
                if (it.subtype === 'chapter') {
                    // the next chapter's label (and anything on it) can close this document
                    const n = String(one(it.atts?.number));
                    if (st.chapter == null) st.chapter = n;
                    if (n !== st.chapter) continue;
                }
                if (it.subtype === 'verses' && it.atts?.number != null && st.verse == null) setVerse(it.atts.number, false);
                if (SKIP_CHAR.has(usfm(it.subtype))) continue;
                // a table cell is a word boundary on both sides (when a verse starts in a
                // cell, the importer leaves that cell's wrapper empty and puts its text
                // beside it, so only the next cell's start marks the boundary)
                if (it.subtype === 'cell') out.add(st.verse, ' ');
                inline(it.content, ctx);
                if (it.subtype === 'cell') out.add(st.verse, ' ');
            }
        }
    };

    const blocks = (list) => {
        for (const b of list || []) {
            if (b.type === 'graft') {
                const kind = b.sequence?.type || b.subtype || '';
                if (!SKIP_GRAFT.has(kind)) blocks(b.sequence?.blocks);
                continue;
            }
            if (b.type === 'row') {
                for (const cell of b.content || []) {
                    inline([cell], { heading: false, verseHere: false });
                    out.add(st.verse, ' ');
                }
                continue;
            }
            const marker = usfm(b.subtype);
            if (SKIP_PARA.test(marker)) continue;
            inline(b.content, { heading: HEADING.test(marker), verseHere: false });
            out.add(st.verse, ' ');
        }
    };

    blocks(doc.sequence?.blocks);
    return out.result();
}
