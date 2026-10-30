// Audio and verse timing for a chapter: a sample client, no dependencies (browsers, Node >= 18).
//
//   media.json    https://cdn.bibel.wiki/dbt/<iso>/media.json: the editions with audio ("a")
//                 or audio and verse timing ("at"), per testament
//   audio         DBT (needs the client's own DBT key), or per audioSource: helloAO, or PKF's own
//                 audio (mostly scriptureearth.org, no key), never from us
//   timing        1. PKF's (se-regional-pwa) on cdn.bibel.wiki/pkf/ (no key), for DBT's audio and its own
//                 2. audio-sync's align/ on cdn.bibel.wiki (no key)
//                 3. DBT's timestamps, with the client's own DBT key
//                 nothing else: bibles publishes no timing of its own
//
// All these hosts allow cross-origin requests, so this runs in a web page as is.
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
  if (src?.source === 'pkf') {                                  // id <ISO>PKF
    return (await pkfOwnItem(edition.id.slice(0, -3).toLowerCase(), book, chapter))?.audio ?? null;
  }
  if (src?.source === 'helloao') {
    const ch = await getJson(`https://bible.helloao.org/api/${src.translation}/${book}/${chapter}.json`);
    return ch?.thisChapterAudioLinks?.[src.reader] ?? null;
  }
  if (!dbtKey) return null;
  const r = await getJson(`${DBT}/bibles/filesets/${audioFileset}/${book}/${chapter}?v=4&key=${dbtKey}`);
  return r?.data?.[0]?.path ?? null;
}

// Whether a PKF audio item is DBT audio, which PKF's apps stream from DBT: its src's type in
// media.audio.sources is "fcbh" (src "h1", "h2", ...). Other sources are audio PKF gets elsewhere.
function pkfIsDbt(audio, item) {
  const type = audio.sources?.[item.src]?.type;
  return type ? type === 'fcbh' : String(item.src ?? '').startsWith('h');
}

// The DBT audio fileset of a PKF DBT audio item. damId is the source's setting, not always the
// file's: an old-style file name names the fileset the file is in (B01___01_Matthew_____
// ACAWBTP2DA.mp3, B07___01_1CorinthiansADETBLN2DA.mp3, or an old DAM id, ..._N1IZZTBL.mp3 =
// IZZTBLN1DA). Since 2026-10-29 PKF sets each item's damId to that fileset; before, in 9
// languages it was the source's (ame: AMETBLN2DA for AMETBLN1DA files), and older info.json has
// none. So damId is used when the file name contains it or is new-style
// (BSNWBTN2DA_B03_LUK_001.mp3 is in BSNTBLN2DA), else the file name's fileset.
function pkfFileset(item) {
  const f = item.filename ?? '';
  if (item.damId && f.includes(item.damId)) return item.damId;
  let m = /_([NOP][12])([A-Z0-9]{6})\.mp3$/.exec(f);
  if (m) return m[2] + m[1] + 'DA';
  m = /([A-Z0-9]{10})\.mp3$/.exec(f);
  if (m) return m[1];
  return item.damId ?? /^([A-Z0-9]{10})_[AB]\d\d_/.exec(f)?.[1] ?? null;
}

// PKF's audio items for one chapter of a language, from pkf/<iso>/info.json (cached per
// language): the book and chapter are in bookCode and chapter. In older info.json (no
// media.audio.sources) bookCode can be missing or wrong, so timingFile goes first there
// ("C01-02-MAT-01-timing.txt", any case). Items whose timingFile names this chapter come first
// (until 2026-10-29 trc's hymns were labelled REV 1-31 next to its real REV chapters).
const pkfInfo = new Map();
async function pkfItems(iso, book, chapter) {
  if (!pkfInfo.has(iso)) pkfInfo.set(iso, getJson(`${CDN}/pkf/${iso}/info.json`).catch(() => null));
  const info = await pkfInfo.get(iso);
  if (!info) pkfInfo.delete(iso);                          // a failed fetch is retried next time
  const audio = info?.media?.audio ?? {};
  const cc = String(chapter).padStart(2, '0');
  const items = (audio.items ?? []).filter((i) => i.timingFile && !audio.sources
    ? i.timingFile.toUpperCase().includes(`-${book}-${cc}-`)
    : String(i.bookCode ?? '').toUpperCase() === book && Number(i.chapter) === Number(chapter));
  const named = (i) => (i.timingFile ?? '').toUpperCase().includes(`-${book}-${cc}-`);
  items.sort((a, b) => named(b) - named(a));
  return { audio, items };
}

