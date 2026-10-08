// Tiny builders for hand-made Sofria fixtures (synthetic text only).
export const doc = (...blocks) => ({ sequence: { type: 'main', blocks } });
export const para = (marker, ...content) => ({ type: 'paragraph', subtype: `usfm:${marker}`, content });
export const graft = (type, ...blocks) => ({ type: 'graft', sequence: { type, blocks } });
export const v = (n) => ({ type: 'mark', subtype: 'verses_label', atts: { number: String(n) } });
export const c = (n) => ({ type: 'mark', subtype: 'chapter_label', atts: { number: String(n) } });
export const mark = (subtype, n) => ({ type: 'mark', subtype, atts: { number: String(n) } });
export const w = (subtype, content, atts) => ({ type: 'wrapper', subtype, content, ...(atts ? { atts } : {}) });
export const verses = (n, ...content) => w('verses', content, { number: String(n) });
export const chapter = (n, ...content) => w('chapter', content, { number: String(n) });
export const note = (kind, caller, ...content) => ({
    type: 'graft',
    subtype: kind,
    sequence: {
        type: kind,
        blocks: [
            {
                type: 'paragraph',
                subtype: kind === 'xref' ? 'usfm:x' : 'usfm:f',
                content: [
                    { type: 'graft', subtype: 'note_caller', sequence: { type: 'note_caller', blocks: [{ type: 'paragraph', subtype: 'usfm:f', content: [caller] }] } },
                    ' ',
                    ...content
                ]
            }
        ]
    }
});
export const ms = (subtype, atts) => ({ type: 'start_milestone', subtype: `usfm:${subtype}`, atts });
export const me = (subtype) => ({ type: 'end_milestone', subtype: `usfm:${subtype}` });
export const row = (...cells) => ({ type: 'row', subtype: 'usfm:tr', content: cells });
export const cell = (text, role = 'body', nCols = 1, alignment = 'start') => w('cell', [text], { role, nCols, alignment });
