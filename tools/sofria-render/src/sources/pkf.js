/**
 * PKF source: load a .pkf file (gzip-compressed Proskomma succinct docSet, as
 * published at cdn.bibel.wiki/pkf/<iso>/) and get Sofria per chapter.
 *
 * Chapter 1 also carries the book's title and introduction grafts.
 *
 *   const pkf = loadPkf(bytes);             // Uint8Array of the .pkf file
 *   pkf.books                                // ['MAT', 'MRK', ...]
 *   pkf.chapters('MAT')                      // [1, 2, ...]
 *   const doc = pkf.sofria('MAT', 5);        // Sofria JSON for one chapter
 *
 * Works in Node and in the browser (no fs access here).
 */
import { decompressSync, strFromU8 } from 'fflate';
import { Proskomma } from 'proskomma-core';

class PkfProskomma extends Proskomma {
    constructor() {
        super();
        // PKF docSets are selected by lang + abbr (same as SAB's sab-proskomma)
        this.selectors = [
            { name: 'lang', type: 'string', regex: '^[A-Za-z0-9-]{2,30}$' },
            { name: 'abbr', type: 'string', regex: '^[A-Za-z0-9 -]+$' }
        ];
        this.validateSelectors();
    }
}

export function loadPkf(bytes) {
    const pk = new PkfProskomma();
    pk.loadSuccinctDocSet(JSON.parse(strFromU8(decompressSync(bytes))));
    const docSetId = pk.gqlQuerySync('{docSets{id}}').data.docSets[0].id;
    const docs = pk.gqlQuerySync(
        `{docSet(id:"${docSetId}"){documents{bookCode:header(id:"bookCode") cvIndexes{chapter}}}}`
    ).data.docSet.documents;
    const chaptersByBook = Object.fromEntries(docs.map((d) => [d.bookCode, d.cvIndexes.map((c) => c.chapter)]));
    const safe = /^[0-9A-Z]{3}$/;
    const bookCache = new Map();
    const bookSofria = (book) => {
        if (!bookCache.has(book)) {
            const raw = pk.gqlQuerySync(`{docSet(id:"${docSetId}"){document(bookCode:"${book}"){sofria}}}`).data?.docSet?.document?.sofria;
            if (!raw) throw new Error(`no Sofria for ${book}`);
            bookCache.clear(); // keep one book: whole-book Sofria can be large
            bookCache.set(book, JSON.parse(raw));
        }
        return bookCache.get(book);
    };
    return {
        docSetId,
        books: docs.map((d) => d.bookCode),
        chapters: (book) => chaptersByBook[book] || [],
        sofria(book, chapter) {
            if (!safe.test(book) || !Number.isInteger(chapter)) throw new Error(`bad reference ${book} ${chapter}`);
            let raw = null;
            try {
                raw = pk.gqlQuerySync(`{docSet(id:"${docSetId}"){document(bookCode:"${book}"){sofria(chapter:${chapter})}}}`)
                    .data?.docSet?.document?.sofria;
            } catch {
                raw = null;
            }
            if (raw) return JSON.parse(raw);
            // proskomma-core's chapter-level sofria() fails on some real content (e.g. a
            // table running across a chapter break); the whole-book query still works,
            // so cut the chapter out of that. The result is marked `fallback`.
            const doc = sliceChapter(bookSofria(book), chapter);
            if (!doc.sequence.blocks.length) throw new Error(`no Sofria for ${book} ${chapter}`);
            doc.fallback = 'whole-book';
            return doc;
        },
        proskomma: pk
    };
}

/**
 * A language's stylesheets, in load order: SAB's shared scripture sheet, then the
 * language's own delta.css (fonts, size, direction, Normal/Sepia/Dark colours).
 * Both are named in info.json (style_shared, style_delta, relative to the language
 * folder). The page's #container needs data-iso="<iso>" and data-color-theme.
 * Mirrors without these fields fall back to the raw SAB files listed as assets.
 */
function stylesheetsFor(iso, info, base) {
    const dir = new URL(`${iso}/`, base);
    if (info.style_shared && info.style_delta) {
        return [new URL(info.style_shared, dir).href, new URL(info.style_delta, dir).href];
    }
    return (info.assets || []).filter((a) => a.kind === 'css').map((a) => new URL(`styles/raw/${a.name}`, dir).href);
}

/**
 * Cut one chapter out of a whole-book Sofria document, matching what
 * sofria(chapter: N) returns: a block's top-level `chapter` wrappers say which
 * chapter its content belongs to; a block's other top-level items go with the
 * chapter last seen. Grafts between blocks (headings) go with the chapter of the
 * next block that has content; grafts before chapter 1 (title, introduction)
 * go with chapter 1.
 */
export function sliceChapter(bookDoc, chapter) {
    const want = String(chapter);
    const blocks = bookDoc.sequence?.blocks || [];
    const out = [];
    let pending = [];
    let current = null; // chapter of the content seen so far
    for (const b of blocks) {
        if (b.type === 'graft') {
            pending.push(b);
            continue;
        }
        const kept = [];
        let firstChapter = null;
        for (const item of b.content || []) {
            if (item && item.type === 'wrapper' && item.subtype === 'chapter') {
                current = String(Array.isArray(item.atts?.number) ? item.atts.number[0] : item.atts?.number);
                if (firstChapter == null) firstChapter = current;
            }
            if ((current ?? '1') === want) kept.push(item);
        }
        const graftChapter = firstChapter ?? current ?? '1';
        if (graftChapter === want) out.push(...pending);
        pending = [];
        if (kept.length) out.push({ ...b, content: kept });
    }
    if ((current ?? '1') === want) out.push(...pending); // trailing grafts
    return { ...bookDoc, sequence: { ...bookDoc.sequence, blocks: out } };
}

