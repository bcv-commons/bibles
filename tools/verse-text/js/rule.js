// The verse-text rule, shared by the USJ and Sofria extractors (agreed with
// lexeme-aligner, 2026-10-12):
//
// - Verse text is the text after a verse number, up to the next verse number,
//   across paragraphs (poetry lines, table cells included).
// - Not verse text: footnotes and cross-references; headings (\s \ms \mr \r \sr \sp
//   \cl \qa \mt \d ...), up to a verse number inside the heading paragraph: text after
//   that number is the verse's text (a \d numbered psalm title; a source that left out
//   the paragraph marker after a heading, bcv LUK 9:51); introductions; figures;
//   remarks (\rem, and Paratext's \restore metadata); \rq (quotation source); \qac (acrostic letter); \fm (footnote
//   mark); \vp and \va/\ca (published or alternative numbers).
// - Word-level markup (\w, \wj, \nd, ...) contributes its text, never attributes. Inside
//   \w, text from a `|` on is an attribute the source failed to parse (USX
//   <char style="w">word|lemma</char>, DBT HLBMSS / YBBCAB): it is dropped.
// - `| default="X"` (proskomma's rendering of a `|` in text, found in DBT's own Sofria,
//   CARBSS) reads as `|X`, the source text. Any other `|` is text (a Sanskrit danda, LSV).
// - A bridged verse 4-5 is one verse, under its first number (4).
// - A verse number given twice: both texts, in document order, joined by one space.
// - A verse with no text of its own is skipped.
// - Whitespace: runs collapsed to one space, trimmed.

export const HEADING = /^(s\d*|ms\d*|mr|r|sr|sp|cl|qa|mt\d*|mte\d*|cd|d)$/;
export const SKIP_CHAR = new Set(['rq', 'qac', 'fm', 'vp', 'va', 'ca', 'fig']);
export const SKIP_PARA = /^(rem|restore|cp|ide|h\d*|toc\d*|toca\d*|i\w+)$/;

export const firstNumber = (v) => String(v).trim().split(/[-,‐-―]/)[0].trim();
export const PROSKOMMA_PIPE = /\| default="([^"]*)"/g;
export const clean = (s) => s.replace(PROSKOMMA_PIPE, '|$1').replace(/\s+/g, ' ').trim();

/** A \w's content up to its first `|` (the rest is an unparsed attribute). */
export function wordBeforePipe(items) {
    const out = [];
    for (const it of items || []) {
        if (typeof it === 'string' && it.includes('|')) {
            out.push(it.slice(0, it.indexOf('|')));
            break;
        }
        out.push(it);
    }
    return out;
}

/** Collects text per verse: add(verse, text); result() -> [{verse, text}] in order. */
export function collector() {
    const order = [];
    const text = new Map();
    return {
        add(verse, s) {
            if (verse == null) return;
            const key = firstNumber(verse);
            if (!text.has(key)) {
                text.set(key, []);
                order.push(key);
            }
            text.get(key).push(s);
        },
        // a verse number seen again later (not continuing): start a new piece, joined by a space
        restart(verse) {
            const key = firstNumber(verse);
            if (text.has(key)) text.get(key).push(' ');
        },
        result() {
            return order
                .map((v) => ({ verse: v, text: clean(text.get(v).join('')) }))
                .filter((x) => x.text !== '');
        }
    };
}
