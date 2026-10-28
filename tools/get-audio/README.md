# get-audio

How a client gets a chapter's audio and verse timing: a sample, one file with no
dependencies (`get_audio.mjs`; browsers and Node >= 18).

## The standard

1. **Which editions have audio**: `https://cdn.bibel.wiki/dbt/<iso>/media.json`, per testament:
   `media: "a"` (audio) or `"at"` (audio and verse timing). `a` lists the audio fileset ids,
   the ones PKF uses first: play the first that has audio.
   For an `"a"` edition without `a`, the ids are in
   [`catalog/<i>/<iso>/audio.json`](../../doc/catalog-audio.md).
2. **Which books have timing**, without fetching anything: `timingOnly`
   `{audio fileset: [books with timing]}` or `timingExcept` `{audio fileset: [books without]}`;
   neither means every book of the testament ([dbt-timing.md](../../doc/dbt-timing.md)).
3. **Audio**: from DBT with the client's own DBT key, or, by the edition's `audioSource`:
   `{"source": "helloao", ...}`, from helloAO's chapter JSON (`thisChapterAudioLinks[reader]`,
   no key); `{"source": "pkf"}` (editions `<ISO>PKF`), PKF's own audio, mostly on
   scriptureearth.org, URL from `pkf/<iso>/info.json`, no key
   ([dbt-timing.md](../../doc/dbt-timing.md#pkfs-own-audio-no-key-needed)).
4. **Timing**, in this order:
   1. PKF's (se-regional-pwa), no key. For a `<ISO>PKF` edition, the timing of PKF's own audio;
      for DBT audio, where `https://cdn.bibel.wiki/pkf/<iso>/info.json`
      has an item in `media.audio.items` with `hasTiming`, `src` `h…`, the audio fileset in its
      `filename` (four forms, [dbt-timing.md](../../doc/dbt-timing.md)) and a `timingFile`
      containing `-<BOOK>-<chapter, 2 digits>-`, the timing is
      `https://cdn.bibel.wiki/pkf/<iso>/timing/<BOOK>-<chapter>.json`, `[[start, end, "1a"], ...]`
      per verse part. PKF comes first: its timing is often checked by hand
      ([dbt-timing.md](../../doc/dbt-timing.md));
   2. audio-sync's alignment, no key:
      `https://cdn.bibel.wiki/align/<canon>/<iso>/<edition id>/<BOOK>/<BOOK>_<NNN>_<audio fileset>_timing.json`,
      `{"pos": [verse start seconds, from verse 1], "intro_end"?: seconds}`;
   3. DBT, with the client's own key: `https://4.dbt.io/api/timestamps/<audio fileset>/<BOOK>/<chapter>?v=4&key=<key>`,
      rows `{verse_start, timestamp}` (`verse_start` `"0"` is the intro).

   A 404 or an empty answer means no timing from that source. bibles publishes no timing
   of its own (`dbt/<iso>/timing-raw/` is being retired).

   media.json's `"at"` and `timingOnly`/`timingExcept` count all three. This sample still
   tries PKF for every DBT audio chapter (it checks info.json anyway, to put the recording
   PKF uses for the chapter first), and align/ and DBT only where media.json says so.

   The align/ folder is the edition id for all but 13 audio filesets (2026-10-28, e.g. `cmo`
   `CM3WBTN1DA` is under `CMOBSCK`, not `CMOBSC`); for those this sample gets a 404 and falls
   through to DBT ([dbt-timing.md](../../doc/dbt-timing.md)).

All of cdn.bibel.wiki, 4.dbt.io and bible.helloao.org allow cross-origin requests, so the
code runs in a web page unchanged. Without a DBT key a client gets helloAO's audio and PKF's
own audio (115 languages, nearly all with timing), but no DBT audio.

## Use

```js
import { getChapter, verseAt } from './get_audio.mjs';
const ch = await getChapter('eng', 'nt', 'ENGKJV', 'JHN', 18, { dbtKey });
// {edition, audioFileset, audio: <mp3 URL>, timing: {source: 'pkf' | 'align' | 'dbt', starts: {"1": 3.52, ...}, introEnd?}}
verseAt(ch.timing, 20);   // "3"
```

The parts can be used on their own: `loadMedia`, `audioEditions`, `audioFilesets`,
`hasTiming`, `getAudioUrl`, `pkfFilesets`, `getPkfTiming`, `getTiming`.

```
node get_audio.mjs eng nt ENGKJV JHN 18 --key <DBT key>    # or DBT_API_KEY in the environment
node get_audio.mjs eng nt ENGBSBHAY JHN 3                  # helloAO audio, no key needed
node get_audio.mjs tee nt TEEPKF MAT 1                     # PKF's own audio and timing, no key
```

Checked 2026-10-28: ACAWBT MAT 1, ACUTBL ACT 1, ZAATBL MRK 3 (DBT audio, PKF timing), ENGKJV
JHN 18 (DBT audio, align timing), ENGBSBHAY JHN 3 (helloAO audio, align timing), SPAPDT GEN 1
(OT, align), AAAMLT JHN 3 (DBT audio, DBT timing); PKF timing for the other file-name forms:
ADETBL 1CO 1, IZZTBL MAT 1 (old DAM id), DESWBT HEB 1 (`-Heb-`), and CULWBT JHN 6 (PKF's drama
recording N2DA, played instead of N1DA). PKF's own audio and timing, no key (against the
regenerated media.json, before publishing): TEEPKF MAT 1, ZAIPKF PSA 1 (OT), DEDPKF GEN 1 and
GVSPKF MAT 1 (spaces in the file name), APSPKF MRK 1 (`url` given), AGGPKF MRK 1 (`base_url`),
IFAPKF GEN 1, TRCPKF MAT 1.

## Not covered

- audiobiblia's BLL (Spanish) audio is outside media.json: `audiobiblia/spa/BLL/_meta.json`,
  see [client-chapter-formats.md](../../doc/client-chapter-formats.md). It has no timing yet.
- openbible (Biblica) audio: Biblica's own API ([sources.md](../../doc/sources.md)).
