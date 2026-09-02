#!/usr/bin/env node
// Fetch an OBS (Open Bible Stories) language's media.json and print
// story 01's real text, using whichever contentLayout that language
// actually uses ("md" or "ts-desktop" - see doc/obs-media.md). No
// dependencies - uses the built-in fetch() (Node 18+, or any browser).
//
// Usage: node fetch_obs.js <iso> [storyId]
//   node fetch_obs.js ahr        # standard "md" layout, has audio
//   node fetch_obs.js ar-xzn     # "ts-desktop" layout, text-only

const MEDIA_URL = (iso) => `https://cdn.bibel.wiki/obs/${iso}/media.json`;

async function fetchStandardStory(mediaJson, storyId) {
  const url = `${mediaJson.content_base_url}/${storyId}.md`;
  return await (await fetch(url)).text();
}

async function fetchTsDesktopStory(mediaJson, storyId) {
  const base = `${mediaJson.content_base_url}${storyId}/`;
  const get = (name) => fetch(base + name).then((r) => (r.ok ? r.text() : null));

  const title = await get("title.txt");
  const paragraphs = [];
  for (let n = 1; ; n++) {
    const text = await get(String(n).padStart(2, "0") + ".txt");
    if (text === null) break;
    paragraphs.push(text);
  }
  const reference = await get("reference.txt");
  return [title, "", ...paragraphs, "", reference].join("\n");
}

async function main() {
  const iso = process.argv[2];
  const storyId = process.argv[3] || "01";
  if (!iso) {
    console.error("usage: node fetch_obs.js <iso> [storyId]");
    process.exit(1);
  }

  const res = await fetch(MEDIA_URL(iso));
  if (!res.ok) {
    console.log(`No OBS media.json for '${iso}' (check catalog/obs-index.json first).`);
    return;
  }
  const media = await res.json();

  const contentLayout = media.contentLayout || "md"; // older publishes may predate this field
  console.log(`${iso}: ${media.storyCount} stories, ${media.audioStories} with audio, ` +
    `${media.timingStories} with real timing (layout: ${contentLayout})`);
  if (media.collectionTitle) console.log(`Collection title: ${media.collectionTitle}`);

  const text = contentLayout === "ts-desktop"
    ? await fetchTsDesktopStory(media, storyId)
    : await fetchStandardStory(media, storyId);

  console.log(`\n--- Story ${storyId} ---\n${text}`);
}

main();
