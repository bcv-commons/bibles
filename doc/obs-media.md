# `/obs/<iso>/media.json`

`https://cdn.bibel.wiki/obs/<iso>/media.json`

Per-language detail for OBS (Open Bible Stories) narration content — the
OBS analogue of [`/dbt/<iso>/media.json`](README.md), at its own root
(`/obs/`, not `/dbt/`) because OBS is a genuinely different content shape:
50 fixed stories, no book/chapter/verse/canon. Only exists for languages
listed in [`catalog-obs-index.json`](catalog-obs.md) — check that file
first before fetching this one. `iso` here is normalized the same way as
there (ISO 639-3, not door43's raw code for 36 of 214 languages) — see
that doc's `iso` field note.

## Shape

```json
{
  "iso": "ahr",
  "source": "OBS-TLF",
  "source_repo": "OBS-TLF/ahr_obs",
  "content_base_url": "https://git.door43.org/OBS-TLF/ahr_obs/raw/tag/v1/content",
  "contentLayout": "md",
  "license": "CC BY-SA 4.0",
  "checking_level": "1",
  "storyCount": 50,
  "audioStories": 50,
  "timingStories": 50,
  "stories": {
    "01": {
      "title": "सृष्टी",
      "audio_url": "https://git.door43.org/OBS-TLF/ahr_obs/releases/download/v1/ahr_obs_v1_01_128kbps.m4a",
      "segmentCount": 16
    }
  }
}
```

(`audioStoriesSet`/`timingStoriesSet` only appear when partial — see below;
omitted here because `ahr` has all 50.)

## Fields

- **`source`** / **`source_repo`** — the door43 org/repo this content
  comes from (e.g. `OBS-TLF`, `OBS-OBS4All`, `translationCore-Create-BCS`,
  `unfoldingWord`, `Door43-Catalog`). Resolved directly from door43's own
  catalog API for every language, audio-bearing or text-only alike.
- **`content_base_url`** — the real, resolved base URL for fetching a
  story's source text/images (`<content_base_url>/<story_id>.md`, per
  door43's OBS content convention). Resolved here so a client doesn't need
  to interpolate door43 raw-URL patterns itself — different door43 repos
  don't always use `content` as their sub-path (some put it at repo root),
  and this field already reflects whatever the real repo layout is.
- **`contentLayout`** — `"md"` (197 of 214 languages) or `"ts-desktop"`
  (17 of 214). Tells a client which of the two fetch strategies below to
  use for a story's actual text — **this repo never fetches or re-hosts
  story text itself** (`stories[storyId].title` is the one deliberate
  exception, see above), so getting the body is always the client's own
  fetch against `content_base_url`. See
  ["Fetching a story's text"](#fetching-a-storys-text) below for both.
- **`license`** / **`checking_level`** — read from the source repo's
  manifest at resolution time, carried through as-is.
- **`storyCount`** — how many of the 50 canonical OBS stories this
  language's repo has a real content file for (almost always 50; a few
  repos are genuinely partial — see `awa` below).
- **`audioStories`** — how many stories have a real resolved `audio_url`.
  **`audioStoriesSet`** — the actual story-id list, included only when
  `0 < audioStories < 50` (the standard "omit when full or empty, list
  when partial" convention shared with `audioBooksSet`/`timingBooksSet`
  in `/dbt/<iso>/media.json`) — lets a client grey out unavailable stories
  without fetching per-story data.
- **`timingStories`** — how many stories have real per-segment timing
  from audio-sync's alignment pipeline (real, running work, currently a
  small fraction of `audioStories` — see [`catalog-obs.md`](catalog-obs.md)
  for current numbers). **`timingStoriesSet`** — the story-id list, same
  omit-when-full-or-empty convention as `audioStoriesSet`. When nonzero,
  fetch [`/obs/<iso>/timing.json`](#obsisotimingjson) below for the actual
  segment ranges.
- **`stories`** — one entry per story, keyed by 2-digit story id
  (`"01"`–`"50"`), present whenever `storyCount > 0` **for every
  language, text-only included** (not just audio-bearing ones — added
  2026-09-01 for a client's browse/category grid that needs a real title
  per story without fetching all 50 full stories itself):
  - **`title`** — the story's vernacular title (the first line of its
    door43 markdown, a standard `# Title` or `# N. Title` heading).
    Present whenever resolved. **This is the one field in this whole
    catalog family that comes from real story CONTENT, not just
    existence/routing metadata** — door43's raw content endpoint doesn't
    support HTTP `Range` requests, so getting a title means fetching each
    story's full markdown; only the first line is ever kept, the body is
    discarded immediately and never written to disk anywhere in this
    pipeline. Same "resolve display metadata, don't stage content"
    principle as [`catalog-books.json`](catalog-books.md)'s vernacular
    Bible book names — not a new category of thing this repo does, just
    OBS's version of it.
  - **`audio_url`** — door43's real release asset URL, already resolved
    (naming isn't consistent across door43 repos — done here so a client
    never has to guess it). Only present for stories with real audio.
  - **`segmentCount`** — audio-sync's own claim for how many narration
    segments that story's audio is expected to contain, when a cached
    `_obs_batches/<iso>.json` staging manifest happens to have it (purely
    optional enrichment — `null` when not available, never blocks the
    rest of the entry). Only present alongside `audio_url`.
  - A story with neither a resolved title nor audio is omitted from
    `stories` entirely, rather than included as an empty object.

