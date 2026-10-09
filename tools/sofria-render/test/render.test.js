import test from 'node:test';
import assert from 'node:assert/strict';
import { renderChapter } from '../src/render.js';
import { missingStrings, missingNumbers } from './nodrop.js';
import { doc, para, graft, v, c, mark, w, verses, chapter, note, ms, me, row, cell } from './fixtures.js';

// Every test renders through this: it also asserts nothing was dropped.
function render(d, opts) {
    const r = renderChapter(d, opts);
    assert.deepEqual(missingStrings(d, r.html + r.introduction), [], 'text dropped');
    assert.deepEqual(missingNumbers(d, r.html), [], 'number dropped');
    return r;
}

test('paragraph markers become SAB classes; level 1 loses its digit', () => {
    const r = render(doc(para('p', chapter(1, c(1), v(1), verses(1, 'Alpha'))), para('q1', 'Beta'), para('q2', 'Gamma')));
    assert.match(r.html, /<div class="m" data-usfm="p">/); // drop-cap paragraph becomes m, like SAB
    assert.match(r.html, /<div class="q">/);
    assert.match(r.html, /<div class="q2">/);
});

test('verse phrases carry id, data-verse, data-phrase; a verse continued in the next paragraph gets the next letter', () => {
    const r = render(doc(para('q1', chapter(1, v(1), verses(1, 'line one'))), para('q2', chapter(1, verses(1, 'line two')))));
    assert.match(r.html, /<div id="1a" data-verse="1" data-phrase="a" class="txs seltxt scroll-item"><span class="v">1<\/span><span class="vsp">&nbsp;<\/span>line one/);
    assert.match(r.html, /<div id="1b" data-verse="1" data-phrase="b" class="txs seltxt scroll-item">line two/);
});

test('chapter number: drop-cap (default, direction-aware), top, none', () => {
    const d = doc(para('p', chapter(5, c(5), v(1), verses(1, 'x'))));
    assert.match(render(d).html, /<div class="c-drop" data-c="5" style="float:left">5<\/div>/);
    assert.match(render(d, { direction: 'rtl' }).html, /float:right/);
    assert.match(render(d, { chapterNumber: 'top' }).html, /<div class="c" data-c="5">5<\/div><div class="p">/);
    assert.match(render(d, { chapterNumber: 'none' }).html, /<div class="c" data-c="5" hidden>5<\/div>/);
});

test('a chapter number with no verse after it is still shown', () => {
    assert.match(render(doc(para('p', chapter(3, c(3), 'no verses here')))).html, /<div class="c" data-c="3">3<\/div>/);
});

test('hideVerseNumberOne and showVerseNumbers keep the number, hidden', () => {
    const d = doc(para('p', chapter(1, c(1), v(1), verses(1, 'a'), v(2), verses(2, 'b'))));
    const r1 = render(d, { hideVerseNumberOne: true });
    assert.match(r1.html, /<span class="v" data-v="1" hidden>1<\/span>/);
    assert.match(r1.html, /<span class="v">2<\/span>/);
    assert.equal((render(d, { showVerseNumbers: false }).html.match(/hidden>/g) || []).length, 2);
});

test('numerals: digit string and function', () => {
    const d = doc(para('p', chapter(12, c(12), v(10), verses(10, 'x'))));
    assert.match(render(d, { numerals: '٠١٢٣٤٥٦٧٨٩' }).html, /<span class="v">١٠<\/span>/);
    assert.match(render(d, { numerals: (s) => `[${s}]` }).html, /\[12\]/);
});

test('title graft, heading graft with ids, \\r parallel reference', () => {
    const r = render(
        doc(
            graft('title', para('mt1', 'Book'), para('mt2', 'Sub')),
            graft('heading', para('s1', 'First'), para('r', '(Ref 1.1)')),
            graft('heading', para('s1', 'Second')),
            para('p', chapter(1, v(1), verses(1, 'x')))
        ),
        { refLink: (t) => `#ref:${t}` }
    );
    assert.match(r.html, /<div class="scroll-item" data-verse="title" data-phrase="none"><div class="mt"><span class="mt">Book<\/span><\/div><div class="mt2"><span class="mt2">Sub<\/span><\/div><div class="b"><\/div><div class="b"><\/div><\/div>/);
    assert.match(r.html, /<div class="s"><div id="s1">First<\/div><\/div>/);
    assert.match(r.html, /<div class="s"><div id="s2">Second<\/div><\/div>/);
    assert.match(r.html, /<div class="r"><div id="r1"><a class="header-ref" href="#ref:\(Ref 1.1\)">/);
});

