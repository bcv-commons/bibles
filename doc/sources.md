# The four sources

## DBT (Bible Brain, Digital Bible Platform, by Faith Comes By Hearing)

The largest catalog by far, and the only source with **broad, catalog-wide**
published audio (thousands of versions). Real-time API, no bulk download.

- Catalog: `https://cdn.bibel.wiki/dbt/_catalog.json` — one row per
  `[iso, distinct_id, canon, ...tags]`. `canon` is `nt`/`ntp`/`ot`/`otp`
  (`p` suffix = Portions, i.e. partial coverage — the same convention
  `catalog-index.json` reuses directly). Tags are `a:`/`A:` (audio) and
  `t:`/`T:` (text); lowercase means "append to the distinct_id to get the
  fileset id", uppercase means "this is the full fileset id already".
- Fetching actual verse text/audio requires a DBT API key against
  `https://4.dbt.io/api/...` — this repo doesn't proxy that; you'd need
  your own DBT API access to pull content directly, or read the metadata
  this repo already publishes (timing, media availability) under
  `/dbt/<iso>/`.
- **A text fileset's own response can be one of two real, different
  shapes — check `type` before assuming plain text.** Most editions
  return `{"type": "verses", "data": [...]}` (per-verse inline text,
  the common case). Some — real fileset ids carry a telltale `-json`
  suffix, e.g. `ADXNVSO_ET-json` (Tibetan) — return
  `{"type": "path", "data": <signed CDN URL>}` instead: the downloaded
  document at that URL is a raw, UNCOMPRESSED Proskomma **Sofria** JSON
  document (`schema.constraints[].name == "sofria"`), **not** plain
  text, **not** USFM, and **not** a `.pkf` succinct docSet either —
  same real engine family as PKF's `.pkf` (see below), genuinely
  different wire format. Confirmed via a real client report
  (audio-sync, 2026-10-02): treating this JSON as line-per-verse plain
  text — the trap its own telltale `-json`-suffixed id invites — feeds
  a ~29,000-character blob into a single "verse," which crashed a
  downstream forced-alignment call. Use
  **[`tools/dbt-sofria-decode-py/`](../tools/dbt-sofria-decode-py/)**
  - Availability (checked 2026-10-06, John 3 across all 1,305 `-json` filesets): 1,015 return Sofria; 286 lack the book (404); 4 are blocked by key permissions. Plain text shares the same key permissions for these filesets, apart from one Sofria-only download refusal.
  (in this repo) to extract real plain verse text from it — same spirit
  as `tools/pkf-decode/`, deliberately minimal (verse text only, skips
  grafts entirely). For anything beyond plain text (tables, milestones,
  real rendering), the authoritative reference is
  [`proskomma-json-tools`'s `SofriaRenderFromJson.js`](https://github.com/Proskomma/proskomma-json-tools/blob/main/src/render/renderers/SofriaRenderFromJson.js).

## PKF (published by `se-regional-pwa`, at `cdn.bibel.wiki/pkf/`)

- Manifest: `https://cdn.bibel.wiki/pkf/manifest.json` — per-language
  `collections[]`, each with a `.pkf` filename and a `catalog` filename.
- **A `.pkf` file is a gzip-compressed Proskomma "succinct docSet"** — not
  plain text, not USFM directly. Use **[`tools/pkf-decode/`](../tools/pkf-decode/)**
  (in this repo) to turn it into readable USFM.
- No API key needed to fetch the `.pkf`/`manifest.json` files themselves.
- Per-language `app-config.json` carries a `copyright` block
  (`CC-BY-NC-ND-4.0` / `CC-BY-4.0` / Public Domain, varies per language) —
  check it before redistributing decoded text.
- A real timing/audio endpoint exists per language:
  `<iso>/timing/<BOOK>-<chapter>.json`.

## helloAO (`bible.helloao.org`)

- Catalog: `https://bible.helloao.org/api/available_translations.json` —
  flat list, no API key, no documented rate limit.
- Per-chapter content: `https://bible.helloao.org/api/<id>/<BOOK>/<chapter>.json`
  — structured JSON (verses, headings, footnotes as typed blocks), not
  USFM. Straightforward to extract plain text from directly.
- Per-translation book list: `https://bible.helloao.org/api/<id>/books.json`
  — use this to check exactly which books a translation actually has
  before assuming coverage from a book count alone.
- **Has real published audio for one edition: `BSB`** (Berean Standard
  Bible), three narrators (`david`/`hays`/`souer`), verified directly
  (2026-08-14) via `thisChapterAudioLinks`/`nextChapterAudioLinks` on the
  per-chapter endpoint — e.g.
  `https://audio.bible.helloao.org/api/BSB/GEN/1/audio/hays.mp3`. Checked
  across a random sample of ~40 other translations (English and non-English)
  and found audio on none of them — this is not a general helloAO
  capability, it's one specific attached recording. `AAB` ("Accessible
  Ancients Bible", helloAO's own edition) also *reports* audio links, but
  they resolve to the same `/api/BSB/...` URLs — there is exactly one real
  audio production in helloAO's system, not two. No per-verse timing
  accompanies it (`thisChapterAudioTimings` is present in the response
  shape but empty on every chapter checked). Not currently cataloged
  anywhere this repo publishes — see
  `internal-docs/catalog-audio-ownership-architecture.md` §8 for the
  scoping notes on adding it.

## openbible (Biblica's Open Bible catalog, `openbible-api-1.biblica.com`)

Added 2026-09-16. A real, independent Spring Data REST catalog — 943
projects (554 text, 357 audio, 32 video as of the initial fetch), not the
same thing as `yaapi.bible` (a smaller, curated, text-only subset of this
same underlying catalog).

- Project catalog: `https://openbible-api-1.biblica.com/projects`
  (paginated, `?page=N&size=100`) — each project has `languageCode` (real
  ISO 639-3), `languageName`, `type` (`"text"`/`"audio"`/`"video"`),
  `title`/`titleEnglish`, `scope`, `disabled`.
- Per-project versions: `/projects/{id}/versions` — **the version objects
  here carry no `_links` at all** (confirmed live, unlike the flat
  `/versions` collection) — don't rely on a `_links.artifacts.href`;
  construct `/versions/{id}/artifacts` directly from the version id
  instead.
- Real content download: `/artifactContent/{artifactId}` — direct,
  no-auth, CloudFront-served. **Audio** artifacts are per-BOOK zips (one
  MP3 per chapter inside). **Text** artifacts are per-EDITION zips (the
  whole Bible in one zip, one `.usfm`/`.usx` file per book inside) —
  genuinely different granularity from audio, confirmed by inspection.
  Real per-verse **Timing** artifacts also exist for some audio versions
  (a marker-track export, `label<TAB>HH:MM:SS,fraction` per line, one
  `.txt` per chapter inside a whole-edition zip) — different shape from
  DBT's own timing JSON, not yet consumed by anything this repo publishes.
- **Per-chapter text access**: `doc/openbible-chapters.md` — a derived,
  CDN-published per-chapter endpoint (390 of Biblica's 452 yaapi.bible-
  covered editions, non-ND-only), built as a caching layer in front of
  [`yaapi.bible`](https://yaapi.bible/)'s own real per-verse API rather
  than a second USFM extraction pipeline. Use this instead of the raw
  whole-edition zips for any client that just wants readable text.
- **Licensing is real and mixed, not uniformly "open"** — every version
  carries a real `licenses[]` field; roughly a third of both audio and
  text editions carry an NC and/or ND clause. NC is fine to use (with
  attribution); ND specifically blocks any *derivative* work (e.g.
  extracting a whole-edition text zip's per-book files and republishing
  them individually) — check the license on the specific edition before
  assuming otherwise.
- This repo maintains a persistent local cache of current-version text
  USFM zips (`internal-data/api-cache/openbible/text-zips/`, ~380MB) —
  fetched once, reused for both book-coverage classification and text
  comparison, rather than re-fetched per use.
- Text-identity comparison against DBT/PKF/helloAO uses the exact same
  algorithm as the PKF/DBT comparison work (`compare_pkf_dbt.py`'s
  char-level, homoglyph-corrected comparator) — real USFM, no new parsing
  logic needed. Three additional structural-marker bugs were found and
  fixed via this comparison (`\cl`, `\r`, `\ms`/`\ms1`/`\ms2` — see that
  script's history for detail).

## eBible.org (editions `bibles` republishes, `e`)

Added 2026-10-15. eBible.org publishes clean USFM zips per translation
(`https://eBible.org/Scriptures/<translationId>_usfm.zip`), most of which helloAO
already carries. `generate_ebible_chapters.py` republishes the rest, as book USJ under
`export/ebible-usj/<iso>/<translationId>/`, when all three hold:

- helloAO doesn't carry it (helloAO links its eBible sources as
  `details.php?id=<translationId>`; a few, such as BSB, link elsewhere and are listed in
  the script);
- the edition's copyright page gives Public Domain, CC0 or a Creative Commons licence
  without No Derivatives (eBible's own `Redistributable` flag alone also lets through ND
  and "All rights reserved" editions);
- its text isn't already reachable from another source: compared before publishing
  (letters-only similarity of sample chapters, 0.95 or more = same text), never assumed.
  The first run (2026-10-15) found 11 such duplicates, e.g. hltmcsb = helloAO
  `hlt_mcs`, eka = openbible EKA, spabll = audiobiblia BLL.

That gave 12 editions, published as book USJ and (since 2026-10-26) per-chapter Sofria on
`cdn.bibel.wiki/ebible/`; every verse reads the same from both (route parity, 8,774
chapters). In the catalogs they're the `e` source; their relationships to the
other sources (e.g. the Open English Bible's two spelling editions, `e:engoebus` and
`e:engoebcw`, `orthography_convention` of each other) come from the same text comparison
as every other source's.

## CrossWire (SWORD modules `bibles` republishes, `c`)

Added 2026-10-21. CrossWire's main module repository
(`https://www.crosswire.org/sword/modules/`) has 276 Bible texts, as SWORD modules: a
`.conf` per module (in `mods.d.tar.gz`) and a zip of the module data. Read with `pysword`
(pure Python). `generate_crosswire_usj.py` republishes a module, as book USJ under
`export/crosswire-usj/<iso>/<module>/` and per-chapter Sofria, on `cdn.bibel.wiki/crosswire/`,
when all of these hold:

- its conf's `DistributionLicense` is Public Domain or a Creative Commons licence without
  NC or ND. "Permission to distribute granted to CrossWire" and non-commercial licences
  are not republishable (most of the rest);
- its text is plain, or OSIS with only the elements the script maps to USFM (paragraphs,
  poetry lines, Psalm titles, acrostic headings, footnotes and cross-references, added words,
  words of Jesus). Anything else stops the module, so nothing leaks into verse text;
- its text isn't already reachable from another source: sample chapters compared,
  letters only, with every edition in the language from helloAO, DBT and our own
  openbible / audiobiblia / eBible USJ (0.95 or more = same text, skipped and recorded),
  unless the module has more books than the edition it matches. Then it is published with
  the match in its `_meta.json` (`same_text_as`).

The modules are listed in the script with the iso we catalog them under, since a conf's
`Lang` is a BCP 47 tag that is sometimes a macrolanguage or plain wrong (`el` -> ell;
`mlf` for Malayalam). Every verse is checked against an independent reading of the OSIS
(notes, titles and colophons removed), and USJ against Sofria (route parity).

Published (2026-10-21), 15 editions:

| edition | language | what | books |
|---|---|---|---|
| `c:GreVamvas` | ell, modern Greek | Vamvas, 1850 | 66 |
| `c:ArmEastern` | hye, Eastern Armenian | Eastern Armenian Bible | 6 |
| `c:ArmWestern` | hyw, Western Armenian | NT, 1853 | 27 |
| `c:LvGluck8` | lvs, Latvian | Glück, 8th edition | 66 |
| `c:SloStritar` | slv, Slovenian | Stritar NT and Psalms, 1882 | 28 |
| `c:KswSKMB` | ksw, S'gaw Karen | Mason Bible, 1853 (USJ only, see below) | 66 |
| `c:Peshitta` | syc, Classical Syriac | Peshitta NT | 27 |
| `c:CSlElizabeth` | chu, Church Slavonic | Elizabeth Bible, 1757 | 76 |
| `c:Wycliffe` | eng (Middle English) | Wycliffe, c.1395 | 76 |
| `c:ScotsGaelic` | gla, Scottish Gaelic | Mark | 1 |
| `c:ManxGaelic` | glv, Manx | portions | 5 |
| `c:PotLykins` | pot, Potawatomi | Matthew and Acts, 1833 | 2 |
| `c:Calo` | rmq, Caló | Luke | 1 |
| `c:vlsJoNT` | vls, West Flemish | De Jonge NT | 27 |
| `c:KLV` | tlh, Klingon | from the World English Bible | 66 |

- **GreVamvas**: before it, the only modern Greek text we reached was DBT's ELLELL (Spyros
  Filos, 1994, plain text only); the two are distinct translations (0.71 on REV 15, 0.63 on
  PSA 117).
- **Wycliffe** is Middle English, filed under `eng` next to helloAO's `eng_w88`: the same
  text (1.0 on Genesis 1 and Matthew 1), but helloAO has only 9 of its 76 books.
- **KswSKMB** is USJ only. S'gaw Karen writes phrases without spaces, and proskomma (which
  builds our Sofria) cuts a "word" at 255 bytes, so 491 chapters lost letters in Sofria.
