/**
 * Sofria chapter -> HTML, matching the DOM and class names SIL's Scripture App
 * Builder PWA builds (sillsdev/appbuilder-pwa, ScriptureViewSofria.svelte), so
 * SAB's own stylesheets style it unchanged.
 *
 * Rule: nothing in the input is dropped. Every element type in the Sofria schema
 * (blocks: paragraph, graft, row; inline: text, mark, wrapper, graft,
 * start_milestone, end_milestone, plus meta_content on any element) has a
 * rendering. Anything not recognised is still rendered generically, with its
 * text, and reported in `warnings`.
 *
 * Pure function: no DOM, no app state. Runs in Node and in the browser.
 */

const DEFAULTS = {
    notes: 'collected', // 'collected' | 'inline'
    chapterNumber: 'drop-cap', // 'drop-cap' | 'top' | 'none'
    direction: 'ltr',
    numerals: null, // null, a 10-character digit string, or a function(numberString) -> string
    showVerseNumbers: true,
    hideVerseNumberOne: false,
    wordsOfJesus: true,
    glossaryLinks: true,
    introduction: 'inline', // 'inline' | 'separate'
    remarks: 'hidden', // 'hidden' | 'shown'
    figureUrl: null, // function(src) -> url | null
    video: null, // function(id) -> { title, url, thumbnailUrl } | null
    refLink: null, // function(referenceText) -> href | null  (for \xt and \r)
    idPrefix: '', // prefix for generated ids, when several chapters share one page
    // SAB caller settings (footnote-caller-type etc.): type 'default' | 'abc' | 'custom-symbol'
    callers: {
        footnote: { type: 'default', symbol: '', noCallerToAuto: true },
        xref: { type: 'default', symbol: '', noCallerToAuto: true }
    },
    showNotes: true, // false: callers hidden, notes still in the output
    showImages: true, // false: figures still in the output, hidden
    showVideos: true, // false: video blocks still in the output, hidden
    verseLayout: 'paragraphs', // 'paragraphs' | 'one-per-line' (SAB's verse-layout)
    verseRangeSeparator: '-' // how a verse range like 1-3 is printed (SAB's ref-verse-range-separator)
};

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ESC[c]);

const one = (v) => (Array.isArray(v) ? v[0] : v);
const usfm = (subtype) => (subtype && subtype.startsWith('usfm:') ? subtype.slice(5) : subtype || '');

// SAB's stylesheets name level-1 markers without the digit (div.s, div.q, div.mt).
const cssClass = (marker) => marker.replace(/1$/, '');

function letterIndex(n) {
    // 0 -> a, 25 -> z, 26 -> aa ... (same sequence SAB uses for phrases and note callers)
    let s = '';
    n += 1;
    while (n > 0) {
        n -= 1;
        s = String.fromCharCode(97 + (n % 26)) + s;
        n = Math.floor(n / 26);
    }
    return s;
}

const SAFE_LINK = /^(https?:|mailto:|tel:)/i;

function decode(v) {
    try {
        return decodeURIComponent(v);
    } catch {
        return v;
    }
}

// Proskomma writes `| default=""` for an anonymous attribute bar (SAB applies the same fix).
const fixText = (t) => (t === '| default=""' ? '| ' : t);