test('introduction: inline by default, or returned separately; never dropped', () => {
    const d = doc(graft('introduction', graft('title', para('imt1', 'Intro title')), para('ip', 'Intro text')), para('p', chapter(1, v(1), verses(1, 'x'))));
    const inline = render(d);
    assert.match(inline.html, /<div class="introduction">.*<div class="ip"><div id="\+1" class="txs">Intro text<\/div><\/div>/s);
    const sep = render(d, { introduction: 'separate' });
    assert.doesNotMatch(sep.html, /Intro text/);
    assert.match(sep.introduction, /Intro text/);
});

test('end titles (\\mte, \\imte) render as plain paragraphs; \\imte goes with the introduction', () => {
    const d = doc(graft('end_title', para('imte', 'End of intro')), para('p', chapter(1, v(1), verses(1, 'x'))), graft('end_title', para('mte', 'End of book')));
    const r = render(d);
    assert.deepEqual(r.warnings, []);
    assert.match(r.html, /<div class="imte">.*End of intro/s);
    assert.match(r.html, /<div class="mte">.*End of book/s);
    const sep = render(d, { introduction: 'separate' });
    assert.match(sep.introduction, /End of intro/);
    assert.doesNotMatch(sep.html, /End of intro/);
    assert.match(sep.html, /End of book/);
});

test('remarks are kept, hidden by default', () => {
    const r = render(doc(graft('remark', para('rem', 'a comment'))));
    assert.match(r.html, /<div class="rem" hidden>.*a comment/);
    assert.doesNotMatch(render(doc(graft('remark', para('rem', 'a comment'))), { remarks: 'shown' }).html, /hidden/);
});

test('\\b gets a real blank line; \\b with text keeps its text', () => {
    assert.match(render(doc(para('b'))).html, /<div class="b">&nbsp;<\/div>/);
    assert.match(render(doc(para('b', chapter(1, verses(13, 'Amen! Amen!'))))).html, /Amen! Amen!/);
});

test('footnotes: collected (default) with automatic callers, inline (SAB) as option', () => {
    const d = doc(para('p', chapter(1, v(1), verses(1, 'Word', note('footnote', '+', w('usfm:fr', ['1.1 ']), w('usfm:ft', ['Note one'])), ' more', note('xref', '+', w('usfm:xo', ['1.1 ']), w('usfm:xt', ['Gen 1.1']))))));
    const col = render(d);
    assert.match(col.html, /<a class="footnote-caller" href="#X-1" data-note="X-1"><sup class="footnote">a<\/sup><\/a>/);
    assert.match(col.html, /<sup class="footnote">b<\/sup>/); // shared caller sequence, like SAB
    assert.match(col.html, /<div class="footnotes"><div class="note" id="X-1" type="footnote"><span class="caller">a<\/span> /);
    assert.equal(col.notes.length, 2);
    assert.equal(col.notes[0].verse, '1');
    const inl = render(d, { notes: 'inline' });
    assert.match(inl.html, /<span data-graft="X-1"><a class="cursor-pointer"><sup class="footnote">a<\/sup><\/a><div id="X-1" style="display:none" type="footnote">/);
    assert.doesNotMatch(inl.html, /class="footnotes"/);
});

test('note callers follow SAB rules: "-" becomes automatic by default, or no caller (note kept); custom caller as given', () => {
    const d = doc(para('p', chapter(1, v(1), verses(1, 'x', note('footnote', '-', 'dash note'), note('footnote', '*', 'star note')))));
    assert.match(render(d).html, /<sup class="footnote">a<\/sup>.*<sup class="footnote">\*<\/sup>/s);
    const off = render(d, { callers: { footnote: { noCallerToAuto: false } } });
    assert.match(off.html, /<sup class="footnote"><\/sup>/);
    assert.match(off.html, /dash note/);
});

