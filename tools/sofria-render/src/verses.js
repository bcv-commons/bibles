/**
 * Sofria chapter -> an ordered list of typed text entries, for clients that want
 * plain text (search, alignment, audio sync) rather than HTML.
 *
 * Nothing is dropped and nothing is glued onto the wrong thing:
 *   { type: 'verse',   verse: '9', text, title?: true }
 *   { type: 'heading', marker: 'd' | 's' | 'mt' | ..., text, verse: <open verse or null> }
 *   { type: 'intro',   marker: 'ip' | ..., text }
 *   { type: 'note',    kind: 'footnote' | 'xref', caller, verse, text }
 *   { type: 'other',   marker, text }          (remarks, unknown grafts)
 *
 * The heading rule: in a heading-type paragraph (\d, \s, \ms, \mt, \r, \sp, \sr,
 * \mr, \cl, \qa) text before a verse number is a heading; text after a verse
 * number in that same paragraph is verse text (e.g. `\d \v 1 (Of David)` is
 * verse 1, marked `title: true`). \b is not a heading: its text is verse text.
 */

const HEADING = /^(d|s\d?|ms\d?|mt\d?|r|sp|sr|mr|cl|qa)$/;
const usfm = (subtype) => (subtype && subtype.startsWith('usfm:') ? subtype.slice(5) : subtype || '');
const one = (v) => (Array.isArray(v) ? v[0] : v);
const clean = (s) => s.replace(/\s+/g, ' ').trim();

export function extractEntries(doc) {
    const out = [];
    const st = { verse: null };
    walkBlocks(doc.sequence?.blocks || [], doc.sequence?.type || 'main', st, out);
    // merge consecutive pieces of the same verse
    const merged = [];
    for (const e of out) {
        const last = merged[merged.length - 1];
        if (e.type === 'verse' && last && last.type === 'verse' && last.verse === e.verse && !!last.title === !!e.title) {
            last.text = clean(last.text + ' ' + e.text);
        } else merged.push(e);
    }
    for (const e of merged) {
        if (e.type !== 'verse') continue;
        if (st.display?.[e.verse]) e.display = st.display[e.verse];
        if (st.alt?.[e.verse]) e.alt = st.alt[e.verse];
        if (st.published?.has(e.verse)) e.published = true;
    }
    // a heading introduces the verse that follows it
    let next = null;
    for (let i = merged.length - 1; i >= 0; i--) {
        if (merged[i].type === 'verse') next = merged[i].verse;
        else if (merged[i].type === 'heading') merged[i].beforeVerse = next;
    }
    return merged.filter((e) => e.text !== '' || e.type === 'verse');
}

/** Convenience: { '1': 'text', '2': '...' } — verse entries only. */
export function verseMap(entries) {
    const m = {};
    for (const e of entries) if (e.type === 'verse') m[e.verse] = m[e.verse] ? clean(m[e.verse] + ' ' + e.text) : e.text;
    return m;
}

function walkBlocks(blocks, seqType, st, out) {
    for (const b of blocks) {
        if (b.type === 'graft') {
            const seq = b.sequence || { blocks: [] };
            const kind = seq.type || b.subtype || '';
            if (kind === 'title' || kind === 'heading') {
                for (const p of seq.blocks || []) {
                    out.push({ type: 'heading', marker: usfm(p.subtype), text: textOf(p.content, st, out), verse: st.verse });
                }
            } else if (kind === 'introduction') {
                walkBlocks(seq.blocks || [], 'introduction', st, out);
            } else {
                for (const p of seq.blocks || []) out.push({ type: 'other', marker: kind, text: textOf(p.content, st, out) });
            }
            continue;
        }
        if (seqType === 'introduction') {
            out.push({ type: 'intro', marker: usfm(b.subtype), text: textOf(b.content, st, out) });
            continue;
        }
        const marker = usfm(b.subtype);
        const ctx = { heading: HEADING.test(marker), marker, buf: '', verseSeenHere: false, notes: [] };
        walkInline(b.content, st, out, ctx);
        flush(st, out, ctx);
    }
}