export function renderChapter(doc, options = {}) {
    const o = { ...DEFAULTS, ...options };
    const st = {
        o,
        warnings: [],
        warned: new Set(),
        notes: [],
        noteIndex: 0, // shared caller sequence for footnotes and cross-refs, like SAB
        headingCounts: {},
        introIndex: 0,
        verse: null, // verse number currently open
        phraseIndex: 0,
        chapterLabel: null, // chapter number waiting to be placed
        firstVerseSeen: false,
        milestones: [], // open milestone stack
        pendingAfterPara: [], // e.g. video blocks, placed after the paragraph
        paraClasses: null, // extra classes from \zstyle for the current paragraph
        paraStyle: null,
        spanStyle: null, // one-shot class from \zcstyle
        lists: {}
    };
    const warn = (key, msg) => {
        if (!st.warned.has(key)) {
            st.warned.add(key);
            st.warnings.push(msg);
        }
    };
    st.warn = warn;

    const body = [];
    const intro = [];
    renderBlocks(doc.sequence?.blocks || [], doc.sequence?.type || 'main', st, body, intro);
    if (st.chapterLabel != null) {
        // a chapter number with no verse after it is still shown (hidden in 'none' mode, never dropped)
        const hide = o.chapterNumber === 'none' ? ' hidden' : '';
        body.unshift(`<div class="c" data-c="${esc(st.chapterNumber ?? st.chapterLabel)}"${hide}>${esc(numeral(st.chapterLabel, o))}</div>`);
    }

    let html = body.join('\n');
    if (o.notes === 'collected' && st.notes.length) {
        html +=
            `\n<div class="footnotes"${o.showNotes ? '' : ' hidden'}>` +
            st.notes
                .map(
                    (n) =>
                        `<div class="note" id="${esc(n.id)}" type="${esc(n.kind)}">` +
                        (n.caller ? `<span class="caller">${esc(n.caller)}</span> ` : '') +
                        `${n.html}</div>`
                )
                .join('') +
            '</div>';
    }
    return {
        html,
        introduction: o.introduction === 'separate' ? intro.join('\n') : '',
        notes: st.notes,
        warnings: st.warnings
    };
}

// ---------- blocks ----------

function renderBlocks(blocks, seqType, st, out, introOut) {
    let table = null;
    const closeTable = () => {
        if (table) {
            out.push(table.before.join('') + `<table cellpadding="5">${table.rows.join('')}</table>`);
            table = null;
        }
    };
    for (const block of blocks) {
        if (block.type === 'row') {
            table = table || { before: [], rows: [] };
            table.rows.push(renderRow(block, st, table.before));
            continue;
        }
        closeTable();
        if (block.type === 'graft') {
            renderBlockGraft(block, st, out, introOut);
        } else if (block.type === 'paragraph') {
            out.push(renderParagraph(block, seqType, st));
            out.push(...st.pendingAfterPara.splice(0));
        } else {
            st.warn(`block:${block.type}`, `unknown block type "${block.type}" rendered generically`);
            out.push(`<div class="${esc(block.type)}">${renderContent(block.content, st, seqType)}</div>`);
        }
    }
    closeTable();
}

function renderBlockGraft(block, st, out, introOut) {
    const seq = block.sequence || { blocks: [] };
    const kind = seq.type || block.subtype || '';
    if (kind === 'title') {
        const parts = (seq.blocks || []).map((b) => {
            const cls = cssClass(usfm(b.subtype) || 'mt');
            return `<div class="${esc(cls)}"><span class="${esc(cls)}">${renderContent(b.content, st, 'title')}</span></div>`;
        });
        out.push(
            `<div class="scroll-item" data-verse="title" data-phrase="none">${parts.join('')}<div class="b"></div><div class="b"></div></div>`
        );
    } else if (kind === 'heading') {
        for (const b of seq.blocks || []) out.push(renderHeading(b, st));
    } else if (kind === 'introduction') {
        const parts = [];
        renderBlocks(seq.blocks || [], 'introduction', st, parts, parts);
        const html = `<div class="introduction">${parts.join('\n')}</div>`;
        (st.o.introduction === 'separate' ? introOut : out).push(html);
    } else if (kind === 'remark') {
        const parts = [];
        renderBlocks(seq.blocks || [], 'remark', st, parts, parts);
        out.push(`<div class="rem"${st.o.remarks === 'hidden' ? ' hidden' : ''}>${parts.join('')}</div>`);
    } else {
        st.warn(`graft:${kind}`, `unknown block graft "${kind}" rendered generically`);
        const parts = [];
        renderBlocks(seq.blocks || [], kind, st, parts, parts);
        out.push(`<div class="graft-${esc(kind)}">${parts.join('\n')}</div>`);
    }
}

