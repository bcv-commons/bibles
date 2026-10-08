/**
 * The no-drop check: every text string in a Sofria document must appear, in
 * order, in the text of the rendered HTML. Exempt by design: Proskomma's
 * placeholders (`NO_CAPTION`, the `| default=""` artifact) and note callers
 * ('+'/'-' are instructions, replaced by the caller actually shown).
 */
export function inputStrings(doc) {
    const out = [];
    const walkContent = (items, inCaller) => {
        for (const it of items || []) {
            if (typeof it === 'string') {
                if (!inCaller && it !== 'NO_CAPTION' && it !== '| default=""') out.push(it);
                continue;
            }
            if (!it || typeof it !== 'object') continue;
            const caller = inCaller || it.subtype === 'note_caller';
            walkContent(it.content, caller);
            walkContent(it.meta_content, caller);
            if (it.sequence) walkBlocks(it.sequence.blocks, caller);
        }
    };
    const walkBlocks = (blocks, inCaller) => {
        for (const b of blocks || []) {
            walkContent(b.content, inCaller);
            if (b.sequence) walkBlocks(b.sequence.blocks, inCaller || b.sequence.type === 'note_caller');
        }
    };
    walkBlocks(doc.sequence?.blocks);
    return out;
}

const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'", nbsp: ' ' };
export function outputText(html) {
    return html
        .replace(/<[^>]*>/g, ' ')
        .replace(/&(amp|lt|gt|quot|#39|nbsp);/g, (_, e) => ENT[e]);
}

const norm = (s) => s.replace(/\s+/g, ' ').trim();

/** Returns the input strings not found (in order) in the output. Empty = pass. */
export function missingStrings(doc, html) {
    const text = norm(outputText(html));
    const missing = [];
    let pos = 0;
    for (const s of inputStrings(doc)) {
        const n = norm(s);
        if (!n) continue;
        const at = text.indexOf(n, pos);
        if (at === -1) {
            // not found after the previous match: fall back to anywhere (order can differ, e.g. notes collected at the end)
            if (text.indexOf(n) === -1) missing.push(s);
        } else pos = at + n.length;
    }
    return missing;
}

const NUMBER_MARKS = new Set(['verses_label', 'pub_verse', 'chapter_label', 'pub_chapter', 'alt_verse', 'alt_chapter']);

/** Numbers carried in marks (verse, chapter, published, alternate) must also be in the output. */
export function missingNumbers(doc, html) {
    const nums = [];
    const walk = (items) => {
        for (const it of items || []) {
            if (!it || typeof it !== 'object') continue;
            if (it.type === 'mark' && NUMBER_MARKS.has(it.subtype)) {
                const n = Array.isArray(it.atts?.number) ? it.atts.number[0] : it.atts?.number;
                if (n != null) nums.push(`${it.subtype}:${n}`);
            }
            walk(it.content);
            if (it.sequence) for (const b of it.sequence.blocks || []) walk(b.content);
        }
    };
    for (const b of doc.sequence?.blocks || []) {
        walk(b.content);
        if (b.sequence) for (const x of b.sequence.blocks || []) walk(x.content);
    }
    // shown as text, or kept as the canonical number in data-verse / data-v / data-c
    // (with a `numerals` option the visible digits differ; the data attribute does not)
    const text = outputText(html);
    const attrs = new Set([...html.matchAll(/data-(?:verse|v|c)="([^"]*)"/g)].map((m) => m[1]));
    return nums.filter((k) => {
        const n = k.split(':')[1];
        if (attrs.has(n)) return false;
        return !new RegExp(`(^|[^0-9])${n.replace(/[-]/g, '\\-')}([^0-9]|$)`).test(text);
    });
}