/**
 * Find a PKF language's files on the CDN: the .pkf collections (from
 * pkf/manifest.json, or the language's own info.json), its stylesheets (see
 * stylesheetsFor), and its SAB settings (pkf/<iso>/app-config.json; see
 * optionsFromAppConfig).
 */
export async function pkfLanguage(iso, base = 'https://cdn.bibel.wiki/pkf/') {
    if (!/^[a-z]{2,3}[a-z0-9-]*$/.test(iso)) throw new Error(`bad iso ${iso}`);
    const [manifest, info, appConfig] = await Promise.all([
        fetch(`${base}manifest.json`).then((r) => r.json()),
        fetch(`${base}${iso}/info.json`).then((r) => (r.ok ? r.json() : { assets: [] })),
        fetch(`${base}${iso}/app-config.json`).then((r) => (r.ok ? r.json() : {}))
    ]);
    // The manifest is the index; each language's own info.json also lists its .pkf
    // files, so a language missing from the manifest can still be loaded.
    const entry = manifest.languages?.[iso];
    const fromInfo = (info.assets || []).filter((a) => a.kind === 'pkf').map((a) => ({ pkf: a.name, pkf_bytes: a.size }));
    const collections = entry?.collections?.length ? entry.collections : fromInfo;
    if (!collections.length) throw new Error(`no PKF language ${iso}`);
    return {
        name: entry?.nm || iso,
        collections: collections.map((c) => ({ ...c, url: `${base}${iso}/${c.pkf}` })),
        stylesheets: stylesheetsFor(iso, info, base),
        appConfig
    };
}

// SAB numeral-system names -> digits 0..9. Every PKF language currently uses "Default".
const NUMERALS = {
    arabic: '٠١٢٣٤٥٦٧٨٩', 'arabic-indic': '٠١٢٣٤٥٦٧٨٩', persian: '۰۱۲۳۴۵۶۷۸۹', urdu: '۰۱۲۳۴۵۶۷۸۹',
    devanagari: '०१२३४५६७८९', bengali: '০১২৩৪৫৬৭৮৯', gurmukhi: '੦੧੨੩੪੫੬੭੮੯', gujarati: '૦૧૨૩૪૫૬૭૮૯',
    oriya: '୦୧୨୩୪୫୬୭୮୯', tamil: '௦௧௨௩௪௫௬௭௮௯', telugu: '౦౧౨౩౪౫౬౭౮౯', kannada: '೦೧೨೩೪೫೬೭೮೯',
    malayalam: '൦൧൨൩൪൫൬൭൮൯', thai: '๐๑๒๓๔๕๖๗๘๙', lao: '໐໑໒໓໔໕໖໗໘໙', tibetan: '༠༡༢༣༤༥༦༧༨༩',
    myanmar: '၀၁၂၃၄၅၆၇၈၉', khmer: '០១២៣៤៥៦៧៨៩'
};

/**
 * Renderer options from a PKF language's app-config.json (SAB's own settings), so
 * each language renders the way its publisher configured it. Returns
 * { options, warnings }.
 */
export function optionsFromAppConfig(cfg = {}) {
    const f = cfg.features || {};
    const warnings = [];
    const options = {
        direction: cfg.collection?.textDirection || 'ltr',
        chapterNumber: f['show-chapter-numbers'] === false ? 'none' : f['chapter-number-format'] === 'top' ? 'top' : 'drop-cap',
        hideVerseNumberOne: f['hide-verse-number-1'] === true,
        showVerseNumbers: f['show-verse-numbers'] !== false,
        wordsOfJesus: f['show-red-letters'] === true,
        glossaryLinks: f['show-glossary-words'] !== false,
        showNotes: f['show-footnotes'] !== false,
        showImages: f['show-illustrations'] !== false && f['display-images-in-bible-text'] !== 'hidden',
        showVideos: f['display-videos-in-bible-text'] !== 'hidden',
        verseLayout: f['verse-layout'] === 'one-per-line' ? 'one-per-line' : 'paragraphs',
        verseRangeSeparator: f['ref-verse-range-separator'] || '-',
        callers: {
            footnote: { type: f['footnote-caller-type'] || 'default', symbol: f['footnote-caller-symbol'] || '', noCallerToAuto: f['footnote-caller-no-caller-to-auto'] !== false },
            xref: { type: f['crossref-caller-type'] || 'default', symbol: f['crossref-caller-symbol'] || '', noCallerToAuto: f['crossref-caller-no-caller-to-auto'] !== false }
        }
    };
    const nt = String(f['numerals-type'] || 'default').toLowerCase();
    if (nt !== 'default') {
        if (NUMERALS[nt]) options.numerals = NUMERALS[nt];
        else warnings.push(`numerals-type "${f['numerals-type']}" not known; Western digits used`);
    }
    return { options, warnings };
}