function renderHeading(b, st) {
    const marker = usfm(b.subtype) || 's';
    const prefix = marker.replace(/[0-9]/g, '');
    st.headingCounts[prefix] = (st.headingCounts[prefix] || 0) + 1;
    const id = `${st.o.idPrefix}${prefix}${st.headingCounts[prefix]}`;
    let inner = renderContent(b.content, st, 'heading');
    if (marker === 'r' && st.o.refLink) {
        const href = st.o.refLink(plainText(b.content));
        if (href) inner = `<a class="header-ref" href="${esc(href)}">${inner}</a>`;
    }
    return `<div class="${esc(cssClass(marker))}"><div id="${esc(id)}">${inner}</div></div>`;
}

function renderParagraph(block, seqType, st) {
    const marker = usfm(block.subtype) || 'p';
    st.paraClasses = [];
    st.paraStyle = null;
    const content = renderParaContent(block.content, st, seqType);
    let cls = cssClass(marker);
    let extraAttr = '';
    if (content.dropCap) {
        // SAB turns the paragraph holding a drop-cap into `m`; the original marker is kept.
        extraAttr = ` data-usfm="${esc(cls)}"`;
        cls = 'm';
    }
    const classes = [cls, ...st.paraClasses].join(' ');
    const style = st.paraStyle ? ` style="${esc(st.paraStyle)}"` : '';
    const blank = marker === 'b' && !content.html.trim() ? '&nbsp;' : '';
    const before = content.before || '';
    return `${before}<div class="${esc(classes)}"${extraAttr}${style}>${content.dropCap || ''}${content.html}${blank}</div>`;
}

function renderRow(block, st, before) {
    let cell = 0;
    const cells = [];
    const walk = (items) => {
        for (const it of items || []) {
            if (it && it.type === 'wrapper' && it.subtype === 'cell') {
                cell += 1;
                const a = it.atts || {};
                const tag = one(a.role) === 'header' ? 'th' : 'td';
                const span = Number(one(a.nCols)) > 1 ? ` colspan="${esc(one(a.nCols))}"` : '';
                const align = one(a.alignment) ? ` style="text-align:${esc(one(a.alignment))}"` : '';
                cells.push(`<${tag} class="tc${cell}"${span}${align}>${renderContent(it.content, st, 'main')}</${tag}>`);
            } else if (it && it.type === 'wrapper') {
                walk(it.content); // chapter/verses context around cells
            } else if (it && it.type === 'mark' && it.subtype === 'chapter_label') {
                // A chapter number between rows can't sit inside <tr>; place it before the table.
                before.push(`<div class="c">${esc(numeral(one(it.atts?.number), st.o))}</div>`);
            } else if (it && it.type === 'mark' && it.subtype === 'verses_label') {
                st.verse = one(it.atts?.number);
                cells.push(`<td class="tc-v">${verseNumberHtml(st.verse, st)}</td>`);
            } else {
                // text or anything else directly in a row, outside a cell: keep it in its own cell
                const html = renderContent([it], st, 'main');
                if (html.trim()) cells.push(`<td>${html}</td>`);
            }
        }
    };
    walk(block.content);
    return `<tr>${cells.join('')}</tr>`;
}

// ---------- inline content ----------

function numeral(n, o) {
    let s = String(n ?? '');
    if (o.verseRangeSeparator !== '-') s = s.replace(/(\d)-(\d)/g, `$1${o.verseRangeSeparator}$2`);
    if (!o.numerals) return s;
    if (typeof o.numerals === 'function') return o.numerals(s);
    return s.replace(/[0-9]/g, (d) => o.numerals[Number(d)] ?? d);
}

function verseNumberHtml(number, st) {
    return `<span class="v">${esc(numeral(number, st.o))}</span><span class="vsp">&nbsp;</span>`;
}

function phraseOpenTag(st, seqType) {
    if (seqType === 'introduction') {
        st.introIndex += 1;
        return `<div id="${esc(st.o.idPrefix)}+${st.introIndex}" class="txs">`;
    }
    const v = st.verse ?? 'none';
    const ph = letterIndex(st.phraseIndex);
    st.phraseIndex += 1;
    return `<div id="${esc(st.o.idPrefix + v + ph)}" data-verse="${esc(v)}" data-phrase="${ph}" class="txs seltxt scroll-item">`;
}

