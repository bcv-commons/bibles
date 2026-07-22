#!/usr/bin/env node
// Fetch verse text from DBT (Bible Brain, Digital Bible Platform, by
// Faith Comes By Hearing) - requires your own API key (this repo doesn't
// proxy DBT access). Get one at https://www.faithcomesbyhearing.com/bible-brain
//
// No dependencies - uses the built-in fetch() (Node 18+, or any browser).
//
// Usage: BIBLE_API_KEY=... node fetch_dbt.js <fileset_id> <BOOK> <chapter>

const API_BASE = "https://4.dbt.io/api";

async function main() {
  const [filesetId, book, chapter] = process.argv.slice(2);
  const apiKey = process.env.BIBLE_API_KEY;
  if (!filesetId || !book || !chapter) {
    console.error("usage: BIBLE_API_KEY=... node fetch_dbt.js <fileset_id> <BOOK> <chapter>");
    process.exit(1);
  }
  if (!apiKey) {
    console.error(
      "Set BIBLE_API_KEY first - get one at https://www.faithcomesbyhearing.com/bible-brain"
    );
    process.exit(1);
  }

  const url = `${API_BASE}/bibles/filesets/${filesetId}/${book}/${chapter}?key=${apiKey}&v=4`;
  const data = await (await fetch(url)).json();
  const verses = data.data || [];

  if (verses.length && verses[0].path) {
    console.log("This fileset returns a downloadable file, not inline verses:");
    console.log(verses[0].path);
    return;
  }

  for (const verse of verses) {
    console.log(`${verse.verse_start}. ${verse.verse_text}`);
  }
}

main();
