// Audio and verse timing for a chapter: a sample client, no dependencies (browsers, Node >= 18).
//
//   media.json    https://cdn.bibel.wiki/dbt/<iso>/media.json: the editions with audio ("a")
//                 or audio and verse timing ("at"), per testament
//   audio         DBT (needs the client's own DBT key) or helloAO (audioSource), never from us
//   timing        1. audio-sync's align/ on cdn.bibel.wiki (no key)
//                 2. DBT's timestamps, with the client's own DBT key
//                 nothing else: bibles publishes no timing of its own
//
// All three hosts allow cross-origin requests, so this runs in a web page as is.
//
//   node get_audio.mjs <iso> <nt|ot> <edition id> <BOOK> <chapter> [--key <DBT key>]

const CDN = 'https://cdn.bibel.wiki';
const DBT = 'https://4.dbt.io/api';

async function getJson(url) {
  const r = await fetch(url);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`${r.status} ${url.replace(/key=[^&]*/, 'key=…')}`);
  return r.json();
}

export const loadMedia = (iso) => getJson(`${CDN}/dbt/${iso}/media.json`);

// The editions of one testament that have audio: [{id, media, a: [audio fileset ids], ...}].
// An "a" edition may have no `a` list; its fileset ids are in catalog audio.json (audioFilesets).
export function audioEditions(media, canon) {
  return (media?.canons?.[canon]?.filesets ?? []).filter((e) => e.media === 'a' || e.media === 'at');
}

// DBT audio fileset ids of an edition from catalog/<i>/<iso>/audio.json. `a:` is a suffix to the
// edition id, `A:` the whole id. Every variant is listed (bitrates, drama / non-drama).
export async function audioFilesets(iso, canon, editionId) {
  const cat = await getJson(`${CDN}/catalog/${iso[0]}/${iso}/audio.json`);
  return (cat?.entries?.[`${iso}:${canon}`]?.[editionId] ?? []).map((v) => ({
    ...v, id: v.id.startsWith('a:') ? editionId + v.id.slice(2) : v.id.slice(2),
  }));
}

// Whether a book has timing, from media.json alone (to grey out books without fetching).
// timingOnly lists the books with timing, timingExcept the books without; neither: all have it.
export function hasTiming(edition, audioFileset, book) {
  if (edition.media !== 'at') return false;
  const only = edition.timingOnly?.[audioFileset];
  if (only) return only.includes(book);
  const except = edition.timingExcept?.[audioFileset];
  return except ? !except.includes(book) : true;
}

// The audio URL of one chapter, or null. DBT audio needs the client's DBT key.
export async function getAudioUrl(edition, audioFileset, book, chapter, { dbtKey } = {}) {
  const src = edition.audioSource;
  if (src?.source === 'helloao') {
    const ch = await getJson(`https://bible.helloao.org/api/${src.translation}/${book}/${chapter}.json`);
    return ch?.thisChapterAudioLinks?.[src.reader] ?? null;
  }
  if (!dbtKey) return null;
  const r = await getJson(`${DBT}/bibles/filesets/${audioFileset}/${book}/${chapter}?v=4&key=${dbtKey}`);
  return r?.data?.[0]?.path ?? null;
}

// Verse start times of one chapter: {source: 'align' | 'dbt', starts: {verse: seconds}, introEnd?}
// or null (no timing). `verse` is the edition's own verse number as a string.
export async function getTiming(iso, canon, editionId, audioFileset, book, chapter, { dbtKey } = {}) {
  const nnn = String(chapter).padStart(3, '0');
  const al = await getJson(`${CDN}/align/${canon}/${iso}/${editionId}/${book}/${book}_${nnn}_${audioFileset}_timing.json`);
  if (al?.pos?.length) {
    const starts = Object.fromEntries(al.pos.map((t, i) => [String(i + 1), t]));   // pos[0] is verse 1
    return { source: 'align', starts, ...(al.intro_end != null && { introEnd: al.intro_end }) };
  }
  if (!dbtKey) return null;
  const r = await getJson(`${DBT}/timestamps/${audioFileset}/${book}/${chapter}?v=4&key=${dbtKey}`);
  const rows = (r?.data ?? []).filter((x) => x.verse_start !== '0');              // "0": the intro
  if (!rows.length) return null;
  return { source: 'dbt', starts: Object.fromEntries(rows.map((x) => [String(x.verse_start), Number(x.timestamp)])) };
}

// The verse playing at time t (seconds), from getTiming's starts.
export function verseAt(timing, t) {
  let cur = null;
  for (const [v, s] of Object.entries(timing.starts)) if (s <= t) cur = v;
  return cur;
}

// Everything for one chapter of one edition: the first audio fileset that gives audio.
export async function getChapter(iso, canon, editionId, book, chapter, opts = {}) {
  const edition = audioEditions(await loadMedia(iso), canon).find((e) => e.id === editionId);
  if (!edition) return null;
  const ids = edition.a ?? (await audioFilesets(iso, canon, editionId)).map((v) => v.id);
  for (const audioFileset of ids) {
    const audio = await getAudioUrl(edition, audioFileset, book, chapter, opts);
    if (!audio) continue;
    const timing = hasTiming(edition, audioFileset, book)
      ? await getTiming(iso, canon, editionId, audioFileset, book, chapter, opts) : null;
    return { edition: editionId, audioFileset, audio, timing };
  }
  return null;
}

if (typeof process !== 'undefined' && import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const k = args.indexOf('--key');
  const dbtKey = k >= 0 ? args.splice(k, 2)[1] : process.env.DBT_API_KEY;
  const [iso, canon, editionId, book, chapter] = args;
  if (!chapter) {
    console.error('usage: node get_audio.mjs <iso> <nt|ot> <edition id> <BOOK> <chapter> [--key <DBT key>]');
    process.exit(2);
  }
  const res = await getChapter(iso, canon, editionId, book, Number(chapter), { dbtKey });
  if (res?.audio) res.audio = res.audio.split('?')[0];
  console.log(JSON.stringify(res, null, 1));
}