test('caller types: abc forces letters; custom-symbol always wins', () => {
    const d = doc(para('p', chapter(1, v(1), verses(1, 'x', note('footnote', '*', 'n1'), note('xref', '+', 'r1')))));
    assert.match(render(d, { callers: { footnote: { type: 'abc' } } }).html, /<sup class="footnote">a<\/sup>.*<sup class="footnote">b<\/sup>/s);
    assert.match(render(d, { callers: { xref: { type: 'custom-symbol', symbol: '†' } } }).html, /<sup class="footnote">†<\/sup>/);
});

test('showNotes, showImages, showVideos hide content without dropping it', () => {
    const d = doc(para('p', chapter(1, v(1), verses(1, 'x', note('footnote', '+', 'n'), w('usfm:fig', ['cap'], { src: ['f.jpg'] }), ms('zvideo', { id: ['V1'] }), me('zvideo')))));
    const r = render(d, { showNotes: false, showImages: false, showVideos: false });
    assert.match(r.html, /<a class="footnote-caller"[^>]* hidden>/);
    assert.match(r.html, /<div class="footnotes" hidden>/);
    assert.match(r.html, /<div class="image-block" data-src="f.jpg" hidden>/);
    assert.match(r.html, /<div class="video-block" data-video-id="V1" hidden>/);
});

test("verse layout one-per-line wraps each verse in div.verse-block, as SAB does", () => {
    const r = render(doc(para('p', chapter(1, v(1), verses(1, 'one'), v(2), verses(2, 'two')))), { verseLayout: 'one-per-line' });
    assert.match(r.html, /<div class="p"><div class="verse-block"><div id="1a"[^>]*>.*?one<\/div><\/div><div class="verse-block"><div id="2a"[^>]*>.*?two<\/div><\/div><\/div>/);
});

test('character styles nest (SAB keeps only one at a time)', () => {
    const r = render(doc(para('p', chapter(1, v(1), verses(1, w('usfm:wj', ['said ', w('usfm:nd', ['Lord']), ' here']))))));
    assert.match(r.html, /<span class="wj">said <span class="nd">Lord<\/span> here<\/span>/);
});

test('\\w: glossary link using the lemma when present; attributes kept as data-*', () => {
    const d = doc(para('p', chapter(1, v(1), verses(1, w('usfm:w', ['grace'], { lemma: ['charis'], strong: ['G5485'] })))));
    assert.match(render(d).html, /<span class="glossary"><a class="glossary" match="charis" data-lemma="charis" data-strong="G5485">grace<\/a><\/span>/);
    assert.match(render(d, { glossaryLinks: false }).html, /<span class="w" data-lemma="charis" data-strong="G5485">grace<\/span>/);
});

test('\\jmp: safe protocols become links; anything else stays text', () => {
    const ok = render(doc(para('p', w('usfm:jmp', ['site'], { href: ['https%3A%2F%2Fexample.org'] }))));
    assert.match(ok.html, /<a class="web-link" href="https:\/\/example.org" target="_blank" rel="noopener noreferrer">site<\/a>/);
    assert.match(render(doc(para('p', w('usfm:jmp', ['mail'], { href: ['mailto:a@b.c'] })))).html, /class="email-link"/);
    const bad = render(doc(para('p', w('usfm:jmp', ['click'], { href: ['javascript:alert(1)'] }))));
    assert.doesNotMatch(bad.html, /javascript:/);
    assert.match(bad.html, /<span class="jmp">click<\/span>/);
    assert.equal(bad.warnings.length, 1);
});

test('text and attributes are escaped', () => {
    const r = render(doc(para('p', chapter(1, v(1), verses(1, '<script>alert(1)</script> & "q"', w('usfm:w', ['x'], { lemma: ['"><img onerror=1>'] }))))));
    assert.doesNotMatch(r.html, /<script>|<img onerror/);
    assert.match(r.html, /&lt;script&gt;/);
});

