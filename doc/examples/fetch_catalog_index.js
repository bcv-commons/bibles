#!/usr/bin/env node
// Look up what's available for a language from catalog-index.json.
// No dependencies - uses the built-in fetch() (Node 18+, or any browser).
//
// Usage: node fetch_catalog_index.js <iso>

const URL = "https://cdn.bibel.wiki/catalog/index.json";
const SOURCE_NAMES = { d: "DBT", p: "PKF", h: "helloAO" };

async function main() {
  const iso = process.argv[2];
  if (!iso) {
    console.error("usage: node fetch_catalog_index.js <iso>");
    process.exit(1);
  }

  const data = await (await fetch(URL)).json();
  const matches = data.entries.filter((row) => row[0] === iso);

  if (matches.length === 0) {
    console.log(`No entries found for '${iso}'.`);
    return;
  }

  console.log(`Availability for '${iso}':`);
  for (const row of matches) {
    const [, canon, source, count = 1] = row;
    const portions = canon.endsWith("p") ? " (Portions - partial coverage)" : "";
    console.log(`  ${canon.padEnd(4)} ${SOURCE_NAMES[source].padEnd(8)} ${count} version(s)${portions}`);
  }
}

main();
