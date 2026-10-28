# Real per-verse audio timing

`bibles` publishes no timing of its own — there is nothing to fetch here
beyond this page. Per-verse timing for an audio fileset comes from one of
two sources, each at a fixed, computable URL: audio-sync's alignments,
then DBT's own timing with your own DBT key. Compute the path yourself
from `media.json`'s `filesets[]` and fetch it directly — treat a 404 or an
empty answer as "no data from that source for this chapter," nothing more.
A sample client that does all of this, audio included:
[`tools/get-audio/`](../tools/get-audio/).

**Redesigned 2026-09-14.** Earlier iterations published a merged per-book
file, then a resolved per-edition pointer index — both retired. Neither
survived contact with the real requirement: a client only ever needs the
one edition it already chose, and the real URL can be computed from
`media.json` (see below). Publishing a copy of the timing was redundant.

## The two sources, in this order

| # | Source | Path |
|---|---|---|
| 1 | **audio-sync** (`align/`, no key) | `https://cdn.bibel.wiki/align/<canon>/<iso>/<distinct_id>/<book>/<book>_<chapter:03d>_<audio_fileset>_timing.json` |
| 2 | **DBT**, with your own key | `https://4.dbt.io/api/timestamps/<audio_fileset>/<book>/<chapter>?v=4&key=<key>` |

Stop at the first one that answers. Both allow cross-origin requests from
a browser. Without a DBT key a client has audio-sync's timing only (and no
DBT audio either).

**Changed 2026-10-28.** Until then this page listed three more sources
under `https://cdn.bibel.wiki/dbt/<iso>/timing-raw/<BB|contrib|legacy>/...`,
tried first. None was DBT's live timing: `legacy` and `contrib` were
bibles' own pre-audio-sync alignments (25 sampled chapters: none matched
DBT, 18 had no DBT timing at all), and `BB` was a copy of DBT's timing
from April 2026 (deleted from the CDN 2026-10-28). `timing-raw/` is
being retired: audio-sync aligns what only it had, and `media.json` no
longer counts it.

`distinct_id` is the DBT edition abbr, the same value as `media.json`'s
`filesets[].id`, for every DBT edition but a few: on 2026-10-28, 13 audio
filesets were filed by audio-sync under another folder (e.g. `cmo`'s
`CM3WBTN1DA` under `CMOBSCK`, not `CMOBSC`; `pes`'s `PESNMVN1DA` under
`PESNMV09`). For those the computed path 404s and a client falls through
to DBT; `media.json` doesn't carry the folder.

`audio_fileset` is the specific audio fileset id (e.g. `ENGKJVN1DA`) —
**not necessarily equal to `distinct_id`** (e.g. `EN1ESV`'s chapters are
filed under audio fileset `ENGESHN1DA`). Get the real value either from
`media.json`'s `filesets[].a[]` (bibles' own known-real ids) or, for
anything audio-sync has aligned, from their manifest's `audio_fileset`
field directly.

## Discovering non-DBT editions — check `media.json` first, not manifests

**As of 2026-09-14, `media.json`'s `filesets[]` already includes any
real, confirmed-aligned edition, DBT or not** — you don't need to know an
id in advance or inspect audio-sync's manifests to find one. A non-DBT
edition looks exactly like a DBT one, plus two extra fields:

```json
{
  "id": "ENGBSBHAY", "media": "at", "a": ["ENGBSBHAY"], "t": "ENGBSBHAY",
  "audioSource": {"source": "helloao", "translation": "BSB", "reader": "hays"},
  "textSource": {"source": "helloao", "id": "BSB", "verified": true}
}
```

