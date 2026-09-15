# Real per-verse audio timing

`bibles` publishes no resolved timing index — there is nothing to fetch
here beyond this page. Real per-verse timing for any DBT audio fileset
comes from one of four sources, each at a fixed, computable URL. Compute
the path yourself from data you already have (from `media.json`'s
`filesets[]`, or from audio-sync's own manifests) and fetch it directly —
treat a 404 as "no data from that source for this chapter," nothing more.

**Redesigned 2026-09-14.** Earlier iterations published a merged per-book
file, then a resolved per-edition pointer index — both retired. Neither
survived contact with the real requirement: a client only ever needs the
one edition it already chose, and audio-sync's own manifests already
carry everything needed to compute the real URL and know whether it's
real, once two gaps in their manifest schema were closed (see below).
Publishing a copy of that was redundant.

## The four sources, in override priority (later wins on a conflict)

| # | `src` | Owner | Path formula |
|---|---|---|---|
| 1 | `BB` | bibles (DBT's own bulk export, republished) | `https://cdn.bibel.wiki/dbt/<iso>/timing-raw/BB/<canon>/<distinct_id>/<book>/<book>_<chapter:03d>_<audio_fileset>_timing.json` |
| 2 | `contrib` | bibles (community-contributed, republished) | same shape, `BB` → `contrib` |
| 3 | `legacy` | bibles (one-time historical copy, republished) | same shape, `BB` → `legacy` |
| 4 | `align` | **audio-sync** (their own live CDN, not mirrored here) | `https://cdn.bibel.wiki/align/<canon>/<iso>/<distinct_id>/<book>/<book>_<chapter:03d>_<audio_fileset>_timing.json` |

`distinct_id` is the DBT edition abbr (same value as `media.json`'s
`filesets[].id`) for every **DBT-sourced** edition — confirmed live for
both bibles' own sources and audio-sync's.

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
this fileset id isn't ours or DBT's — go get it from wherever `source`
says (currently always `"helloao"`). This also appears on some entries
that otherwise look like ordinary DBT editions (real `distinct_id`, real
`a[]`) — DBT provides the audio but has no native text for that edition,
so audio-sync tells us which text they verified it against.

**A handful of editions (4, confirmed 2026-09-15: `nor/NBS` — `src:
"legacy"`; `deu/DEUSOL` — `src: "contrib"`; `mal/MALBIB` and `xon/XONIBS`
— `src: "BB"`) carry `media: "at"` and a real `a[]` id with *neither*
field** — bibles' own pre-this-repo historical timing imports (not DBT,
not audio-sync), with no preserved record of the real audio's origin.
Real and resolvable via the formula above (using each one's own `src`
above — they're not all the same source), just honestly un-attributed
rather than guessed — e.g. `nor/NBS`'s real DBT text counterpart is very
likely `NORNBS` by name, but that's an unverified guess, not confirmed
the way `ENGBSBHAY`'s pairing was, so no `t` is published for these. If
you can independently verify the real source for one of these, that's
useful information to send back.

**One of the four, `nor/NBS`, also has a real playable raw audio file** —
confirmed live: `https://cdn.bibel.wiki/audio/nor/NBS/<BOOK>_<chapter>.mp3`
(e.g. `.../JHN_1.mp3`, `.../JHN_2.mp3`, `.../JHN_3.mp3`, all real
`audio/mpeg`, no zero-padding on the chapter number). **This is not a
general convention** — checked directly and ruled out for the other
three (`DEUSOL`, `MALBIB`, `XONIBS` all 404 at the equivalent path
across multiple books/chapters tried) — don't assume it applies beyond
`NBS` specifically without checking.

`textSource` alone (no `audioSource`) is the DBT-audio-but-non-DBT-text
case described just above — a real DBT `distinct_id` with real `a[]`,
just no native DBT text.

**If you already have `media.json`, that's the whole discovery step —
skip straight to resolving the source below.** The manifest-inspection
path (`audio_fileset` presence, `text_sources`/`audio_sources` maps) is
for audio-sync's own manifests directly, useful if you're consuming
those independently rather than through bibles' catalog, or want to
understand what these fields mean.

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

Two equivalent places carry the real answer — use whichever you already
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

Once you've confirmed `audio_fileset` is present, try the four sources in
priority order 1→4, stop at the first 200. In practice a whole chapter
(often a whole book) resolves from exactly one source, so this is
usually one request, sometimes two.

## Response shapes — differ by `src`

- **`BB` / `contrib` / `legacy`** (bibles' own, unchanged raw files): a
  flat list of `{book, chapter, verse_start, timestamp}` rows, one per
  verse. `end` for a verse = the next row's `timestamp`; the last verse's
  `end` = its own `timestamp` — use the audio's real duration for that one.
- **`align`** (audio-sync's own): `{"id": "<BOOK> <CH>", "pos": [<verse
  start seconds>, ...], "intro_end": <seconds>}` — `pos` is index-aligned
  to verse order starting at verse 1.

## Why this is safe to compute, not just convenient

Three real gaps existed in audio-sync's manifests that would have made a
pure formula unreliable, all found and closed the same day (2026-09-14),
each the same shape: **audio-sync always has the answer in hand already —
the fix is always to have them deliver it, not for bibles or a client to
guess or maintain a side mapping.**

1. **Naming**: `align/`'s version-folder segment could, in principle, be
   an id not derivable from anything bibles or a client has. Turned out
   to be one case, corrected twice the same week as the id itself got
   refined (`ENGBSB` → `BSBHAY` → `ENGBSBHAY`) — each time fixed at the
   source, never by bibles maintaining a mapping.
2. **Existence + path completeness**: manifest results didn't always
   carry `audio_fileset`. Fixed: mandatory on every DBT-sourced result,
   backfilled across the full historical set. A `status: "ok"` result
   **is** the existence signal for those — no separate check needed.
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

## For bibles' own sources (`BB`/`contrib`/`legacy`)

These are republished unchanged, byte-for-byte, by `publish_timing_raw.py`
— bibles is the only host for these three (no external producer), so this
part still requires a real publish step, just no resolution logic. A
version-excluded `(iso, distinct_id)` pair (`data/version-exclude.toml`)
is skipped entirely — nothing published for it under any of the three.

## Not applicable to

[`/obs/<iso>/timing.json`](obs-media.md#obsisotimingjson) — a different,
still-embedded-data format for now; OBS's much smaller content scale (50
stories) doesn't hit the over-fetch problem this redesign exists to fix.
