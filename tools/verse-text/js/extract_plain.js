// Verse text from plain verse JSON (DBT's text_plain filesets): the reading rule for the
// plain-text route, used only where an edition has no structured text (no Sofria, no USX).
// Not a conversion: the result is the same list of verses the other extractors give.
//
//   extractPlain(items) -> [{ verse, text }, ...]
//   items: DBT's per-chapter `data`, [{ verse_start, verse_end, verse_text, ... }, ...]
//
// Rules (same as ../python/plain_text.py):
// - A verse is keyed by its first number (verse_start; a bridged 4-5 is verse 4). Several
//   items with the same first number are joined by one space, in order.
// - `~` is USFM's no-break space and a literal `//` USFM's optional line break: both read
//   as a space.
// - Then clean() from rule.js; a verse with no text is left out.
import { collector } from './rule.js';

export function extractPlain(items) {
    const out = collector();
    for (const it of items || []) {
        if (it.verse_start == null) continue;
        const text = String(it.verse_text ?? '').replaceAll('~', ' ').replaceAll('//', ' ');
        out.add(String(it.verse_start), ' ' + text + ' ');
    }
    return out.result();
}
