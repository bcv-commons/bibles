#!/usr/bin/env node
// Fetch a chapter of text from helloAO - no API key needed.
// No dependencies - uses the built-in fetch() (Node 18+, or any browser).
//
// Usage: node fetch_helloao.js <translation_id> <BOOK> <chapter>

const API_BASE = "https://bible.helloao.org/api";

async function main() {
  const [translationId, book, chapter] = process.argv.slice(2);
  if (!translationId || !book || !chapter) {
    console.error("usage: node fetch_helloao.js <translation_id> <BOOK> <chapter>");
    process.exit(1);
  }

  const url = `${API_BASE}/${translationId}/${book}/${chapter}.json`;
  const data = await (await fetch(url)).json();

  for (const block of data.chapter.content) {
    if (block.type !== "verse") continue;
    // Verse content items are plain strings, {text, poem} (poetic
    // sub-lines), or markup-only objects like {noteId} / {lineBreak} -
    // skip anything without real text.
    const parts = block.content
      .map((item) => (typeof item === "string" ? item : item.text))
      .filter(Boolean);
    console.log(`${block.number}. ${parts.join(" ")}`);
  }
}

main();