`audioSource`/`textSource` present means: the real audio and/or text for
this fileset id isn't this edition's own on DBT — go get it from wherever
`source` says. `audioSource.source` is currently always `"helloao"`.
`textSource` also appears on some entries that otherwise look like
ordinary DBT editions (real `distinct_id`, real `a[]`) — DBT provides the
audio but has no native text for that edition, so audio-sync tells us
which text they aligned it against: `"helloao"` (a helloAO translation
id) or `"dbt-other"` (another DBT edition's id). It is passed through from
audio-sync as is, with its own `verified` (mostly `false`) and `tier`
fields.

Until 2026-10-28 four more editions (`nor/NBS`, `deu/DEUSOL`, `mal/MALBIB`,
`xon/XONIBS`) were listed as `"at"` with neither field, from bibles' own old
timing. Their audio filesets don't exist on DBT, so they are no longer listed;
`nor/NBS` and `deu/DEUSOL` went to audio-sync.

**If you already have `media.json`, that's the whole discovery step —
skip straight to resolving the source below.** The manifest-inspection
path (`audio_fileset` presence, `text_sources`/`audio_sources` maps) is
for audio-sync's own manifests directly, useful if you're consuming
those independently rather than through bibles' catalog, or want to
understand what these fields mean.

## Which books have timing: `timingOnly` / `timingExcept`

An edition with `media: "at"` has timing, from audio-sync or DBT, for at
least some books of at least one of its `a[]` audio filesets. Which books,
per audio fileset, is published only where it isn't the whole testament
(added 2026-10-27):

```json
{"id": "ARBVDV", "media": "at", "a": ["ARBVDVN2DA", "ARZVDVN1DA"],
 "timingExcept": {"ARBVDVN2DA": ["JHN"]}}
{"id": "MDVWYI", "media": "at", "a": ["MDVWYIP1DA"],
 "timingOnly": {"MDVWYIP1DA": ["MRK"]}}
```

- An audio fileset in **neither** map has timing for every book of the
  testament (27 NT / 39 OT), like `ARZVDVN1DA` in the example.
- **`timingOnly`**: the books **with** timing; `[]` means none at all
  (this audio fileset has none, another in `a[]` does).
- **`timingExcept`**: the books **without** timing.
- Each audio fileset appears in at most one of the two, whichever list is
  shorter.

So: `timingOnly[id]` if present, else every book but `timingExcept[id]`,
else every book. A book in that set still 404s for a chapter whose
alignment failed; treat a 404 as "no timing for this chapter".

DBT's timing is checked once per testament (REV 15, else MRK 1 for the NT;
PSA 117, else GEN 1 for the OT), so a fileset with DBT timing counts as
timed for its whole testament: DBT may still answer empty for a book it
never timed.

The testament-level `timingBooks` (count) and `timingBooksSet` (books,
only when partial) are the union across all of the language's audio
filesets: use them to grey out books for the language as a whole, and the
per-fileset fields once an edition is chosen.

## First, check whether `audio_fileset` is even present (manifests only)

**If a manifest result has `audio_fileset` → it's a normal DBT edition.**
Use the table above directly, exactly as described.

**If it doesn't → this is a manually-imported, non-DBT edition, and the
formula above does not apply at all.** Resolve it instead (see next
section). Rare: as of 2026-09-14 the only real example is `ENGBSBHAY`
(English Berean Standard Bible, helloAO's `hays` narrator, renamed from
an earlier `BSBHAY`/`ENGBSB` — audio-sync corrected this in place twice
the same week; if you cached an older id, re-check) — audio-sync's own
words: "genuinely a one-off," expected to stay rare, and any future
recurrence gets its own explicit handling rather than a silent guess.

## Resolving a no-`audio_fileset` edition (e.g. `ENGBSBHAY`)

Three equivalent places carry the real answer — use whichever you already
have in hand:

1. **`media.json`'s `audioSource`/`textSource` fields** (see above) — the
   easiest, if you're already fetching `media.json`.
2. **The manifest's own `text_sources` / `audio_sources` maps** (top-level
   keys alongside `results`, keyed `"<iso>/<distinct_id>"`):
   ```json
   {
     "text_sources": {"eng/ENGBSBHAY": {"source": "helloao", "id": "BSB", "verified": true}},
     "audio_sources": {"eng/ENGBSBHAY": {"source": "helloao", "translation": "BSB", "reader": "hays"}}
   }
   ```
3. **A per-edition sidecar**, if you don't already have a manifest open:
   `https://cdn.bibel.wiki/align/<canon>/<iso>/<distinct_id>/_source.json`
   — e.g. `align/nt/eng/ENGBSBHAY/_source.json` — same two objects, no
   `results` wrapper.

Either way, `source: "helloao"` means: go get the real content from
helloAO directly, not from any bibles or audio-sync path. Confirmed live:

