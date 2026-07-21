# pipeline/

The publish pipeline behind this repo — generates and publishes to
`cdn.bibel.wiki` (Cloudflare R2). Not needed to *use* the published data;
see [`../doc/README.md`](../doc/README.md) for that.

Extracted from `bible-story-builder` (MONO) as part of a three-way repo
split; see `internal-docs/` in MONO for the split design docs.

## Layout

- **`core/`** — the original CDN-generation pipeline: versification
  scheme/fingerprint generation, `media.json`/timing metadata, the
  DBT↔helloAO id crosswalk, audio-sync alignment pull
  (`pull_align_cache.py`), and CDN publishing (`publish-dbt.sh`).
- **`comparison/`** — the routine, re-runnable PKF/DBT/helloAO
  version-identity comparison pipeline: fetches, char-/word-level text
  comparison, and the two generators that produce `catalog-index.json` /
  `catalog-overlap.json` (see `../doc/`).
- **`research/`** — investigative/diagnostic tooling built to answer a
  specific question once (why isn't this score 1.0, does DBT actually
  have text for this language) — not meant for routine re-running the way
  `comparison/` is. `comparison/` imports from here (`confirm_text_availability.py`'s
  `fetch_catalog`), so `research/` isn't purely downstream of `comparison/`.
- **`paths.py`** — shared path constants all three of the above import
  from, instead of hardcoding `data/`/`internal-data/`/`export/` string
  literals in each script. See its module docstring for the
  tracked-vs-gitignored rationale.

## An undocumented external dependency worth knowing about

`generate_audio_metadata.py`, `fingerprint_versification.py`, and
`generate_version_info.py` all **read** `export/ALL-langs/` (and
`generate_audio_metadata.py` also reads `export/ALL-langs-compact.json`).
Nothing in this repo produces that directory — it's an upstream export
from MONO's own "export-stories" step (see the `[ERROR] export/ALL-langs
not found. Run export-stories first.` message in
`generate_audio_metadata.py` if it's missing). It must already exist
before running `make dbt-metadata`; this repo doesn't fetch or generate it.

## Running it

```bash
make dbt-metadata     # generate all CDN artifacts into export/
make publish-dbt      # upload export/ to cdn.bibel.wiki (incremental delta)
make publish-dbt-dry  # dry-run (no writes)
make align-pull       # pull new audio-sync alignment output (see below)
make help             # full target list
```

(`make` targets live in the repo-root `Makefile` and invoke scripts under
`pipeline/` — always run `make` from the repo root, not from inside
`pipeline/`.)

The `catalog-index.json`/`catalog-overlap.json` generators aren't wired
into `make dbt-metadata` yet — run them directly:

```bash
.venv/bin/python pipeline/comparison/generate_catalog_index.py
.venv/bin/python pipeline/comparison/generate_catalog_overlap.py
```

## Configuration

Copy `.env` from a sibling repo publishing to the same R2 bucket (or your
own credentials) with:

- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`
  (Cloudflare R2 — `pipeline/core/publish-dbt.sh` and
  `pipeline/core/pull_align_cache.py` use `rclone` against this)
- `BIBLE_API_KEY` — DBT (Bible Brain, Digital Bible Platform, by Faith
  Comes By Hearing), for `fingerprint_versification.py`'s text probes
