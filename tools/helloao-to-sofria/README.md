# helloAO → Sofria: two client sample solutions

helloAO (`bible.helloao.org`) is the one source this repo tracks with no
USFM available at all — every real translation reports
`availableFormats: ["json"]` only. So getting from helloAO's own JSON to
Sofria always starts with a bespoke JSON→JSON mapping
(`helloao_to_usj.mjs`, a JS port of `pipeline/core/helloao_to_usj.py`,
producing USJ — Unified Scripture JSON). This directory offers two
different ways to take that USJ the rest of the way to Sofria:

- **`via-usj.mjs`** — hands the USJ to real `proskomma-core`
  (`pk.importDocument(..., 'usj', ...)` → `doc.sofria(chapter)`). Always
  correct by construction, since it's the real library. Also writes out
  the intermediate USJ file, which is independently useful on its own
  (portable to any other USJ-consuming tool).
- **`via-native.mjs`** — hand-built, **zero dependencies**, no
  `proskomma-core` at all. Reproduces the same block/wrapper/mark
  structure by hand, reverse-engineered directly from real Proskomma
  output (not from any spec document).

Both reuse the same `helloao_to_usj.mjs` mapping module — the only real
difference is the last step: hand the USJ to a real library, or render it
by hand.

## Usage

```
node via-usj.mjs    <helloAO-complete.json> <out-dir>   # writes out-dir/usj/ and out-dir/sofria/
node via-native.mjs <helloAO-complete.json> <out-dir>   # writes out-dir/sofria/ only
```

`<helloAO-complete.json>` is the response from
`https://bible.helloao.org/api/<translationId>/complete.json` (one fetch
per translation gets every book/chapter — see
`pipeline/core/generate_helloao_usj.py`'s docstring for why that endpoint
is used instead of one request per chapter).

## `via-native.mjs`'s accuracy, and its one known gap

Verified against real `proskomma-core@0.11.3` output across three full
translations (BSB, AAB, ARBNAV — 3,567 chapters total, 2026-09-19):

| Translation | Chapters identical to real Proskomma output |
|---|---|
| ARBNAV | 1189 / 1189 (100%) |
| BSB | 1178 / 1189 (99.1%) |
| AAB | 1177 / 1189 (99.0%) |

Getting there took several real, confirmed-against-live-output fixes to
`usj_to_sofria_native.mjs` (documented inline in that file, and in
`internal-docs/pkf-encode-decode-bugs-found.md` #8 for the one shared
`proskomma-core` USJ-import bug found along the way): a verse's "open"
state persisting across paragraph-block boundaries (blank lines, poetry
line breaks), a stranded verse-label correction pass, dropping
scaffolding-only blocks, and merging adjacent plain-text fragments the
way Proskomma's own renderer does.

**One known, precisely-characterized gap remains** (all non-matching
chapters across all three translations share this exact signature, no
exceptions found): when a chapter's leading content is *entirely*
heading(s) — optionally followed by a blank line — before its first
verse marker, real Proskomma's chapter-scoped `doc.sofria(undefined, N)`
export silently drops that leading heading material when extracting one
chapter out of an imported whole book. `via-native.mjs` keeps it (since
it renders each chapter independently and has no reason to drop content
that's genuinely part of that chapter). This shows up almost entirely in
poetic books (Psalms, Song of Songs, Proverbs) whose per-chapter
super-title is the very first thing in the chapter — 11-12 chapters out
of 1189 in each translation checked.

This is not a general defect in the block/wrapper walk — it's one
specific, narrow trigger condition, not chased further given the
diminishing signal (every other non-1.0 case that looked like a genuine
new pattern turned out, on inspection, to share the exact same root
cause). Treat `via-native.mjs`'s output for a chapter matching that
pattern as missing its opening heading; everything else about it
(including the rest of that same chapter's content) is real,
byte-verified-correct Sofria.

## Which one to use

- Already have `proskomma-core` available (or don't mind the dependency)?
  Use `via-usj.mjs` — it's the real library, always correct.
- Want zero dependencies, and the leading-heading gap above is
  acceptable (or you post-process to patch it in)? Use `via-native.mjs`.
- Either way: clients will receive Sofria produced by *both* code paths
  in real usage (this repo's own server-side pipeline uses the
  `proskomma-core` path — see `tools/usj-to-sofria/`), so any Sofria
  consumer you build should be written against real Proskomma-shaped
  output regardless of which example you start from here.
