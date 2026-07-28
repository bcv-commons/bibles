#!/usr/bin/env node
// Resolve the distinct options + a recommended default for a language from
// catalog-overlap.json. No dependencies - uses the built-in fetch()
// (Node 18+, or any browser).
//
// No `default` field is published (removed 2026-07-28) - it's a one-line
// computation from `priority` + `ids` that every client can do itself, so
// this example does exactly that rather than relying on a precomputed field.
//
// Usage: node fetch_catalog_overlap.js <iso> [canon]

const URL = "https://cdn.bibel.wiki/dbt/_app/catalog-overlap.json";
const SOURCE_NAME = { d: "dbt", h: "helloao", p: "pkf" };

function pickDefault(ids, priority) {
  const rank = Object.fromEntries(priority.map((name, i) => [name, i]));
  return ids.reduce((best, id) => {
    const source = SOURCE_NAME[id.split(":")[0]];
    const bestSource = SOURCE_NAME[best.split(":")[0]];
    return rank[source] < rank[bestSource] ? id : best;
  });
}

async function main() {
  const iso = process.argv[2];
  const canon = process.argv[3] || "nt";
  if (!iso) {
    console.error("usage: node fetch_catalog_overlap.js <iso> [canon]");
    process.exit(1);
  }

  const data = await (await fetch(URL)).json();
  const clusters = data.entries[`${iso}:${canon}`];

  if (!clusters) {
    console.log(
      `No comparison data for '${iso}' (${canon}). Either only one candidate exists ` +
      `for this language (nothing to compare against - check catalog-index.json), ` +
      `or nothing has been fetched yet.`
    );
    return;
  }

  console.log(`Distinct options for '${iso}' (${canon}):`);
  for (const cluster of clusters) {
    const { ids } = cluster;
    if (cluster.r === false) {
      const note = cluster.confirmed_removed ? "[CONFIRMED REMOVED]" : "[currently unreachable]";
      console.log(`  ${ids[0]} ${note}`);
      continue;
    }
    const def = pickDefault(ids, data.priority);
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