/**
 * Main-sequence paragraph content. Text is grouped into phrase divs per verse,
 * the way SAB groups it (one phrase per verse per paragraph; no audio-based
 * phrase splitting yet).
 */
function renderParaContent(items, st, seqType) {
    const res = { html: '', dropCap: '', before: '' };
    let open = false;
    // verse-layout 'one-per-line': each verse's phrases sit in a div.verse-block, as in SAB
    const perLine = st.o.verseLayout === 'one-per-line' && seqType === 'main';
    let blockOpen = false;
    const openPhrase = () => {
        if (!open) {
            if (perLine && !blockOpen) {
                res.html += '<div class="verse-block">';
                blockOpen = true;
            }
            res.html += phraseOpenTag(st, seqType);
            open = true;
        }
    };
    const closePhrase = () => {
        if (open) {
            res.html += '</div>';
            open = false;
        }
    };
    const closeBlock = () => {
        closePhrase();
        if (blockOpen) {
            res.html += '</div>';
            blockOpen = false;
        }
    };
    const emit = (html, needsPhrase = true) => {
        if (!html) return;
        if (needsPhrase) openPhrase();
        res.html += html;
    };

    // the next sibling that isn't whitespace: used to pair \v with a following \vp, \c with \cp
    const nextMark = (list, i) => {
        for (let j = i + 1; j < list.length; j++) {
            const x = list[j];
            if (typeof x === 'string' && !x.trim()) continue;
            return x && typeof x === 'object' && x.type === 'mark' ? x : null;
        }
        return null;
    };

    const walk = (list) => {
        list = list || [];
        for (let i = 0; i < list.length; i++) {
            const it = list[i];
            if (typeof it === 'string') {
                emit(textHtml(it, st));
                continue;
            }
            if (!it || typeof it !== 'object') continue;
            if (it.type === 'mark' && (it.subtype === 'chapter_label' || it.subtype === 'pub_chapter')) {
                // \cp (published chapter) is what readers see; \c stays as data-c
                if (it.subtype === 'chapter_label') st.chapterNumber = one(it.atts?.number);
                st.chapterLabel = one(it.atts?.number);
                emitMeta(it, st, emit);
                continue;
            }
            if (it.type === 'mark' && it.subtype === 'pub_verse' && st.pubPairedWith != null) {
                // \v N \vp X: show X; N is already in the phrase as data-verse and a hidden span
                res.html += `<span class="v vp" data-v="${esc(st.pubPairedWith)}">${esc(numeral(one(it.atts?.number), st.o))}</span><span class="vsp">&nbsp;</span>`;
                st.pubPairedWith = null;
                emitMeta(it, st, emit);
                continue;
            }
            if (it.type === 'mark' && (it.subtype === 'verses_label' || it.subtype === 'pub_verse')) {
                // a lone \vp (no \v before it) is the only verse number there is: it opens the verse
                const published = it.subtype === 'pub_verse';
                closeBlock();
                st.verse = one(it.atts?.number);
                st.phraseIndex = 0;
                const n = st.verse;
                const isFirst = !st.firstVerseSeen;
                st.firstVerseSeen = true;
                const pairedPub = !published && nextMark(list, i)?.subtype === 'pub_verse';
                if (isFirst && st.chapterLabel != null && seqType === 'main') {
                    const c = esc(numeral(st.chapterLabel, st.o));
                    if (st.o.chapterNumber === 'drop-cap') {
                        const side = st.o.direction.toLowerCase() === 'rtl' ? 'right' : 'left';
                        res.dropCap = `<div class="c-drop" data-c="${esc(st.chapterNumber ?? st.chapterLabel)}" style="float:${side}">${c}</div>`;
                    } else if (st.o.chapterNumber === 'top') {
                        res.before += `<div class="c" data-c="${esc(st.chapterNumber ?? st.chapterLabel)}">${c}</div>`;
                    } else {
                        // 'none': not shown, but kept
                        res.before += `<div class="c" data-c="${esc(st.chapterNumber ?? st.chapterLabel)}" hidden>${c}</div>`;
                    }
                    st.chapterLabel = null;
                }
                openPhrase();
                const hide = pairedPub || !st.o.showVerseNumbers || (isFirst && st.o.hideVerseNumberOne);
                if (pairedPub) st.pubPairedWith = n;
                const cls = published ? 'v vp' : 'v';
                res.html += hide
                    ? `<span class="v" data-v="${esc(n)}" hidden>${esc(numeral(n, st.o))}</span>`
                    : `<span class="${cls}">${esc(numeral(n, st.o))}</span><span class="vsp">&nbsp;</span>`;
                emitMeta(it, st, emit);
                continue;
            }
            if (it.type === 'mark' && (it.subtype === 'alt_verse' || it.subtype === 'alt_chapter')) {
                // \va / \ca: an alternate number, shown in parentheses after the main one
                const cls = it.subtype === 'alt_verse' ? 'va' : 'ca';
                emit(`<span class="${cls}">(${esc(numeral(one(it.atts?.number), st.o))})</span>`);
                emitMeta(it, st, emit);
                continue;
            }
            if (it.type === 'wrapper' && (it.subtype === 'chapter' || it.subtype === 'verses')) {
                if (it.subtype === 'verses' && it.atts?.number != null && st.verse == null) {
                    st.verse = one(it.atts.number);
                }
                walk(it.content);
                emitMeta(it, st, emit);
                continue;
            }
            // everything else is phrase content
            emit(renderInline(it, st, seqType));
        }
    };
    walk(items);
    closeBlock();
    return res;
}

