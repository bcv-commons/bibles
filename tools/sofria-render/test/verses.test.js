import test from 'node:test';
import assert from 'node:assert/strict';
import { extractEntries, verseMap } from '../src/verses.js';
import { doc, para, graft, v, mark, w, verses, chapter, note } from './fixtures.js';

const strip = (entries) => entries.map(({ type, verse, marker, text, title, beforeVerse }) => ({ type, verse, marker, text, title, beforeVerse }));

test('a title between paragraphs while a verse is open becomes a heading, not verse text', () => {
    const e = extractEntries(doc(para('p', chapter(7, v(9), verses(9, 'first half'))), para('d', chapter(7, verses(9, 'A Title'))), para('p', chapter(7, verses(9, 'second half'), v(10), verses(10, 'next')))));
    assert.deepEqual(strip(e), [
        { type: 'verse', verse: '9', marker: undefined, text: 'first half', title: undefined, beforeVerse: undefined },
        { type: 'heading', verse: '9', marker: 'd', text: 'A Title', title: undefined, beforeVerse: '9' },
        { type: 'verse', verse: '9', marker: undefined, text: 'second half', title: undefined, beforeVerse: undefined },
        { type: 'verse', verse: '10', marker: undefined, text: 'next', title: undefined, beforeVerse: undefined }
    ]);
});

test('a title numbered as verse 1 is verse 1, marked title', () => {
    const e = extractEntries(doc(para('d', chapter(3, v(1), verses(1, '(A psalm)'))), para('q1', chapter(3, v(2), verses(2, 'Lord')))));
    assert.deepEqual(e[0], { type: 'verse', verse: '1', text: '(A psalm)', title: true });
    assert.equal(verseMap(e)['2'], 'Lord');
});

test('text before the verse number in a heading paragraph is the heading; after it, the verse', () => {
    const e = extractEntries(doc(para('d', 'Heading words ', v(1), 'verse words')));
    assert.deepEqual(strip(e).map((x) => [x.type, x.text, x.title]), [
        ['heading', 'Heading words', undefined],
        ['verse', 'verse words', true]
    ]);
});

test('\\b is not a heading: its text is verse text', () => {
    const e = extractEntries(doc(para('q1', chapter(41, v(13), verses(13, 'Blessed be'))), para('b', chapter(41, verses(13, 'Amen! Amen!')))));
    assert.equal(verseMap(e)['13'], 'Blessed be Amen! Amen!');
});

test('a verse across several paragraphs is joined with a space', () => {
    assert.equal(verseMap(extractEntries(doc(para('q1', v(1), 'line one'), para('q2', 'line two'))))['1'], 'line one line two');
});

test('notes follow the verse text they belong to', () => {
    const e = extractEntries(doc(para('p', v(1), 'word', note('footnote', '+', w('usfm:ft', ['a note'])), ' more')));
    assert.deepEqual(e.map((x) => x.type), ['verse', 'note']);
    assert.equal(e[1].verse, '1');
    assert.equal(e[1].text, 'a note');
    assert.equal(e[0].text, 'word more');
});

test('title, heading and introduction grafts become typed entries', () => {
    const e = extractEntries(doc(graft('title', para('mt1', 'Book')), graft('introduction', para('ip', 'Intro')), graft('heading', para('s1', 'Section')), para('p', v(1), 'x')));
    assert.deepEqual(e.map((x) => [x.type, x.marker, x.text]), [
        ['heading', 'mt1', 'Book'],
        ['intro', 'ip', 'Intro'],
        ['heading', 's1', 'Section'],
        ['verse', undefined, 'x']
    ]);
    assert.equal(e[2].beforeVerse, '1');
});

test('published and alternate verse numbers are recorded', () => {
    const paired = extractEntries(doc(para('p', v(1), mark('pub_verse', '1a'), 'x', v(2), mark('alt_verse', '3'), 'y')));
    assert.equal(paired[0].display, '1a');
    assert.equal(paired[1].alt, '3');
    const lone = extractEntries(doc(para('p', mark('pub_verse', '1-3'), 'first', mark('pub_verse', '4'), 'second')));
    assert.deepEqual(lone.map((x) => [x.verse, x.text, x.published]), [
        ['1-3', 'first', true],
        ['4', 'second', true]
    ]);
});
