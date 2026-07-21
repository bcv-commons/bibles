#!/usr/bin/env node
/**
 * Decode a PKF file (a Proskomma "succinct docSet" — gzip-compressed JSON)
 * into one plain USFM file per book. PKF is the format behind
 * cdn.bibel.wiki/pkf/<iso>/<collection>.pkf (published by the se-regional-pwa
 * repo, sourced from Scripture App Builder / scriptureearth.org).
 *
 * This is a sample client solution: it shows how to read PKF content without
 * needing to understand Proskomma's internals — proskomma-core's native
 * `usfm` document field does the actual export.
 *
 * Setup (once): cd tools/pkf-decode && npm install
 *
 * Usage:
 *   node decode.mjs <path-to.pkf> [--out <dir>]
 *   node decode.mjs <dir-of-.pkf-files> [--out <dir>]
 *
 * Example — decode a language fetched from the CDN:
 *   curl -o aai_C01.pkf https://cdn.bibel.wiki/pkf/aai/aai_C01.Dv3gvNPV.pkf
 *   node decode.mjs aai_C01.pkf --out out/aai
 *   # -> out/aai/41-MAT.usfm, out/aai/67-REV.usfm, ...
 */
import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync } from 'node:fs';
import { join, basename } from 'node:path';
import { decompressSync, strFromU8 } from 'fflate';
import { Proskomma } from 'proskomma-core';

// USFM/Paratext book id -> file number, for stable sortable filenames.
// 40 is reserved (skipped) between OT (39 books) and NT (starts at 41).
const BOOK_NUM = {
  GEN: '01', EXO: '02', LEV: '03', NUM: '04', DEU: '05', JOS: '06', JDG: '07',
  RUT: '08', '1SA': '09', '2SA': '10', '1KI': '11', '2KI': '12', '1CH': '13',
  '2CH': '14', EZR: '15', NEH: '16', EST: '17', JOB: '18', PSA: '19', PRO: '20',
  ECC: '21', SNG: '22', ISA: '23', JER: '24', LAM: '25', EZK: '26', DAN: '27',
  HOS: '28', JOL: '29', AMO: '30', OBA: '31', JON: '32', MIC: '33', NAM: '34',
  HAB: '35', ZEP: '36', HAG: '37', ZEC: '38', MAL: '39',
  MAT: '41', MRK: '42', LUK: '43', JHN: '44', ACT: '45', ROM: '46', '1CO': '47',
  '2CO': '48', GAL: '49', EPH: '50', PHP: '51', COL: '52', '1TH': '53',
  '2TH': '54', '1TI': '55', '2TI': '56', TIT: '57', PHM: '58', HEB: '59',
  JAS: '60', '1PE': '61', '2PE': '62', '1JN': '63', '2JN': '64', '3JN': '65',
  JUD: '66', REV: '67',
  // deuterocanon
  TOB: '68', JDT: '69', ESG: '70', WIS: '71', SIR: '72', BAR: '73', LJE: '74',
  S3Y: '75', SUS: '76', BEL: '77', '1MA': '78', '2MA': '79', '3MA': '80',
  '4MA': '81', '1ES': '82', '2ES': '83', MAN: '84', PS2: '85', ODA: '86',
  PSS: '87',
  // peripherals + user-defined "extra material" books (XXA-XXG)
  FRT: 'A0', BAK: 'A1', OTH: 'A2', INT: 'A7', CNC: 'A8', GLO: 'A9', TDX: 'B0',
  NDX: 'B1', XXA: '94', XXB: '95', XXC: '96', XXD: '97', XXE: '98', XXF: '99',
  XXG: '100',
};

class PkfProskomma extends Proskomma {
  constructor() {
    super();
    this.selectors = [
      { name: 'lang', type: 'string', regex: '^[A-Za-z0-9-]{2,30}$' },
      { name: 'abbr', type: 'string', regex: '^[A-Za-z0-9 -]+$' },
    ];
    this.validateSelectors();
  }
}

function parseArgs(argv) {
  const out = { input: null, out: null, book: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--out') out.out = argv[++i];
    else if (a === '--book') out.book = argv[++i].toUpperCase();
    else if (!a.startsWith('--') && !out.input) out.input = a;
  }
  return out;
}

function decodePkf(pkfPath, outDir, bookFilter) {
  const pk = new PkfProskomma();
  pk.loadSuccinctDocSet(
    JSON.parse(strFromU8(decompressSync(new Uint8Array(readFileSync(pkfPath)))))
  );
  const dsId = pk.gqlQuerySync('{docSets{id}}').data.docSets[0].id;
  const docs = pk.gqlQuerySync(
    `{docSet(id:"${dsId}"){documents{bookCode:header(id:"bookCode")}}}`
  ).data.docSet.documents;

  mkdirSync(outDir, { recursive: true });
  let n = 0;
  const unmapped = [];
  for (const { bookCode } of docs) {
    if (bookFilter && bookCode !== bookFilter) continue;
    const usfm = pk.gqlQuerySync(
      `{docSet(id:"${dsId}"){document(bookCode:"${bookCode}"){ usfm }}}`
    ).data.docSet.document.usfm;
    const num = BOOK_NUM[bookCode];
    if (!num) unmapped.push(bookCode);
    const name = num ? `${num}-${bookCode}.usfm` : `${bookCode}.usfm`;
    writeFileSync(join(outDir, name), usfm);
    n++;
  }
  return { n, unmapped };
}

function main() {
  const { input, out, book } = parseArgs(process.argv.slice(2));
  if (!input) {
    console.error('usage: node decode.mjs <path-to.pkf-or-dir> [--out <dir>] [--book <BOOKCODE>]');
    process.exit(2);
  }

  let pkfFiles;
  const st = statSync(input);
  if (st.isDirectory()) {
    pkfFiles = readdirSync(input).filter((f) => f.endsWith('.pkf')).map((f) => join(input, f));
  } else {
    pkfFiles = [input];
  }
  if (pkfFiles.length === 0) {
    console.error(`[pkf-decode] no .pkf files found in ${input}`);
    process.exit(1);
  }

  const baseOut = out || 'out';
  const multi = pkfFiles.length > 1;
  for (const pkfPath of pkfFiles) {
    const base = basename(pkfPath).split('.')[0]; // e.g. aai_C01
    const dir = multi ? join(baseOut, base) : baseOut;
    const { n, unmapped } = decodePkf(pkfPath, dir, book);
    let msg = `[pkf-decode] ${base}: ${n} book(s) -> ${dir}/`;
    if (unmapped.length) msg += `  (unknown book code, named without a number prefix: ${unmapped.join(', ')})`;
    console.log(msg);
  }
}

main();