function emitMeta(it, st, emit) {
    if (it.meta_content && it.meta_content.length) {
        st.warn('meta_content', 'meta_content present: kept as hidden text');
        emit(`<span class="meta-content" hidden>${renderContent(it.meta_content, st, 'meta')}</span>`, false);
    }
}

function textHtml(text, st) {
    let html = esc(fixText(text));
    if (st.spanStyle) {
        html = `<span class="${esc(st.spanStyle)}">${html}</span>`;
        st.spanStyle = null;
    }
    const link = st.milestones.find((m) => m.link);
    if (link) html = linkWrap(link, html);
    return html;
}

function linkWrap(m, html) {
    if (m.kind === 'zreflink') {
        return `<a class="ref-link" ref="${esc(m.link)}"${m.title ? ` title="${esc(m.title)}"` : ''}>${html}</a>`;
    }
    if (m.kind === 'zaudioc') return `<a class="audio-link audioclip" filelink="${esc(m.link)}">${html}</a>`;
    return html;
}

/** Content outside main-sequence phrase grouping (titles, headings, notes, cells). */
function renderContent(items, st, seqType) {
    let out = '';
    for (const it of items || []) {
        if (typeof it === 'string') out += textHtml(it, st);
        else out += renderInline(it, st, seqType);
    }
    return out;
}

function renderInline(it, st, seqType) {
    if (!it || typeof it !== 'object') return '';
    let html = '';
    switch (it.type) {
        case 'mark':
            html = renderMark(it, st);
            break;
        case 'wrapper':
            html = renderWrapper(it, st, seqType);
            break;
        case 'graft':
            html = renderInlineGraft(it, st);
            break;
        case 'start_milestone':
            html = startMilestone(it, st);
            break;
        case 'end_milestone':
            html = endMilestone(it, st);
            break;
        default:
            st.warn(`inline:${it.type}`, `unknown inline element "${it.type}" rendered generically`);
            html = `<span class="${esc(it.type)}">${renderContent(it.content, st, seqType)}</span>`;
    }
    if (it.meta_content && it.meta_content.length && it.type !== 'wrapper') {
        st.warn('meta_content', 'meta_content present: kept as hidden text');
        html += `<span class="meta-content" hidden>${renderContent(it.meta_content, st, 'meta')}</span>`;
    }
    return html;
}

