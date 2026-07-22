#!/usr/bin/env node
// Resolve the distinct options + recommended default for a language from
// catalog-overlap.json. No dependencies - uses the built-in fetch()
// (Node 18+, or any browser).
//
// Usage: node fetch_catalog_overlap.js <iso> [canon]

const URL = "https://cdn.bibel.wiki/dbt/_app/catalog-overlap.json";

async function main() {
  const iso = process.argv[2];
  const canon = process.argv[3] || "nt";
  if (!iso) {
    console.error("usage: node fetch_catalog_overlap.js <iso> [canon]");
    process.exit(1);
  }

  const data = await (await fetch(URL)).json();
  const matches = data.entries.filter((row) => row[0] === iso && row[1] === canon);

  if (matches.length === 0) {
    console.log(
      `No comparison data for '${iso}' (${canon}). Either only one source exists ` +
      `for this language, or nothing has been compared yet - check catalog-index.json instead.`
    );
    return;
  }

  console.log(`Distinct options for '${iso}' (${canon}):`);
  for (const [, , cluster] of matches) {
    const { ids } = cluster;
    const def = cluster.default || ids[0];
    const alternatives = ids.filter((i) => i !== def);
    let line = `  -> ${def}`;
    if (alternatives.length) line += `  (identical to: ${alternatives.join(", ")})`;
    console.log(line);
    if (cluster.likely) {
      console.log(
        `     not identical to anything - closest is ${cluster.closest} ` +
        `(${cluster.likely}, score ${cluster.score})`
      );
    }
  }
}

main();