```
GET https://bible.helloao.org/api/{text.id}/{book}/{chapter}.json
```
→ `thisChapterAudioLinks.{audio.reader}` is the real playable audio URL
(e.g. `thisChapterAudioLinks.hays` for `ENGBSBHAY`) — verified
2026-09-14: `GET .../BSB/JHN/1.json` → `thisChapterAudioLinks.hays` =
`https://audio.bible.helloao.org/api/BSB/JHN/1/audio/hays.mp3`, a real
mp3. The same response's `thisChapterAudioTimings` field, if present, is
helloAO's own timing — not audio-sync's; not covered by this doc.

Audio-sync's manifest `whisper`/`mms`/`status`/`verses` fields still
describe the real alignment quality for this edition — only the *path*
resolution differs, not whether it's trustworthy.

## Trying the sources (DBT editions only)

Once you've confirmed `audio_fileset` is present, try audio-sync first,
then DBT, and stop at the first answer with verses. A whole chapter
resolves from one source, so this is one request, sometimes two.

## Response shapes

- **audio-sync** (`align/`): `{"id": "<BOOK> <CH>", "pos": [<verse start
  seconds>, ...], "intro_end"?: <seconds>}` — `pos` is index-aligned to
  verse order starting at verse 1.
- **DBT** (`timestamps`): `{"data": [{book, chapter, verse_start,
  verse_start_alt, timestamp}, ...]}`, one row per verse; `verse_start`
  `"0"` is the intro. `end` for a verse = the next row's `timestamp`; for
  the last verse, use the audio's duration.

## Why this is safe to compute, not just convenient

Four real gaps existed in audio-sync's manifests that would have made a
pure formula unreliable, all found and closed the same day (2026-09-14;
two reopened 2026-10-28, see #1 and #2), each the same shape: **audio-sync always has the answer in hand already —
the fix is always to have them deliver it, not for bibles or a client to
guess or maintain a side mapping.**

1. **Naming**: `align/`'s version-folder segment could, in principle, be
   an id not derivable from anything bibles or a client has. In September
   that was one case, corrected twice the same week as the id itself got
   refined (`ENGBSB` → `BSBHAY` → `ENGBSBHAY`) — each time fixed at the
   source, never by bibles maintaining a mapping. The listing of 2026-10-28
   found 13 more audio filesets under such folders (see above).
2. **Existence + path completeness**: manifest results didn't always
   carry `audio_fileset`. Fixed: mandatory on every DBT-sourced result,
   backfilled across the full historical set. A `status: "ok"` result
   was taken as the existence signal for those. 2026-10-28: it isn't
   complete (3,466 books on `align/` had no manifest), so bibles now
   builds its timing index from a listing of `align/` itself and reports
   the differences to audio-sync.
3. **The one real exception, found via #2's backfill**: `ENGBSBHAY`'s
   `audio_fileset` values turned out to be fake (`distinct_id` repeated
   back, not a real fileset) — because it was never a DBT edition at
   all, so no DBT-style path was ever going to resolve. Fixed by
   *removing* the field for this case (its absence is now itself the
   signal) and adding `text_sources`/`audio_sources` so it's still fully
   resolvable, just via a different path — see the section above.
4. **Discoverability**: knowing how to resolve `ENGBSBHAY` once you have
   its id is different from ever learning the id exists. Fixed on
   bibles' side, not audio-sync's — `text_sources`/`audio_sources` were
   already being delivered, bibles just wasn't reading them yet. Now
   folded directly into `media.json`'s `filesets[]` (see above) — the
   same catalog you already check for every DBT edition.

## Retired timing files

- `https://cdn.bibel.wiki/dbt/<iso>/timing-raw/` still holds bibles' old
  `contrib` and `legacy` timing until audio-sync has aligned the books only
  it had (requested 2026-10-28); then it is deleted. `timing-raw/BB/` was
  deleted 2026-10-28. Don't build on it.
- `dbt/<iso>/timing/<BOOK>.json` (the merged per-book files): frozen since
  2026-09-14, still on the CDN, not updated. Don't use them.
- `dbt/<iso>/timing/<audio_fileset>.json` (the per-fileset pointer index):
  deleted 2026-10-28.

## Not applicable to

OBS: its timing comes from audio-sync (`align/obs/`) or video-sync
(`obs-video/`) directly, see [OBS story timing](obs-media.md#obs-story-timing).
The old `/obs/<iso>/timing.json` is retired the same way.