function renderMark(it, st) {
    const n = one(it.atts?.number);
    if (it.subtype === 'verses_label') {
        st.verse = n; // a verse number nested in a character style still opens that verse
        st.firstVerseSeen = true;
        return verseNumberHtml(n, st);
    }
    if (it.subtype === 'chapter_label' || it.subtype === 'pub_chapter') {
        return `<span class="c" data-c="${esc(n)}">${esc(numeral(n, st.o))}</span>`;
    }
    if (it.subtype === 'pub_verse') return `<span class="v vp">${esc(numeral(n, st.o))}</span><span class="vsp">&nbsp;</span>`;
    if (it.subtype === 'alt_verse') return `<span class="va">(${esc(numeral(n, st.o))})</span>`;
    if (it.subtype === 'alt_chapter') return `<span class="ca">(${esc(numeral(n, st.o))})</span>`;
    st.warn(`mark:${it.subtype}`, `unknown mark "${it.subtype}" kept as an empty marker`);
    return `<span class="mark" data-mark="${esc(it.subtype ?? '')}"></span>`;
}

function attData(atts) {
    // Keep every attribute, as data-* (lemma, strong, srcloc, ...).
    let s = '';
    for (const [k, v] of Object.entries(atts || {})) {
        const name = k.replace(/[^a-zA-Z0-9_-]/g, '-').toLowerCase();
        s += ` data-${esc(name)}="${esc(Array.isArray(v) ? v.join(' ') : v)}"`;
    }
    return s;
}

function renderWrapper(it, st, seqType) {
    const marker = usfm(it.subtype);
    const inner = () => renderContent(it.content, st, seqType);
    const meta =
        it.meta_content && it.meta_content.length
            ? `<span class="meta-content" hidden>${renderContent(it.meta_content, st, 'meta')}</span>`
            : '';
    if (meta) st.warn('meta_content', 'meta_content present: kept as hidden text');

    if (it.subtype === 'chapter' || it.subtype === 'verses') return inner() + meta;
    if (it.subtype === 'cell') return `<span class="cell">${inner()}</span>${meta}`; // cell outside a row

    switch (marker) {
        case 'w': {
            const text = plainText(it.content);
            const lemma = one(it.atts?.lemma);
            if (st.o.glossaryLinks) {
                return `<span class="glossary"><a class="glossary" match="${esc((lemma || text).trim())}"${attData(it.atts)}>${inner()}</a></span>${meta}`;
            }
            return `<span class="w"${attData(it.atts)}>${inner()}</span>${meta}`;
        }
        case 'wj':
            return (st.o.wordsOfJesus ? `<span class="wj">${inner()}</span>` : `<span class="wj-off">${inner()}</span>`) + meta;
        case 'jmp': {
            const href = it.atts?.href != null ? decode(one(it.atts.href)) : '';
            const title = it.atts?.title != null ? decode(one(it.atts.title)) : '';
            if (!href || !SAFE_LINK.test(href.trim())) {
                if (href) st.warn(`jmp:${href}`, `\\jmp link with unsupported protocol kept as text: ${href}`);
                return `<span class="jmp">${inner()}</span>${meta}`;
            }
            const lower = href.toLowerCase();
            const cls = lower.startsWith('mailto:') ? 'email-link' : lower.startsWith('tel:') ? 'tel-link' : 'web-link';
            const extra = cls === 'web-link' ? ' target="_blank" rel="noopener noreferrer"' : '';
            const a = `<a class="${cls}" href="${esc(href)}"${extra}>${inner()}</a>`;
            return (title ? `<span class="dy-tooltip" style="display:inline" data-tip="${esc(title)}">${a}</span>` : a) + meta;
        }
        case 'xt': {
            const href = st.o.refLink ? st.o.refLink(plainText(it.content)) : null;
            return (href
                ? `<span class="xt reflink"><a class="header-ref" href="${esc(href)}">${inner()}</a></span>`
                : `<span class="xt reflink">${inner()}</span>`) + meta;
        }
        case 'fig':
            return renderFigure(it.atts || {}, plainText(it.content), st) + meta;
        default:
            return `<span class="${esc(cssClass(marker || it.subtype || 'wrapper'))}"${attData(it.atts)}>${inner()}</span>${meta}`;
    }
}