## Text-only and partial-coverage languages

Most OBS languages have no audio at all — 122 of 214 as of 2026-09-01 (see
[`catalog-obs-index.json`](catalog-obs.md)'s `media` field, `"t"` vs
`"at"`). For these, `media.json` is the same shape with `audioStories`/
`timingStories` always `0`, and `stories` entries carry only `title`:

```json
{
  "iso": "am",
  "source": "Door43-Catalog",
  "source_repo": "Door43-Catalog/am_obs",
  "content_base_url": "https://git.door43.org/Door43-Catalog/am_obs/raw/tag/v4.1/content",
  "license": "CC BY-SA 4.0",
  "checking_level": "3",
  "storyCount": 50,
  "audioStories": 0,
  "timingStories": 0,
  "stories": {
    "01": {"title": "ፍጥረት"},
    "02": {"title": "ኃጢአት ወደ ዓለም ገባ"}
  }
}
```

The reverse asymmetry also happens — `awa` has 50 resolved audio tracks
but only 1 published story text (`storyCount: 1`, `audioStories: 50`,
verified directly against door43, not a resolution bug): audio and text
coverage for a language are genuinely independent facts, don't assume one
bounds the other.

17 of 122 (all older `ts-desktop`-format door43 repos) have
`checking_level: null` — that specific field has no reliable value for
this manifest format (see [`catalog-obs.md`](catalog-obs.md#fixed-gap-ts-desktop-format-repos-now-resolve-fully)
for why) — but `license`, `storyCount`, and full per-story `title`s all
resolve normally for them as of 2026-09-02.

## `collectionTitle`

The vernacular equivalent of "Open Bible Stories" itself (the collection
name, not a per-story title). **Only present for the same 17
`ts-desktop`-format languages** — checked directly whether it exists
elsewhere and it doesn't: the standard door43 layout's `content/` folder
is always exactly `01.md`–`50.md`, its manifest `title:` field is always
the fixed English string `"Open Bible Stories"` in every language (never
translated), and `README.md` is auto-generated boilerplate — genuinely
nothing to extract for the other 197 languages, not an oversight. The 17
`ts-desktop` repos have a real one at `front/title.txt`
(e.g. `ar-xzn`: `قصص حرََه من الإنجيل`) — confirmed 16 of 17 resolve it; the
17th (`ilo`) is a one-off community repo (`reymark/ilo_obs_text_story_L3`,
not one of the standard org submissions) that genuinely has no
`front/title.txt`.

## `/obs/<iso>/timing.json`

`https://cdn.bibel.wiki/obs/<iso>/timing.json`

Per-segment timing for stories audio-sync has aligned, in the same nested
`[start, end]`-pair shape [`/dbt/<iso>/timing/<BOOK>.json`](README.md)
already uses — `story` in place of `chapter`, `segment` in place of
`verse`. Deliberately the same shape as an explicit client ask: a direct
drop-in for existing `loadBookTiming()`-style client code, just pointed at
a different endpoint.

```json
{
  "iso": "ahr",
  "01": {
    "1": [5.0, 18.04],
    "2": [18.04, 31.68]
  }
}
```

`end` is the next segment's start; the last segment's own `end` equals its
own `start` — same convention as DBT timing — use the audio file's real
duration for that segment's true end.

**One file per language**, not split per-story — OBS only has 50 stories
total, none of the sharding reasons that apply to DBT's much larger
book/chapter space apply here.

Source data (`align/obs/<iso>/<story>_timing.json`, a flat array of
`{story, segment, timestamp, score, source}` point timestamps — audio-sync's
real, running alignment output) is converted into this ranged shape here;
it is never republished in its original point-timestamp form.

## `media.json` vs `timing.json`: different sources, don't assume either implies the other

`/obs/<iso>/media.json` (content base URL, license, resolved per-story
audio) is resolved directly from door43 — it exists for every language in
[`catalog-obs-index.json`](catalog-obs.md), full stop, no dependency on
any other pipeline's pace. `/obs/<iso>/timing.json` depends entirely on
audio-sync's real, ongoing alignment work (`align/obs/`) and will
genuinely lag — most languages don't have it yet. **A language can have
`media.json` without `timing.json` (the common case today), but never the
reverse** (timing without media.json would be a bug, not an expected
state, given media.json's unconditional coverage). Check `media.json`'s
own `timingStories` field before assuming `timing.json` exists.

This wasn't always true — `media.json`'s audio detail used to depend on
audio-sync's `_obs_batches/` staging pace too, which caused a real gap
(13 languages with live timing data were invisible to `media.json`,
fixed 2026-09-01 — see [`catalog-obs.md`](catalog-obs.md#source-of-truth-door43s-own-catalog-not-audio-syncs-staging-tree)
for the full story). Noted here in case older client code assumed the two
files could go missing independently in either direction.

## Fetching a story's text

Neither format is re-hosted here — always fetch live from door43 via
`content_base_url`, keyed by `contentLayout`. Both are small; the only
real difference is request count (1 fetch for `"md"`, roughly 8-18 for
`"ts-desktop"`, since that layout splits a story into one file per
paragraph instead of one file per story).

**`"md"` (197 of 214 languages)** — one file per story, already
markdown, done:

```js
async function fetchStandardStory(mediaJson, storyId) {
  const url = `${mediaJson.content_base_url}/${storyId}.md`;
  return await (await fetch(url)).text();
  // "# 1. Title\n\n![OBS Image](...)\n\nParagraph...\n\n...\n\n_Reference line_"
}
```

**`"ts-desktop"` (17 of 214 languages)** — one file per paragraph
(`<content_base_url><storyId>/<NN>.txt`), plus a separate `title.txt` and
`reference.txt`. No listing API needed — fetch chunks sequentially until
one 404s:

```js
async function fetchTsDesktopStory(mediaJson, storyId) {
  const base = `${mediaJson.content_base_url}${storyId}/`;
  const get = (name) => fetch(base + name).then(r => r.ok ? r.text() : null);

  const title = await get("title.txt");
  const paragraphs = [];
  for (let n = 1; ; n++) {
    const text = await get(String(n).padStart(2, "0") + ".txt");
    if (text === null) break;
    paragraphs.push(text);
  }
  const reference = await get("reference.txt");

  return { title, paragraphs, reference };
}
```

No per-paragraph image URLs in this layout (unlike `"md"`'s inline
`![OBS Image](...)`) — not stored anywhere per-chunk. OBS artwork is
shared across every translation of a story (same numbered images,
regardless of language), so a client that wants pictures for a
`"ts-desktop"` story can still build the standard URL pattern itself:
`https://cdn.door43.org/obs/jpg/360px/obs-en-<NN>-<CC>.jpg` (`NN` = story
id, `CC` = paragraph number, both zero-padded) — the same images the
`"md"` layout's inline markdown already points at.

## What's not here

- **Story text.** Fetch it live from door43, per `contentLayout` above —
  this repo doesn't re-host OBS text. `stories[storyId].title` and
  `collectionTitle` are the two deliberate exceptions (single lines, not
  full stories), see above.