- **Wulfila** (Gothic) is not published: its verses hold several manuscript readings side
  by side (`seg type=rdg`) and editorial `<...>` brackets in the text, so there is no single
  text without choosing a manuscript.
- Left out of verse text: colophons (SloStritar, 14), a testament heading (SloStritar
  "Nova zaveza") and CSlElizabeth's LXX sub-verse numbers. Extra verses in an edition's own
  numbering (vlsJoNT John 1:52) are kept as their own verses.

## Door43 (aligned Bibles `bibles` republishes, `g`)

Added 2026-10-22. lexeme-aligner's `full-alignments-manual-sa` dataset publishes the word
alignments Door43's translators made in nine Gateway Language texts. Its files are named by
the text fingerprint of each book's verse text, so a client needs exactly that text to use
them. `generate_door43_usj.py` republishes those texts as book USJ under
`export/door43-usj/<iso>/<repo>/` and per-chapter Sofria, on `cdn.bibel.wiki/door43/`, each
pinned to the commit that was aligned (`_meta.json` `door43.commit`). CC BY-SA 4.0
(each repo's `LICENSE.md`).

| edition | language | Door43 repo | books |
|---|---|---|---|
| `g:hi_glt` | hin, Hindi | Door43-Catalog/hi_glt | 27 |
| `g:bn_gst` | ben, Bengali | Door43-Catalog/bn_gst | 15 |
| `g:gu_glt` | guj, Gujarati | Door43-Catalog/gu_glt | 21 |
| `g:kn_glt` | kan, Kannada | Door43-Catalog/kn_glt | 23 |
| `g:mr_glt` | mar, Marathi | Door43-Catalog/mr_glt | 23 |
| `g:ne_glt` | npi, Nepali | Door43-Catalog/ne_glt | 29 |
| `g:or_glt` | ory, Odia | Door43-Catalog/or_glt | 23 |
| `g:te_glt` | tel, Telugu | Door43-Catalog/te_glt | 23 |
| `g:es-419_glt` | spa (Latin American Spanish) | Door43-Catalog/es-419_glt | 1 |

- **Conversion:** the alignment markup (`\zaln-s`/`\zaln-e` milestones, `\w` attributes)
  is dropped, keeping the words, and so are translationStudio leftovers: `\ts\*` and empty
  `\s5` lines. usfmtc put the verse after an empty `\s5` inside the heading, which removed
  1,317 Nepali verses from verse text.
- **Checked:** every verse against an independent reading of the USFM (39,605 verses; the 6
  differences are the check's own: a note inside a word, headings mid-line, an empty last
  verse), USJ against Sofria, and JS against Python.
- **Not duplicates**, but related: DBT's `NPIDPIN_ET`, `HINDPIO_ET`, `MARDPIO_ET` and
  `ORYDPIN_ET` score 0.85-0.97 on some chapters and 0.45-0.6 on others, i.e. other revisions;
  `g:ne_glt` is a revision of helloAO's Nepali ULB (`npi_ulb`: 0.97-0.98 in the Gospels and
  Revelation, 0.37-0.88 elsewhere). openbible's `o:HLT` ("Hindi GLT", 3 John and Titus only)
  is the same text as `g:hi_glt` on Titus 1, the one chapter they share.