// The DBT audio filesets PKF timed for one chapter (usually one: the recording PKF's app uses).
export async function pkfFilesets(iso, book, chapter) {
  const { audio, items } = await pkfItems(iso, book, chapter);
  return items.filter((i) => i.hasTiming && pkfIsDbt(audio, i)).map(pkfFileset).filter(Boolean);
}

// PKF's own audio for one chapter (an edition with audioSource {source: "pkf"}, id <ISO>PKF):
// {audio: URL, hasTiming} or null. The URL is the item's url, already percent-encoded. Older
// info.json (no media.audio.sources) often has none: then base_url + "/" + filename, else
// scriptureearth.org's folder for the language, percent-encoded (some names have spaces).
async function pkfOwnItem(iso, book, chapter) {
  const { audio, items } = await pkfItems(iso, book, chapter);
  const item = items.find((i) => !pkfIsDbt(audio, i));
  if (!item) return null;
  if (audio.sources) {                // the location of a few app-bundled files is unknown
    return item.url ? { audio: item.url, hasTiming: !!item.hasTiming } : null;
  }
  const url = item.url ?? (audio.base_url
    ? `${audio.base_url.replace(/\/+$/, '')}/${item.filename}`
    : `https://www.scriptureearth.org/data/${iso}/audio/${item.filename}`);
  return { audio: encodeURI(url), hasTiming: !!item.hasTiming };
}

// PKF's timing of one chapter, or null: of a DBT audio fileset PKF timed, or of PKF's own audio
// (audioFileset <ISO>PKF). Timing rows are [start, end, "1a"] per verse part; a verse (or bridge,
// "1-2b") starts at its first part, and "s2" and other non-verse rows are skipped.
export async function getPkfTiming(iso, audioFileset, book, chapter) {
  const timed = audioFileset === `${iso.toUpperCase()}PKF`
    ? (await pkfOwnItem(iso, book, chapter))?.hasTiming
    : (await pkfFilesets(iso, book, chapter)).includes(audioFileset);
  if (!timed) return null;
  const rows = await getJson(`${CDN}/pkf/${iso}/timing/${book}-${chapter}.json`);
  const starts = {};
  for (const [start, , label] of rows ?? []) {
    const v = /^\d+/.exec(label)?.[0];
    if (v && !(v in starts)) starts[v] = start;
  }
  return Object.keys(starts).length ? { source: 'pkf', starts } : null;
}

// Verse start times of one chapter: {source: 'pkf' | 'align' | 'dbt', starts: {verse: seconds},
// introEnd?} or null (no timing). `verse` is the edition's own verse number as a string. PKF
// first, for any DBT audio; align/ and DBT only where media.json says the book has timing (pass
// `edition`, or omit it to try them anyway).
export async function getTiming(iso, canon, editionId, audioFileset, book, chapter,
                                { dbtKey, edition } = {}) {
  const pkf = edition?.audioSource?.source === 'helloao' ? null : await getPkfTiming(iso, audioFileset, book, chapter);
  if (pkf) return pkf;
  if (edition && !hasTiming(edition, audioFileset, book)) return null;
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

// Everything for one chapter of one edition: the first audio fileset that gives audio, trying
// first the recording PKF uses for this chapter (its choice is usually reviewed by hand).
export async function getChapter(iso, canon, editionId, book, chapter, opts = {}) {
  const edition = audioEditions(await loadMedia(iso), canon).find((e) => e.id === editionId);
  if (!edition) return null;
  let ids = edition.a ?? (await audioFilesets(iso, canon, editionId)).map((v) => v.id);
  if (!edition.audioSource) {
    const pkf = await pkfFilesets(iso, book, chapter);
    ids = [...ids.filter((id) => pkf.includes(id)), ...ids.filter((id) => !pkf.includes(id))];
  }
  for (const audioFileset of ids) {
    const audio = await getAudioUrl(edition, audioFileset, book, chapter, opts);
    if (!audio) continue;
    const timing = await getTiming(iso, canon, editionId, audioFileset, book, chapter, { ...opts, edition });
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