function flush(st, out, ctx) {
    const text = clean(ctx.buf);
    ctx.buf = '';
    if (text) {
        if (ctx.heading && !ctx.verseSeenHere) out.push({ type: 'heading', marker: ctx.marker, text, verse: st.verse });
        else if (st.verse != null) out.push({ type: 'verse', verse: st.verse, text, ...(ctx.heading ? { title: true } : {}) });
        else out.push({ type: 'other', marker: ctx.marker || 'p', text }); // text before any verse in a plain paragraph
    }
    out.push(...ctx.notes.splice(0)); // notes follow the text they are attached to
}

function walkInline(items, st, out, ctx) {
    for (const it of items || []) {
        if (typeof it === 'string') {
            ctx.buf += it;
            if (it.trim()) st.lastWasVerseMark = false;
            continue;
        }
        if (!it || typeof it !== 'object') continue;
        if (it.type === 'mark' && it.subtype === 'verses_label') {
            flush(st, out, ctx);
            st.verse = String(one(it.atts?.number));
            st.lastWasVerseMark = true;
            ctx.verseSeenHere = true;
            continue;
        }
        if (it.type === 'mark' && it.subtype === 'pub_verse') {
            const n = String(one(it.atts?.number));
            if (st.lastWasVerseMark) {
                // \v N \vp X: the verse is N; X is how the edition prints it
                (st.display ||= {})[st.verse] = n;
            } else {
                // a lone \vp is the only verse number there is
                flush(st, out, ctx);
                st.verse = n;
                (st.published ||= new Set()).add(n);
                ctx.verseSeenHere = true;
            }
            st.lastWasVerseMark = false;
            continue;
        }
        if (it.type === 'mark' && it.subtype === 'alt_verse') {
            (st.alt ||= {})[st.verse] = String(one(it.atts?.number));
            continue;
        }
        if (it.type === 'wrapper') {
            if (it.subtype === 'verses' && st.verse == null && it.atts?.number != null) st.verse = String(one(it.atts.number));
            walkInline(it.content, st, out, ctx);
            continue;
        }
        if (it.type === 'graft') {
            const kind = it.subtype || it.sequence?.type || '';
            if (kind === 'footnote' || kind === 'xref') ctx.notes.push(noteEntry(kind, it.sequence, st));
            else if (kind !== 'note_caller') {
                for (const p of it.sequence?.blocks || []) {
                    const t = clean(plain(p.content));
                    if (t && t !== 'NO_CAPTION') out.push({ type: 'other', marker: kind, text: t });
                }
            }
        }
        // marks other than verses, and milestones, carry no text of their own
    }
}

function noteEntry(kind, seq, st) {
    let caller = '';
    let text = '';
    for (const b of seq?.blocks || []) {
        for (const c of b.content || []) {
            if (c && typeof c === 'object' && c.type === 'graft' && (c.subtype === 'note_caller' || c.sequence?.type === 'note_caller')) {
                caller = clean(plain(c.sequence?.blocks?.flatMap((x) => x.content) || []));
            } else text += typeof c === 'string' ? c : plain([c]);
        }
    }
    return { type: 'note', kind, caller, verse: st.verse, text: clean(text) };
}

function textOf(items, st, out) {
    // heading/title/intro text; notes inside it still become their own entries
    let s = '';
    for (const it of items || []) {
        if (typeof it === 'string') s += it;
        else if (it?.type === 'wrapper') s += textOf(it.content, st, out);
        else if (it?.type === 'graft' && (it.subtype === 'footnote' || it.subtype === 'xref')) out.push(noteEntry(it.subtype, it.sequence, st));
    }
    return clean(s);
}

function plain(items) {
    let s = '';
    for (const it of items || []) {
        if (typeof it === 'string') s += it;
        else if (it?.type === 'wrapper') s += plain(it.content);
        else if (it?.type === 'graft' && it.subtype !== 'note_caller') for (const b of it.sequence?.blocks || []) s += plain(b.content);
    }
    return s;
}