test('figures: as a wrapper (PKF) and as a graft (our USJ->Sofria); NO_CAPTION is not text', () => {
    const fig = w('usfm:fig', ['A caption'], { src: ['pic.jpg'] });
    const r1 = render(doc(para('p', fig)), { figureUrl: (s) => `https://img/${s}` });
    assert.match(r1.html, /<div class="image-block" data-src="pic.jpg"><img src="https:\/\/img\/pic.jpg" alt="A caption" loading="lazy" decoding="async"><div class="caption"><span class="caption">A caption<\/span><\/div><\/div>/);
    const r2 = render(doc(para('p', { type: 'graft', subtype: 'fig', sequence: { type: 'fig', blocks: [para('f', w('usfm:fig', ['NO_CAPTION'], { unknownDefault_fig: ['p2.jpg', 'col', '', '', 'Cap from atts'] }))] } })));
    assert.match(r2.html, /<span class="image-missing" data-src="p2.jpg"><\/span><div class="caption"><span class="caption">Cap from atts<\/span>/);
    assert.doesNotMatch(r2.html, /NO_CAPTION/);
});

test('tables: header and body cells, colspan, alignment; a chapter number between rows goes before the table', () => {
    const r = render(doc(row(chapter(1, c(1), cell('Date', 'header'), cell('Text', 'header'))), row(cell('1'), cell('Gen 1', 'body', 2, 'end')), para('p', 'after')));
    assert.match(r.html, /<div class="c">1<\/div><table cellpadding="5"><tr><th class="tc1" style="text-align:start">Date<\/th><th class="tc2" style="text-align:start">Text<\/th><\/tr><tr><td class="tc1" style="text-align:start">1<\/td><td class="tc2" colspan="2" style="text-align:end">Gen 1<\/td><\/tr><\/table>/);
    assert.match(r.html, /<\/table>\n<div class="p">/);
});

test('milestones: zvideo placed after the paragraph, with an optional resolver', () => {
    const d = doc(para('p', ms('zvideo', { id: ['VID÷1'] }), me('zvideo'), 'text'));
    assert.match(render(d).html, /<\/div>\n<div class="video-block" data-video-id="VID\/1"><\/div>/);
    assert.match(render(d, { video: () => ({ title: 'Film', url: 'https://v/1', thumbnailUrl: 'https://t/1' }) }).html, /data-url="https:\/\/v\/1" style="background-image:url\(https:\/\/t\/1\)"><div class="video-title"><span class="video-title">Film<\/span>/);
});

test('milestones: zreflink and zaudioc wrap the text between start and end', () => {
    const r = render(doc(para('p', ms('zreflink', { link: ['C01.JHN.3.16'], title: ['John%203%3A16'] }), 'see this', me('zreflink'), ' and ', ms('zaudioc', { link: ['clip.mp3'] }), 'listen', me('zaudioc'))));
    assert.match(r.html, /<a class="ref-link" ref="C01.JHN.3.16" title="John 3:16">see this<\/a>/);
    assert.match(r.html, /<a class="audio-link audioclip" filelink="clip.mp3">listen<\/a>/);
});

test('milestones: zstyle adds a paragraph class, zcstyle a span class', () => {
    const r = render(doc(para('p', ms('zstyle', { id: ['special'] }), me('zstyle'), ms('zcstyle', { id: ['red'] }), me('zcstyle'), 'styled', ' plain')));
    assert.match(r.html, /<div class="p special">/);
    assert.match(r.html, /<span class="red">styled<\/span> plain/);
});

test('milestones: ordered and unordered lists', () => {
    const r = render(doc(para('p', ms('zon1', { start: ['3'] }), me('zon1'), 'first'), para('p', ms('zoli1', {}), me('zoli1'), 'item'), para('p', ms('zuli2', {}), me('zuli2'), 'bullet')));
    assert.match(r.html, /<div class="p list-item list-decimal list-inside" style="counter-set: list-item 3; padding-inline-start: 1rem">/);
    assert.match(r.html, /<div class="p list-item list-inside list-circle" style="padding-inline-start: 3rem">/);
});

