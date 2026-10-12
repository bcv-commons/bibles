// Route parity: for every book we publish both ways, the verse text from its USJ
// (per book) must equal the verse text from its Sofria chapters, by the same rule.
//
// Usage: node parity.mjs <usj-root> <sofria-root> <out.json>
//   e.g. node parity.mjs ../../../export/openbible-usj ../../../export/publish/sofria/openbible parity.json
import { readFileSync, readdirSync, statSync, existsSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { extractUsj } from './extract_usj.js';
import { extractSofria } from './extract_sofria.js';

const [usjRoot, sofRoot, outPath] = process.argv.slice(2);
const books = [];
(function walk(d) {
    for (const f of readdirSync(d)) {
        const p = join(d, f);
        if (statSync(p).isDirectory()) walk(p);
        else if (f.endsWith('.json') && f !== '_meta.json') books.push(p);
    }
})(usjRoot);

const report = { books: 0, chapters: 0, verses: 0, identical_chapters: 0, editions: {} };
for (const path of books) {
    const rel = relative(usjRoot, path).replace(/\.json$/, ''); // iso/abbr/BOOK
    const edition = rel.split('/').slice(0, 2).join('/');
    const usjCh = extractUsj(JSON.parse(readFileSync(path, 'utf8')));
    const sofDir = join(sofRoot, rel);
    const sofCh = {};
    if (existsSync(sofDir)) {
        for (const f of readdirSync(sofDir)) sofCh[f.replace(/\.json$/, '')] = extractSofria(JSON.parse(readFileSync(join(sofDir, f), 'utf8')));
    }
    report.books++;
    const e = (report.editions[edition] ||= { chapters: 0, differing_chapters: 0, verses_only_usj: 0, verses_only_sofria: 0, text_differs: 0, samples: [] });
    for (const ch of new Set([...Object.keys(usjCh), ...Object.keys(sofCh)])) {
        report.chapters++;
        e.chapters++;
        const a = new Map((usjCh[ch] || []).map((v) => [v.verse, v.text]));
        const b = new Map((sofCh[ch] || []).map((v) => [v.verse, v.text]));
        report.verses += a.size;
        let same = true;
        for (const [v, t] of a) {
            if (!b.has(v)) { e.verses_only_usj++; same = false; if (e.samples.length < 6) e.samples.push({ ref: `${rel} ${ch}:${v}`, kind: 'only in USJ', usj: t.slice(0, 120) }); }
            else if (b.get(v) !== t) {
                e.text_differs++; same = false;
                if (e.samples.length < 6) {
                    const s = b.get(v); let i = 0; while (i < t.length && t[i] === s[i]) i++;
                    e.samples.push({ ref: `${rel} ${ch}:${v}`, kind: 'text differs', usj: t.slice(Math.max(0, i - 30), i + 60), sofria: s.slice(Math.max(0, i - 30), i + 60) });
                }
            }
        }
        for (const [v, t] of b) if (!a.has(v)) { e.verses_only_sofria++; same = false; if (e.samples.length < 6) e.samples.push({ ref: `${rel} ${ch}:${v}`, kind: 'only in Sofria', sofria: t.slice(0, 120) }); }
        if (same) report.identical_chapters++; else e.differing_chapters++;
    }
}
for (const [k, v] of Object.entries(report.editions)) if (!v.differing_chapters) delete report.editions[k];
writeFileSync(outPath, JSON.stringify(report, null, 1));
console.log(JSON.stringify({ books: report.books, chapters: report.chapters, verses: report.verses, identical_chapters: report.identical_chapters, editions_with_differences: Object.keys(report.editions).length }));
