#!/usr/bin/env node
// Fetch a language's PKF manifest entry and .pkf file - no API key needed.
// No dependencies - uses the built-in fetch() (Node 18+).
//
// A .pkf file is a gzip-compressed Proskomma "succinct docSet", not plain
// text or USFM. This script only handles the fetch; since decoding also
// needs Node, you can chain straight into ../../tools/pkf-decode/, e.g.:
//
//     node fetch_pkf.js aai
//     node ../../tools/pkf-decode/decode.mjs aai.pkf --out out/ --book REV
//
// Usage: node fetch_pkf.js <iso>

import { writeFile } from "node:fs/promises";

const MANIFEST_URL = "https://cdn.bibel.wiki/pkf/manifest.json";

async function main() {
  const iso = process.argv[2];
  if (!iso) {
    console.error("usage: node fetch_pkf.js <iso>");
    process.exit(1);
  }

  const manifest = await (await fetch(MANIFEST_URL)).json();
  const entry = manifest.languages[iso];
  if (!entry || !entry.collections || !entry.collections.length) {
    console.log(`No PKF collection for '${iso}'.`);
    return;
  }

  const collection = entry.collections[0];
  console.log("Collection info:", JSON.stringify(collection, null, 2));

  const pkfUrl = `https://cdn.bibel.wiki/pkf/${iso}/${collection.pkf}`;
  const dest = `${iso}.pkf`;
  console.log(`Fetching ${pkfUrl} ...`);
  const buf = Buffer.from(await (await fetch(pkfUrl)).arrayBuffer());
  await writeFile(dest, buf);
  console.log(`Saved to ${dest}`);
  console.log();
  console.log("This is a gzip-compressed Proskomma succinct docSet, not plain text.");
  console.log(`Decode it with: node ../../tools/pkf-decode/decode.mjs ${dest} --out out/ --book REV`);
}

main();
