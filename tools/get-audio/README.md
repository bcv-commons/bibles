# get-audio

How a client gets a chapter's audio and verse timing: a sample, one file with no
dependencies (`get_audio.mjs`; browsers and Node >= 18).

## The standard

1. **Which editions have audio**: `https://cdn.bibel.wiki/dbt/<iso>/media.json`, per testament:
   `media: "a"` (audio) or `"at"` (audio and verse timing). `a` lists the audio fileset ids.
   For an `"a"` edition without `a`, the ids are in
   [`catalog/<i>/<iso>/audio.json`](../../doc/catalog-audio.md).
2. **Which books have timing**, without fetching anything: `timingOnly`
   `{audio fileset: [books with timing]}` or `timingExcept` `{audio fileset: [books without]}`;
   neither means every book of the testament ([dbt-timing.md](../../doc/dbt-timing.md)).
3. **Audio**: from DBT with the client's own DBT key, or, for an edition with
   `audioSource: {"source": "helloao", ...}`, from helloAO's chapter JSON
   (`thisChapterAudioLinks[reader]`, no key).
4. **Timing**, in this order:
   1. audio-sync's alignment, no key:
      `https://cdn.bibel.wiki/align/<canon>/<iso>/<edition id>/<BOOK>/<BOOK>_<NNN>_<audio fileset>_timing.json`,
      `{"pos": [verse start seconds, from verse 1], "intro_end"?: seconds}`;
   2. DBT, with the client's own key: `https://4.dbt.io/api/timestamps/<audio fileset>/<BOOK>/<chapter>?v=4&key=<key>`,
      rows `{verse_start, timestamp}` (`verse_start` `"0"` is the intro).

   A 404 or an empty answer means no timing from that source. bibles publishes no timing
   of its own (`dbt/<iso>/timing-raw/` is being retired).

All of cdn.bibel.wiki, 4.dbt.io and bible.helloao.org allow cross-origin requests, so the
code runs in a web page unchanged. Without a DBT key a client gets helloAO audio and
audio-sync's timing only.

## Use

```js
import { getChapter, verseAt } from './get_audio.mjs';
const ch = await getChapter('eng', 'nt', 'ENGKJV', 'JHN', 18, { dbtKey });
// {edition, audioFileset, audio: <mp3 URL>, timing: {source: 'align' | 'dbt', starts: {"1": 3.52, ...}, introEnd?}}
verseAt(ch.timing, 20);   // "3"
```

The parts can be used on their own: `loadMedia`, `audioEditions`, `audioFilesets`,
`hasTiming`, `getAudioUrl`, `getTiming`.

```
node get_audio.mjs eng nt ENGKJV JHN 18 --key <DBT key>    # or DBT_API_KEY in the environment
node get_audio.mjs eng nt ENGBSBHAY JHN 3                  # helloAO audio, no key needed
```

Checked 2026-10-28: ENGKJV JHN 18 (DBT audio, align timing), ENGBSBHAY JHN 3 (helloAO audio,
align timing), SPAPDT GEN 1 (OT), AAAMLT JHN 3 (DBT audio, DBT timing).

## Not covered

- audiobiblia's BLL (Spanish) audio is outside media.json: `audiobiblia/spa/BLL/_meta.json`,
  see [client-chapter-formats.md](../../doc/client-chapter-formats.md). It has no timing yet.
- openbible (Biblica) audio: Biblica's own API ([sources.md](../../doc/sources.md)).