function renderFigure(atts, caption, st) {
    const src = one(atts.src) ?? one(atts.unknownDefault_fig) ?? '';
    if (caption === 'NO_CAPTION') caption = '';
    if (!caption && Array.isArray(atts.unknownDefault_fig) && typeof atts.unknownDefault_fig[4] === 'string') {
        caption = atts.unknownDefault_fig[4].trim();
    }
    const url = src && st.o.figureUrl ? st.o.figureUrl(src) : null;
    const img = url
        ? `<img src="${esc(url)}" alt="${esc(caption || src)}" loading="lazy" decoding="async">`
        : `<span class="image-missing" data-src="${esc(src)}"></span>`;
    const cap = caption ? `<div class="caption"><span class="caption">${esc(caption)}</span></div>` : '';
    return `<div class="image-block" data-src="${esc(src)}"${st.o.showImages ? '' : ' hidden'}>${img}${cap}</div>`;
}

// ---------- notes ----------

function renderInlineGraft(it, st) {
    const seq = it.sequence || { blocks: [] };
    const kind = it.subtype || seq.type || '';
    if (kind === 'footnote' || kind === 'xref') return renderNote(kind, seq, st);
    if (kind === 'fig') {
        // A figure as a graft (our USJ->Sofria output). It can hold more than the one
        // figure: back-to-back \fig elements nest, and proskomma-core can nest the
        // following paragraphs too. Render all of it.
        let html = '';
        for (const b of seq.blocks || []) {
            for (const c of b.content || []) {
                if (c && c.type === 'wrapper' && c.subtype === 'usfm:fig') html += renderFigure(c.atts || {}, plainText(c.content), st);
                else html += typeof c === 'string' ? textHtml(c, st) : renderInline(c, st, kind);
            }
        }
        return html;
    }
    if (kind === 'note_caller') return ''; // handled by renderNote
    st.warn(`inlinegraft:${kind}`, `unknown inline graft "${kind}" rendered generically`);
    return `<span class="graft-${esc(kind)}">${renderSeqInline(seq, st, kind)}</span>`;
}

function renderSeqInline(seq, st, kind) {
    return (seq.blocks || []).map((b) => renderContent(b.content, st, kind)).join(' ');
}


function renderNote(kind, seq, st) {
    let caller = null;
    let body = '';
    for (const b of seq.blocks || []) {
        for (const c of b.content || []) {
            if (c && typeof c === 'object' && c.type === 'graft' && (c.subtype === 'note_caller' || c.sequence?.type === 'note_caller')) {
                caller = plainSeq(c.sequence);
                continue;
            }
            body += typeof c === 'string' ? textHtml(c, st) : renderInline(c, st, kind);
        }
    }
    // SAB's caller rules (getFootnoteCallerCharacter): custom-symbol always wins; 'abc' means
    // automatic letters; '-' (no caller) becomes automatic when noCallerToAuto is set; '+' is
    // the next letter in one sequence shared by footnotes and cross-refs. SAB drops a note whose
    // caller ends up empty; here it is kept, with no visible caller.
    const rule = { type: 'default', symbol: '', noCallerToAuto: true, ...(st.o.callers?.[kind] || {}) };
    let sym = caller == null ? '+' : caller;
    let shown;
    if (rule.type === 'custom-symbol') shown = rule.symbol;
    else {
        if (rule.type === 'abc') sym = '+';
        else if (rule.noCallerToAuto && sym === '-') sym = '+';
        if (sym === '-') shown = '';
        else if (sym === '+') {
            shown = letterIndex(st.noteIndex);
            st.noteIndex += 1;
        } else shown = sym;
    }
    const id = `${st.o.idPrefix}X-${st.notes.length + 1}`;
    const note = { id, kind, caller: shown, verse: st.verse, html: body.trim() };
    st.notes.push(note);
    const sup = `<sup class="footnote">${esc(shown)}</sup>`;
    const hide = st.o.showNotes ? '' : ' hidden';
    if (st.o.notes === 'inline') {
        return `<span data-graft="${esc(id)}"${hide}><a class="cursor-pointer">${sup}</a><div id="${esc(id)}" style="display:none" type="${esc(kind)}">${note.html}</div></span>`;
    }
    return `<a class="footnote-caller" href="#${esc(id)}" data-note="${esc(id)}"${hide}>${sup}</a>`;
}

