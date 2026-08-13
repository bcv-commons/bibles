# `catalog-audio.json`

`https://cdn.bibel.wiki/catalog/audio.json`

DBT's own audio fileset routing, compact and per-version — "given a DBT
`(iso, distinct_id, canon)`, which fileset id(s) actually carry its
audio, and at what bitrate/codec." Companion file:
[`catalog-text.md`](catalog-text.md) (same source, same shape, text
instead of audio) — read that page for the shared conventions (grouping,
canon-uncertainty, id encoding) not repeated in full here.

DBT-only, single-source, structural existence only — this file does
**not** claim anything about confirmed timing/alignment quality. "Does
this fileset actually have real, usable per-verse timing" is a
different, stronger question this file does not answer — that answer
lives in `/dbt/<iso>/media.json` (`timingBooks`), sourced from real
alignment work (audio-sync), not from DBT's own catalog metadata. See
`variant.dbtTiming` below for DBT's own (weaker, unverified) claim,
which this file does publish, clearly separated from that confirmed
answer.

## Shape

```json
{"entries":{
"aaa:nt":{"AAAMLT":[
{"id":"a:N1DA","br":64,"c":"mp3","dbtTiming":"mms_align"},
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
(`AAAMLT`'s `a:N1DA` variant really does carry `dbtTiming` in the live
data — the other three variants shown genuinely don't, illustrating that
this is a real per-variant split, not something every variant of a
version carries uniformly.)
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
  — real, not rare, not a corner case worth coding around (see `lid:nt`'s
  `LIDWBT` above, a real case). Exact prevalence isn't quoted here since
  it drifts with every catalog refresh — count `br`-less variants in the
  live file yourself if you need a current figure.
- **`variant.c`** — codec (`"mp3"`, `"opus"`), lowercased. Also omitted
  when blank in the source data.
- **`variant.dbtTiming`** — DBT's own catalog-level claim that this
  specific fileset has verse-level audio timing, passed through
  **verbatim** from DBT's raw `timing_est_err` field. **Omitted** when
  DBT's catalog has no such claim for this fileset — the common case,
  not the exception (most audio variants don't carry it). As with `br`
  above, treat the exact share as something to compute from the live
  file, not a number pinned here — it moves every time DBT's catalog is
  refetched.

  This is deliberately named and documented to avoid the confusion
  `doc/catalog-audio.md` used to warn about before this field existed:
  **`dbtTiming` is DBT's own unverified catalog claim, not a confirmed
  answer.** The confirmed answer — "does this fileset actually have
  real, working per-verse timing we've checked" — is
  `/dbt/<iso>/media.json`'s `timingBooks`, sourced from real alignment
  work. Don't substitute one for the other.

  Only one of the four real observed values is confidently understood:
  `"mms_align"` (near-certainly forced-alignment via an MMS —
  Massively Multilingual Speech — model), which accounts for the
  majority of variants that carry this field. The other three real
  values — `"4"`, `"0"`, `"5"` — are passed through as-is; their exact
  meaning (an error/confidence bucket? an alternate method id?) isn't
  documented anywhere DBT publishes, and isn't guessed at here. Treat
  any value's mere *presence* as "DBT claims some form of timing
  exists for this fileset," and don't read more into the specific
  string than that until DBT's own meaning is confirmed.

Every real variant is listed (bitrate/format alternatives of the same
recording, and genuinely different recordings — e.g. standard narration
vs. dramatized — both show up as separate variants with their own ids;
this file doesn't try to guess which one a client "should" want). Unlike
`catalog-text.json`'s `fmt` field, `id` is not deliberately deduplicated
here — if the exact same audio id were ever found with two different
`br`/`c`/`dbtTiming` values (a genuine anomaly, not the same "one id, two
catalog tags" pattern text has), the generator flags it as a warning
rather than silently merging or dropping data. None found as of this
writing — check the generator's own stderr output on any given run for
the current state, rather than assuming that holds indefinitely.
