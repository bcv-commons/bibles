# pipeline/

The publish pipeline behind this repo — generates and publishes to
`cdn.bibel.wiki` (Cloudflare R2). Not needed to *use* the published data;
see [`../doc/README.md`](../doc/README.md) for that.

Extracted from `bible-story-builder` (MONO) as part of a three-way repo
split; see `internal-docs/` in MONO for the split design docs.

## Layout

- **`core/`** — the CDN-generation pipeline: versification
  scheme/fingerprint generation, `media.json` (which books have timing,
  not the timing itself), the DBT↔helloAO id crosswalk, the catalogs, the
  republished sources (openbible, audiobiblia, eBible, CrossWire, Door43),
  OBS, the audio-sync index (`pull_align_manifests.py`), the DBT timing
  check (`fetch_dbt_timing_index.py`) and CDN publishing (`publish-*.sh`).
- **`comparison/`** — the routine, re-runnable PKF/DBT/helloAO
  version-identity comparison pipeline: fetches, char-/word-level text
  comparison, and the two generators that produce `catalog-index.json` /
  `catalog-overlap.json` (see `../doc/`).
- **`research/`** — investigative/diagnostic tooling built to answer a
  specific question once (why isn't this score 1.0, does DBT actually
  have text for this language) — not meant for routine re-running the way
  `comparison/` is. `comparison/` imports from here (`confirm_text_availability.py`'s
  `fetch_catalog`), so `research/` isn't purely downstream of `comparison/`.
- **`obs_iso.py`** — door43's OBS language codes to ISO 639-3
  (`data/obs-iso-639-1.toml`).
- **`paths.py`** — shared path constants all three of the above import
  from, instead of hardcoding `data/`/`internal-data/`/`export/` string
  literals in each script. See its module docstring for the
  tracked-vs-gitignored rationale.

## External dependencies worth knowing about

`generate_audio_metadata.py` no longer depends on MONO's `export/ALL-langs/`
export (migrated 2026-09-12 to discover DBT filesets live from
`internal-data/sorted/BB`, itself derived from `internal-data/api-cache/`
via `sort-dbt-catalog` — run `make fetch-dbt-catalog sort-dbt-catalog`
first if that directory is missing or stale). `fingerprint_versification.py`
and `generate_version_info.py` still read `export/ALL-langs/` — that
migration hasn't reached them yet.

bibles publishes no timing. `media.json` says which books have it, from
three local indexes:

- `internal-data/pkf-audio-index.json`: PKF's audio and timing, from
  `pkf/<iso>/info.json` on the CDN (`make fetch-pkf-audio`, also part of
  `make dbt-metadata`; no key): the DBT filesets PKF timed (it also orders
  each edition's `a` list, the filesets PKF uses first), and PKF's own
  audio, which becomes each language's `<ISO>PKF` edition.
- `internal-data/align-index.json`: audio-sync's timing, from a listing of
  `align/` on the CDN (`make align-pull`, also part of `make dbt-metadata`
  and `make obs-metadata`). It also pulls audio-sync's `align/_runs/`
  manifests and writes what they and the listing disagree on to
  `internal-data/align-mismatch.json`, to send to audio-sync.
- `internal-data/dbt-timing-index.json`: DBT's own timing, one probe per
  testament (`make fetch-dbt-timing`, run by hand, like `make cache`).

See `doc/dbt-timing.md` for the URLs clients use to fetch timing.

## Running it

```bash
make dbt-metadata     # generate all CDN artifacts into export/
make publish-dbt      # upload export/ to cdn.bibel.wiki (incremental delta)
make publish-dbt-dry  # dry-run (no writes)
make publish-catalog  # upload export/catalog/ (also: publish-obs, publish-ebible, ...)
make align-pull       # index audio-sync's align/ (also runs inside dbt-metadata)
make fetch-dbt-timing # check which DBT filesets have DBT timing (by hand)
make cleanup-dbt-dry  # list CDN files under dbt/ that export/ no longer has
make help             # full target list
```

(`make` targets live in the repo-root `Makefile` and invoke scripts under
`pipeline/` — always run `make` from the repo root, not from inside
`pipeline/`.)

The `catalog-index.json`/`catalog-overlap.json` generators aren't wired
into `make dbt-metadata` yet — run them directly, in this order (the comparison
steps are resumable and only redo what's new or failed):

```bash
.venv/bin/python pipeline/comparison/compare_all.py                         # nt (REV 15)
.venv/bin/python pipeline/comparison/compare_all.py --book PSA --chapter 117 # ot
.venv/bin/python pipeline/comparison/confirm_identical.py  # re-check every 1.0 pair on more chapters
.venv/bin/python pipeline/research/diagnose_all.py
.venv/bin/python pipeline/comparison/generate_catalog_index.py
.venv/bin/python pipeline/comparison/generate_catalog_overlap.py
```

`confirm_identical.py` must run after any `compare_all.py` run: a recompared group loses
its confirmations, and an unconfirmed 1.0 would be clustered as identical on one chapter.

## Configuration

Copy `.env` from a sibling repo publishing to the same R2 bucket (or your
own credentials) with:

- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`
  (Cloudflare R2 — `pipeline/core/publish-dbt.sh` and
  `pipeline/core/pull_align_manifests.py` use `rclone` against this)
- `BIBLE_API_KEY` — DBT (Bible Brain, Digital Bible Platform, by Faith
  Comes By Hearing), for `fingerprint_versification.py`'s text probes,
  `fetch-dbt-catalog` and `fetch_dbt_timing_index.py`