// ---------- milestones ----------

function startMilestone(it, st) {
    const m = usfm(it.subtype);
    const a = it.atts || {};
    let match;
    if ((match = m.match(/^zon(\d+)$/))) {
        st.lists[Number(match[1])] = parseInt(one(a.start), 10) || 1;
        return '';
    }
    if ((match = m.match(/^zoli(\d+)$/))) {
        const lvl = Number(match[1]);
        const n = st.lists[lvl] || 1;
        st.lists[lvl] = n + 1;
        for (const k of Object.keys(st.lists)) if (Number(k) > lvl) delete st.lists[k];
        st.paraClasses.push('list-item', 'list-decimal', 'list-inside');
        st.paraStyle = `counter-set: list-item ${n}; padding-inline-start: ${2 * lvl - 1}rem`;
        return '';
    }
    if ((match = m.match(/^zuli(\d+)$/))) {
        const lvl = Number(match[1]);
        st.paraClasses.push('list-item', 'list-inside');
        if (lvl === 2) st.paraClasses.push('list-circle');
        if (lvl >= 3) st.paraClasses.push('list-square');
        st.paraStyle = `padding-inline-start: ${2 * lvl - 1}rem`;
        return '';
    }
    switch (m) {
        case 'zvideo': {
            const id = String(one(a.id) ?? '').replace(/÷/g, '/');
            const v = st.o.video ? st.o.video(id) : null;
            const title = v?.title ? `<div class="video-title"><span class="video-title">${esc(v.title)}</span></div>` : '';
            const thumb = v?.thumbnailUrl ? ` style="background-image:url(${esc(v.thumbnailUrl)})"` : '';
            const url = v?.url ? ` data-url="${esc(v.url)}"` : '';
            st.pendingAfterPara.push(`<div class="video-block" data-video-id="${esc(id)}"${url}${thumb}${st.o.showVideos ? '' : ' hidden'}>${title}</div>`);
            return '';
        }
        case 'zaudioc':
            st.milestones.push({ kind: 'zaudioc', link: decode(String(one(a.link) ?? '')) });
            return '';
        case 'zreflink':
            st.milestones.push({
                kind: 'zreflink',
                link: decode(String(one(a.link) ?? '')),
                title: a.title != null ? decode(String(one(a.title))) : ''
            });
            return '';
        case 'zstyle':
            if (a.id != null) st.paraClasses.push(String(one(a.id)));
            return '';
        case 'zcstyle':
            if (a.id != null) st.spanStyle = String(one(a.id));
            return '';
        default:
            st.milestones.push({ kind: m });
            st.warn(`milestone:${m}`, `milestone "${m}" kept as a marker`);
            return `<span class="milestone" data-milestone="${esc(m)}"${attData(a)}></span>`;
    }
}

function endMilestone(it, st) {
    const m = usfm(it.subtype);
    for (let i = st.milestones.length - 1; i >= 0; i--) {
        if (st.milestones[i].kind === m) {
            st.milestones.splice(i, 1);
            break;
        }
    }
    return '';
}

// ---------- text helpers ----------

export function plainText(items) {
    let s = '';
    for (const it of items || []) {
        if (typeof it === 'string') s += it;
        else if (it && it.type === 'wrapper') s += plainText(it.content);
    }
    return s;
}

function plainSeq(seq) {
    let s = '';
    for (const b of seq?.blocks || []) s += plainText(b.content);
    return s.trim();
}
