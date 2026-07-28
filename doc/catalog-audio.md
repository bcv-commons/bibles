# `catalog-audio.json`

`https://cdn.bibel.wiki/dbt/_app/catalog-audio.json`

DBT's own audio fileset routing, compact and per-version — "given a DBT
`(iso, distinct_id, canon)`, which fileset id(s) actually carry its
audio, and at what bitrate/codec." Companion file:
[`catalog-text.md`](catalog-text.md) (same source, same shape, text
instead of audio) — read that page for the shared conventions (grouping,
canon-uncertainty, id encoding) not repeated in full here.

DBT-only, single-source, structural existence only — this file **never**
claims anything about confirmed timing/alignment quality. "Does this
fileset actually have real, usable per-verse timing" is a different,
stronger question this file deliberately does not answer — that answer
already lives in `/dbt/<iso>/media.json` (`timingBooks`), sourced from
real alignment work (audio-sync), not from DBT's own catalog metadata.
DBT's own catalog-level timing claim (a separate, weaker signal) isn't
republished here at all — publishing it here would risk it being
mistaken for the confirmed answer sitting in `media.json`.

## Shape

```json
{"entries":{
"aaa:nt":{"AAAMLT":[
{"id":"a:N1DA","br":64,"c":"mp3"},
{"id":"a:N1DA-opus16","br":16,"c":"opus"},
{"id":"a:N2DA","br":64,"c":"mp3"},
{"id":"a:N2DA-opus16","br":16,"c":"opus"}
]},
"lid:nt":{"LIDWBT":[
{"id":"a:N1SA","c":"mp3"},
{"id":"a:N2SA","c":"mp3"}
]}
}}
```
(`LIDWBT`'s real live entry has 7 variants total — the two shown above are
a real subset, picked specifically because they illustrate the "no `br`"
case; the other 5 all have both `br` and `c`, same shape as the `AAAMLT`
example.)

## Row format

`entries["<iso>:<canon>"]["<distinct_id>"] = [variant, ...]`

Same `iso`/`canon`/`distinct_id` conventions as
[`catalog-text.md`](catalog-text.md), and the same `a:`/`A:` id-encoding
scheme (lowercase = append to `distinct_id`, uppercase = literal id) —
just `a:`/`A:` instead of `t:`/`T:`.

- **`variant.br`** — bitrate in kbps, as a bare integer (`64`, not
  `"64kbps"`). **Omitted** when the source data has no bitrate on record
  — real, not rare: about 10% of real audio filesets have this blank
  (see `lid:nt`'s `LIDWBT` above, a real case).
- **`variant.c`** — codec (`"mp3"`, `"opus"`), lowercased. Also omitted
  when blank in the source data.

Every real variant is listed (bitrate/format alternatives of the same
recording, and genuinely different recordings — e.g. standard narration
vs. dramatized — both show up as separate variants with their own ids;
this file doesn't try to guess which one a client "should" want). Unlike
`catalog-text.json`'s `fmt` field, `id` is not deliberately deduplicated
here — if the exact same audio id were ever found with two different
`br`/`c` values (a genuine anomaly, not the same "one id, two catalog
tags" pattern text has), the generator flags it as a warning rather than
silently merging or dropping data. None found in the current build.
