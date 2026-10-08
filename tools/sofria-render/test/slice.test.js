import test from 'node:test';
import assert from 'node:assert/strict';
import { sliceChapter } from '../src/sources/pkf.js';
import { doc, para, graft, v, c, verses, chapter } from './fixtures.js';

// A whole-book document: title and intro before chapter 1, a heading between
// chapters, and one paragraph that runs across the chapter break.
const book = doc(
    graft('title', para('mt1', 'Book')),
    graft('introduction', para('ip', 'Intro')),
    para('p', chapter(1, c(1), v(1), verses(1, 'one-one')), chapter(1, v(2), verses(2, 'one-two'))),
    graft('heading', para('s1', 'Heading of two')),
    para('p', chapter(2, c(2), v(1), verses(1, 'two-one'))),
    para('q1', chapter(2, v(2), verses(2, 'two-two')), chapter(3, c(3), v(1), verses(1, 'three-one')))
);

test('chapter 1 gets the title and introduction', () => {
    const s = JSON.stringify(sliceChapter(book, 1).sequence.blocks);
    for (const t of ['Book', 'Intro', 'one-one', 'one-two']) assert.ok(s.includes(t), t);
    for (const t of ['Heading of two', 'two-one', 'three-one']) assert.ok(!s.includes(t), t);
});

test('a heading goes with the chapter of the block after it', () => {
    const s = JSON.stringify(sliceChapter(book, 2).sequence.blocks);
    for (const t of ['Heading of two', 'two-one', 'two-two']) assert.ok(s.includes(t), t);
    for (const t of ['Book', 'one-two', 'three-one']) assert.ok(!s.includes(t), t);
});

test('a paragraph across a chapter break is split between the chapters', () => {
    const two = sliceChapter(book, 2).sequence.blocks;
    const three = sliceChapter(book, 3).sequence.blocks;
    assert.equal(two.at(-1).subtype, 'usfm:q1');
    assert.equal(three.length, 1);
    assert.equal(three[0].subtype, 'usfm:q1');
    assert.ok(JSON.stringify(three).includes('three-one'));
    assert.ok(!JSON.stringify(three).includes('two-two'));
});

test('a chapter not in the book gives no blocks', () => {
    assert.equal(sliceChapter(book, 9).sequence.blocks.length, 0);
});
