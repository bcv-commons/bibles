// Language parity, JS side: one line per chapter and route, "<route>\t<book>\t<chapter>\t<sha256>",
// hashing the extracted verses as "<verse>\t<text>\n" lines. ../python/dump.py writes the same.
// Usage: node dump.mjs <usj-root> <sofria-root> > js.tsv
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative } from 'node:path';
import { createHash } from 'node:crypto';
import { extractUsj } from './extract_usj.js';
import { extractSofria } from './extract_sofria.js';

const [usjRoot, sofRoot] = process.argv.slice(2);
const hash = (verses) => createHash('sha256').update(verses.map((v) => `${v.verse}\t${v.text}\n`).join('')).digest('hex');
const books = [];
(function walk(d) {
    for (const f of readdirSync(d).sort()) {
        const p = join(d, f);
        if (statSync(p).isDirectory()) walk(p);
        else if (f.endsWith('.json') && f !== '_meta.json') books.push(p);
    }
})(usjRoot);
const lines = [];
for (const path of books) {
    const rel = relative(usjRoot, path).replace(/\.json$/, '');
    for (const [ch, verses] of Object.entries(extractUsj(JSON.parse(readFileSync(path, 'utf8'))))) lines.push(`usj\t${rel}\t${ch}\t${hash(verses)}`);
    const dir = join(sofRoot, rel);
    if (existsSync(dir)) for (const f of readdirSync(dir)) lines.push(`sofria\t${rel}\t${f.replace(/\.json$/, '')}\t${hash(extractSofria(JSON.parse(readFileSync(join(dir, f), 'utf8'))))}`);
}
process.stdout.write(lines.sort().join('\n') + '\n');
