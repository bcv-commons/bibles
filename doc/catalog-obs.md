# `catalog-obs-index.json`

`https://cdn.bibel.wiki/catalog/obs-index.json`

Thin existence signal for **OBS (Open Bible Stories)** content — the OBS
counterpart to [`catalog-index.json`](catalog-index.md) (which is
Bible-edition text only). Answers one question: "does this language have
real OBS content on door43, and is any of it audio" — nothing about story
text, audio routing, or timing detail itself; see
["Where to go for more detail"](#where-to-go-for-more-detail) below for
that.

Deliberately a **separate file**, not new rows inside `catalog-index.json`
itself: that file's `canon` field is a documented 4-value enum
(`nt`/`ntp`/`ot`/`otp`) that existing consumers validate against. OBS has
no canon at all — 50 fixed stories, no book/chapter/verse — so putting
`"obs"` in that slot would be a silent breaking assumption for any client
treating the 4-value set as exhaustive. Same `/catalog/` root, same row
convention, same `schema_version` convention as its siblings — the closest
analogue without breaking that contract.

## Shape

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "sources": [
    {"o": "https://git.door43.org/api/v1/catalog/stats-ext?subject=Open%20Bible%20Stories"}
  ],
  "entries": [
    ["ahr", "obs", "o", "at"],
    ["am", "obs", "o", "t"],
    ["mai", "obs", "o", "at", 2]
  ]
}
```

`schema_version` — same convention as
[`catalog-index.json`](catalog-index.md): an integer, bumped only on a
breaking shape change, never on data changes (new languages never bump it).
Currently `1`.

## Row format

`[iso, "obs", source, media, count?]`

- **`iso`** — ISO 639-3 language code. **Normalized**, not door43's raw
  code — 36 of 214 languages have door43 tag them with a 2-letter ISO
  639-1 code instead (`am`, `ar`, `en`, `fr`, ...); this file always uses
  the 3-letter form so it can be cross-referenced against
  `catalog-index.json` (which has zero 2-letter codes anywhere). See
  [`data/obs-iso-639-1.toml`](../data/obs-iso-639-1.toml) for the table —
  30 of the 36 are a plain, unambiguous mapping; 6 (`ar`/`fa`/`sw`/`zh`/
  `uz`/`ne`, all macrolanguage-level codes) map to whichever specific
  individual-language code this repo's own DBT catalog uses for that
  language (`arb`/`pes`/`swh`/`cmn`/`uzn`/`npi`) — a practical default,
  not a verified "same variant" fact the way the other 30 are. Found and
  fixed 2026-09-02. A handful of other entries carry a private-use
  dialect tag (`kfx-x-innerseraji`) or a region/script subtag
  (`zh-hant`, `pt-br`) — those are left as-is, not a normalization gap
  (collapsing them to a bare 3-letter code would lose real information).
- **`"obs"`** — fixed literal, standing in for `canon` in the Bible-edition
  files' row shape. Always this exact string; there is no OBS equivalent
  of `nt`/`ot`/Portions — an OBS set exists as a whole 50-story unit or not
  at all, no partial-coverage tag.
- **`source`** — single letter, currently only `o` (door43 OBS family:
  OBS-TLF, OBS-OBS4All, translationCore-Create-BCS, unfoldingWord, etc. —
  these all publish into the same door43 repo shape and get treated as one
  production line, rather than DBT/PKF/helloAO's per-organization split).
- **`media`** — `"t"` (text only) or `"at"` (audio + text — audio always
  implies text, since OBS audio is a narration of the OBS text; there is
  no audio-only case). Tells you at a glance whether it's worth fetching
  `/obs/<iso>/media.json`'s audio fields at all.
- **`count`** — how many distinct door43 repos exist for this language (a
  handful have 2, e.g. `mai`/`bho`/`srb`/`bfy`/`bhd`/`dgo` — independent
  OBS projects for the same language). Omitted when exactly 1, same
  convention as `catalog-index.json`.

## Source of truth: door43's own catalog, not audio-sync's staging tree

This file is derived **directly from door43's own catalog stats**
(`catalog/stats-ext?subject=Open%20Bible%20Stories`, plus a second query
with `&hasAudio=true` to tell audio-bearing languages apart), not from
audio-sync's `_obs_batches/<iso>.json` staging manifests. This
deliberately mirrors the DBT precedent: DBT audio existence in
[`catalog-audio-index.json`](catalog-audio-index.md) is derived directly
from DBT's own raw catalog, independent of any downstream alignment
pipeline — audio-sync *consumes* an existence signal like this one, it
doesn't produce it. Using `_obs_batches/` here instead would badly
understate real coverage: it reflects only what audio-sync has staged for
narration/alignment work, not what door43 actually has — and it would
miss the 122 text-only languages entirely (audio-sync's pipeline has no
reason to ever stage a language with no audio to narrate/align).

Per-language *detail* (content base URL, license, checking level, real
story count, and resolved per-story audio URLs) is resolved directly from
door43's own catalog/release APIs too — `fetch_obs_repos.py` covers every
row here, `"t"` and `"at"` alike, independent of `_obs_batches/`.

That independence was a deliberate fix, not the original design: this
file's audio detail was originally sourced from audio-sync's
`_obs_batches/<iso>.json` staging manifests, on the assumption that was
the right place to get resolved per-story audio URLs. That caused a real,
client-reported gap on 2026-09-01 — audio-sync's real alignment output
(`align/obs/`) reached 14 languages while `_obs_batches/` staging had only
reached 1, making 13 languages with live, real timing data invisible to
`/obs/<iso>/media.json` (the layer clients actually use for discovery).
Root cause: door43's own release assets already carry the exact same
per-story audio files audio-sync's staging resolves — a consistent
`<repo>_obs_v<version>_<NN>_<bitrate>kbps.m4a` naming pattern, verified
across 8 languages/orgs — so there was never a real need to wait on
`_obs_batches/` at all. Fixed by resolving audio the same way as
everything else here: directly from door43, in `fetch_obs_repos.py`.
`_obs_batches/`, when cached locally, is now used only as an *optional*
enrichment source for `segmentCount` (audio-sync's own narration-segment
count claim, not derivable from door43's catalog alone) — never required
for a language to have a `media.json`.

**Practical consequence, now**: `/obs/<iso>/media.json` exists for every
row in this file (214 of 214, verified 2026-09-01) — no more waiting on
any staging pipeline's pace. The only thing that can still lag is
`timing.json`, which genuinely does depend on audio-sync's real alignment
work landing at `align/obs/` — check `media.json`'s own `timingStories`
field for that, not its mere existence.

## Where to go for more detail

This file only tells you *that* a language has real OBS content on door43,
and whether any of it is audio:

- **Per-language detail** (resolved content base URL, license, checking
  level, story counts, per-story titles, and — for `"at"` rows —
  per-story audio, timing coverage) —
  [`/obs/<iso>/media.json`](obs-media.md).
- **How to fetch a story's actual text** — see
  [`obs-media.md`'s "Fetching a story's text"](obs-media.md#fetching-a-storys-text)
  for both layouts a language's `media.json` might report
  (`contentLayout: "md"` or `"ts-desktop"`), with working fetch code for
  each.
- **Per-story timing** (audio-bearing languages only) —
  [`/obs/<iso>/timing.json`](obs-media.md#obsisotimingjson), when
  `/obs/<iso>/media.json`'s `timingStories` is nonzero.

## Fixed gap: `ts-desktop`-format repos now resolve fully

17 of the 122 text-only languages (mostly Iranian-language-family repos
under the `fa_gl` door43 org — `azb`, `bal`, `bqi`, `ckb`, `def`, `glk`,
`haz`, `lki`, `lrc`, `mzn`, `qxq`, `smy`, plus a handful of others) use an
older translationStudio (`ts-desktop`) manifest format instead of the
standard Resource Container manifest — no `dublin_core.rights`/
`checking.checking_level` fields exist in that format, and content lives
at `<story>/<chunk>.txt` per chunk rather than one `<story>.md` file.
Originally left as a documented gap (`storyCount: 0`, `license`/
`checking_level: null`); **closed 2026-09-02** in `fetch_obs_repos.py`:
- **Stories**: when the standard `NN.md` scan finds nothing, a fallback
  checks the same directory listing for `NN`-named subdirectories instead
  — confirmed against `ar-xzn_obs`'s real repo tree (`01/`, `02/`, ...,
  each with numbered chunk `.txt` files plus a `title.txt`). All 17 now
  resolve their real story count and per-story title location.
- **License**: when the manifest has no `rights:` field, a fallback reads
  the repo's `LICENSE.md` (present on every `ts-desktop` repo checked) for
  its `creativecommons.org/licenses/<type>/<version>` self-description —
  all 17 resolved to `CC BY-SA 4.0`.
- **`checking_level` stays `null`** for these 17 — the only
  checking-level-shaped field in a `ts-desktop` manifest describes the
  *source* text being translated from, not this translation's own, so
  there's no reliable value to fall back to (left absent rather than
  reporting someone else's number as this translation's).

## Current population

As of 2026-09-02: **214 languages** with real OBS content on door43 — 92
with audio (`"at"`), 122 text-only (`"t"`). `/obs/<iso>/media.json` is
resolved for all 214, with real per-story titles for 10,002 of 10,010
total story slots (the 8-story shortfall is genuinely blank `# N.`
headings on door43's side — a translator left the title untranslated —
not a resolution failure). Real per-story timing (`/obs/<iso>/timing.json`)
exists for 14 languages so far, growing as audio-sync's alignment work
(`align/obs/`) progresses — that's the one thing genuinely still tied to
a downstream pipeline's pace, by nature (there's no direct-from-door43
substitute for real alignment output).