test('an unknown milestone stays as a marker and is reported', () => {
    const r = render(doc(para('p', ms('zfoo', { x: ['1'] }), 'inside', me('zfoo'))));
    assert.match(r.html, /<span class="milestone" data-milestone="zfoo" data-x="1"><\/span>inside/);
    assert.equal(r.warnings.length, 1);
});

test('published verse numbers: \\v with \\vp shows \\vp; a lone \\vp is the verse number', () => {
    const paired = render(doc(para('p', chapter(1, v(1), mark('pub_verse', '1a'), verses(1, 'x')))));
    assert.match(paired.html, /<span class="v" data-v="1" hidden>1<\/span><span class="v vp" data-v="1">1a<\/span>/);
    const lone = render(doc(para('p', chapter(1, mark('pub_verse', '1-3'), 'first', mark('pub_verse', '4'), 'second'))));
    assert.match(lone.html, /<div id="1-3a" data-verse="1-3" data-phrase="a" class="txs seltxt scroll-item"><span class="v vp">1-3<\/span>/);
    assert.match(lone.html, /<span class="v vp">4<\/span>/);
});

test('alternate verse number is shown in parentheses', () => {
    assert.match(render(doc(para('p', chapter(1, v(2), mark('alt_verse', '1'), verses(2, 'x'))))).html, /<span class="va">\(1\)<\/span>/);
});

test('unknown block, inline element and graft are rendered with their text and reported', () => {
    const r = render(doc({ type: 'weird', content: ['block text'] }, para('p', { type: 'odd', content: ['inline text'] }), graft('sidebar', para('p', 'graft text'))));
    assert.match(r.html, /block text/);
    assert.match(r.html, /inline text/);
    assert.match(r.html, /<div class="graft-sidebar">/);
    assert.equal(r.warnings.length, 3);
});

test('meta_content is kept, hidden, and reported', () => {
    const r = render(doc(para('p', { type: 'mark', subtype: 'verses_label', atts: { number: '1' }, meta_content: ['meta words'] })));
    assert.match(r.html, /<span class="meta-content" hidden>meta words<\/span>/);
    assert.equal(r.warnings.length, 1);
});

test('the Proskomma "| default=\\"\\"" artifact becomes a plain bar', () => {
    const r = renderChapter(doc(para('p', 'a', '| default=""', 'b')));
    assert.match(r.html, /a\| b/);
});

test('idPrefix keeps ids unique when several chapters share a page', () => {
    const r = render(doc(graft('heading', para('s1', 'H')), para('p', chapter(1, v(1), verses(1, 'x', note('footnote', '+', 'n'))))), { idPrefix: 'MAT1-' });
    assert.match(r.html, /id="MAT1-s1"/);
    assert.match(r.html, /id="MAT1-1a"/);
    assert.match(r.html, /id="MAT1-X-1"/);
});

test('captions: shown by default; hide, heuristic and a function keep the caption in the output, hidden', () => {
    const fig = (cap) => w('usfm:fig', [cap], { src: ['f.jpg'] });
    const d = doc(para('p', chapter(1, v(1), verses(1, 'Mdimi kangulolela migongolo ', fig('Mdimi kangulolela'), fig('David becomes king')))));
    const shown = (r) => [...r.html.matchAll(/<div class="caption"( hidden)?>/g)].map((m) => !m[1]);
    assert.deepEqual(shown(render(d)), [true, true]);
    assert.deepEqual(shown(render(d, { captions: 'hide' })), [false, false]);
    assert.deepEqual(shown(render(d, { captions: 'heuristic' })), [true, false]); // no word shared with the chapter
    assert.deepEqual(shown(render(d, { captions: (cap) => cap.startsWith('David') })), [false, true]);
});

test('\\k keywords: a plain span by default (as SAB), glossary links with keywordLinks', () => {
    const d = doc(para('p', chapter(1, v(1), verses(1, 'the ', w('usfm:k', ['Sabbath']), ' day'))));
    assert.match(render(d).html, /<span class="k">Sabbath<\/span>/);
    assert.match(render(d, { keywordLinks: true }).html, /<span class="glossary"><a class="glossary" match="Sabbath">Sabbath<\/a><\/span>/);
});