- **Alignment files:** 96 of the 181 aligned books match our text fingerprint. In the others,
  lexeme-aligner's own reading of the USFM dropped zero-width joiners (U+200D/U+200C) and
  kept footnote and heading text in verses; their layers need rebuilding on this text.

## Priority (when more than one source has the same content)

```
1. pkf
2. helloao
3. dbt
4. openbible
5. ebible
6. crosswire
7. door43
```

`openbible` placed last, deliberately conservative — it's the newest
source here, with real but mixed licensing (unlike the other three, which
are either fully open or already well-understood), so it defaults to
last pick rather than displacing an existing preference. Revisit this
ordering once more real-world use has confirmed there's no reason to
prefer it lower. `ebible` (added 2026-10-15) comes after it: its editions are, by
construction, ones no other source has, so the order only matters if a later comparison
finds an overlap. `crosswire` (added 2026-10-21) and `door43` (2026-10-22) come last for the same reason.

This is the **default** `catalog-index.json`/`catalog-overlap.json` point
to when sources overlap — not a filter. Every source that has content for
a language is always listed; nothing is hidden because a higher-priority
source also has it. Pick the default if you don't have a reason to choose
otherwise; check the alternatives if you do.

## Audio

DBT is the largest source with published audio (thousands of versions,
cataloged today in `catalog-audio.json`). openbible is a real second broad
source — 357 audio-type projects, catalogued in `catalog-audio-index.json`
(existence only — no fileset-routing detail the way `catalog-audio.json`
gives for DBT). helloAO has one real edition with audio (`BSB` — see
above), not yet cataloged by this repo. A separate audio-sync pipeline
(different repo) is expected to add more over time via its own alignment
work — once it publishes, it'll be reflected here too.

Note openbible's audio republishing is explicitly **not** this repo's job
— its per-book zips aren't directly usable by a client (one zip per book,
not per chapter), so any real extraction/republishing of the actual MP3
bytes is left to audio-sync. This repo's role is limited to signaling real,
book-level-verified availability (`catalog-audio-index.json`) and pointing
at the source, same "point, don't copy" principle as everywhere else.
