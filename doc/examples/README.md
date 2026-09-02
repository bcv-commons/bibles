# Examples

Small, runnable scripts showing how to actually pull content from each
source — pick Python or JavaScript, whichever you're more comfortable
with. None of them need any packages installed: Python uses only the
standard library, JavaScript uses the built-in `fetch()` (works in Node
18+ and in any browser).

```bash
python3 fetch_catalog_index.py spa       # or: node fetch_catalog_index.js spa
```

## What's here

| Script | What it does | Needs a key? |
|---|---|---|
| `fetch_catalog_index` | Look up what's available for a language | No |
| `fetch_catalog_overlap` | See the distinct options for a language, and the recommended default | No |
| `fetch_helloao` | Fetch a chapter of readable text from helloAO | No |
| `fetch_dbt` | Fetch a chapter of readable text from DBT | **Yes** — your own [Bible Brain API key](https://www.faithcomesbyhearing.com/bible-brain) |
| `fetch_pkf` | Fetch a language's `.pkf` file | No, but see below |
| `fetch_obs` | Fetch an OBS story (Open Bible Stories), either `contentLayout` | No |

Try them against `spa` (Spanish) or `aai` (Arifama-Miniafia) — both used
as examples throughout the rest of `doc/`. For `fetch_obs`, try `ahr`
(standard layout, has audio) or `am` (standard layout, text-only) —
`node fetch_obs.js ahr` / `python3 fetch_obs.py ahr`.

## PKF needs one more step

A `.pkf` file isn't plain text — it's a compressed Proskomma "succinct
docSet". `fetch_pkf` only downloads it; to turn it into readable text,
decode it with the real, working decoder already in this repo:

```bash
node fetch_pkf.js aai
node ../../tools/pkf-decode/decode.mjs aai.pkf --out out/ --book REV
```

That decode step is Node-only — there's no practical Python equivalent
(it needs the Proskomma engine).

## Want more detail than these examples show?

These scripts are deliberately minimal — just enough to see real output
quickly. For the full picture:

- **[`../sources.md`](../sources.md)** — what DBT/PKF/helloAO each are, their
  full API shapes, and the priority rule these examples' catalog lookups
  are built on.
- **[`../catalog-index.md`](../catalog-index.md)** — the full row format
  `fetch_catalog_index` is reading.
- **[`../catalog-overlap.md`](../catalog-overlap.md)** — the full cluster
  format `fetch_catalog_overlap` is reading, including what `likely` /
  `closest` mean and how the taxonomy is derived.
