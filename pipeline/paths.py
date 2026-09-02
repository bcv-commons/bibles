"""Central path constants for the bibles pipeline.

Every script that touches the filesystem should import its paths from here
instead of hardcoding "data/...", "internal-data/...", "export/..." string
literals directly. Two things this buys:

1. The tracked-vs-gitignored split is enforced from one place. `data/` is
   real, hand-curated source data (checked into git); `internal-data/` is
   fetched/rebuildable/computed working data (entirely gitignored). A
   script that imports DATA vs INTERNAL_DATA from here can't accidentally
   blur that line the way a bare Path("data/...") string could.
2. Every path is resolved from this file's own location (REPO_ROOT),
   not from wherever `python3` happened to be invoked from — scripts work
   regardless of CWD, not just when run from the repo root by convention.

Only ROOT anchors and filenames genuinely shared across more than one
script are centralized here. A script's own output filename that nothing
else reads is fine to keep as a local `NAME = INTERNAL_DATA / "foo.json"`
constant in that script — the point is never hardcoding the "data/" /
"internal-data/" / "export/" prefix itself, not eliminating every local
filename choice.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Tracked source data — real, hand-curated, checked into git.
# ---------------------------------------------------------------------------
DATA = REPO_ROOT / "data"
VRS_DIR = DATA / "vrs"
VERSION_EXCLUDE_FILE = DATA / "version-exclude.toml"
HELLOAO_AUDIO_FILE = DATA / "helloao-audio.toml"
OBS_ISO_MAP_FILE = DATA / "obs-iso-639-1.toml"

# ---------------------------------------------------------------------------
# Internal working data — entirely gitignored, entirely rebuildable
# (fetched from DBT/PKF/helloAO APIs, or computed by the comparison
# pipeline). Nothing under here is hand-authored.
# ---------------------------------------------------------------------------
INTERNAL_DATA = REPO_ROOT / "internal-data"

API_CACHE = INTERNAL_DATA / "api-cache"
SORTED_DIR = INTERNAL_DATA / "sorted" / "BB"
PKF_BOOKS_CACHE = API_CACHE / "pkf-books"
HELLOAO_BOOKS_CACHE = API_CACHE / "helloao-books"
DOWNLOADS = INTERNAL_DATA / "downloads"
TIMING_DIR = INTERNAL_DATA / "timing"
TEXT_DIR = INTERNAL_DATA / "text"
LEGACY_TIMING_DIR = INTERNAL_DATA / "legacy-timing-data"
ALIGN_CACHE_DIR = INTERNAL_DATA / "align-cache"
ALIGN_INGESTED_FILE = INTERNAL_DATA / ".align-ingested.json"

# Local cache of audio-sync's OBS narration batch manifests
# (cdn.bibel.wiki/_obs_batches/<iso>.json), fetched by fetch_obs_batches.py.
# Small, whole-tree refetch each run (unlike align-cache, no delta/state
# tracking — the whole set is currently ~1-92 files, not worth the machinery).
OBS_BATCHES_CACHE_DIR = INTERNAL_DATA / "obs-batches"

# Local cache of door43's own OBS-with-audio catalog stats (the actual
# existence source of truth for catalog/obs-index.json — audio-sync's
# _obs_batches/ staging above is a narrower "already resolved for detail"
# signal, not the existence signal itself; see fetch_obs_catalog.py).
OBS_DOOR43_CATALOG_FILE = API_CACHE / "obs-door43-catalog.json"

# Resolved per-language door43 repo detail (content base URL, license,
# checking level, real story-id list, and — where a repo's release assets
# match the audio-filename pattern — resolved per-story audio URLs) for
# EVERY OBS language, text-only or audio-bearing alike. Fetched directly
# from door43's own catalog/release APIs, independent of audio-sync's
# _obs_batches/ staging pace: a language only becomes visible here once
# audio-sync has staged it, which lags real door43 availability and lags
# real align/obs/ alignment output even more (see doc/catalog-obs.md's
# note on this — a client-reported gap). See fetch_obs_repos.py.
OBS_REPOS_FILE = API_CACHE / "obs-repos.json"

# Per-story vernacular titles ({iso: {story_id: title}}), fetched by
# fetch_obs_titles.py. The ONE place this pipeline fetches real story
# CONTENT (door43's raw .md files) rather than pure existence/routing
# metadata — Range requests aren't honored by door43's raw endpoint, so
# each story's full text is fetched to read its first line; only that
# line (the title) is ever kept, the body is discarded immediately and
# never written to disk. See fetch_obs_titles.py's docstring.
OBS_TITLES_FILE = API_CACHE / "obs-titles.json"

# Local cache of audio-sync's real OBS alignment output
# (cdn.bibel.wiki/align/obs/<iso>/<story>_timing.json), fetched by
# pull_obs_align.py. Small, whole-tree resync each run (rclone dedupes via
# its own checksum comparison) — same rationale as OBS_BATCHES_CACHE_DIR.
OBS_ALIGN_CACHE_DIR = INTERNAL_DATA / "obs-align-cache"

# PKF/DBT/helloAO comparison-pilot outputs (pipeline/comparison/, pipeline/research/).
COMPARISON_RESULTS_DIR = INTERNAL_DATA / "comparison-results"
PKF_DBT_COMPARISON_FILE = COMPARISON_RESULTS_DIR / "pkf-dbt-comparison.json"
PKF_DBT_COMPARISON_WORDS_FILE = COMPARISON_RESULTS_DIR / "pkf-dbt-comparison-words.json"
PKF_DBT_COMPARISON_DIAGNOSIS_FILE = COMPARISON_RESULTS_DIR / "pkf-dbt-comparison-diagnosis.json"
HELLOAO_BOOK_COMPLETENESS_FILE = COMPARISON_RESULTS_DIR / "helloao-book-completeness.json"
HELLOAO_DBT_DIAGNOSIS_FILE = COMPARISON_RESULTS_DIR / "helloao-dbt-diagnosis.json"
PKF_HELLOAO_DIAGNOSIS_FILE = COMPARISON_RESULTS_DIR / "pkf-helloao-diagnosis.json"
TEXT_AVAILABILITY_FILE = COMPARISON_RESULTS_DIR / "text-availability.json"
TEXT_FILL_LOG_FILE = COMPARISON_RESULTS_DIR / "text-fill-log.json"

# Unified comparison pipeline (pipeline/comparison/compare_all.py,
# pipeline/research/diagnose_all.py) — replaces the five separate
# per-leg comparison/diagnosis files above with one of each.
ALL_COMPARISONS_FILE = COMPARISON_RESULTS_DIR / "all-comparisons.json"
ALL_DIAGNOSIS_FILE = COMPARISON_RESULTS_DIR / "all-diagnosis.json"

# ---------------------------------------------------------------------------
# Generated build output — rebuilt via `make dbt-metadata`, gitignored,
# never edited by hand.
# ---------------------------------------------------------------------------
EXPORT = REPO_ROOT / "export"

# The cross-source discovery files (index/overlap/text/audio) — genuinely
# multi-source (DBT+PKF+helloAO), so published under their own /catalog/
# namespace rather than /dbt/, which they'd previously been misplaced under
# (cdn.bibel.wiki/dbt/_app/catalog-*.json — a real inconsistency, fixed
# 2026-08-11 via a hard cutover: new location is canonical going forward,
# old location is left live and un-updated, not deleted — see
# publish-dbt.sh's cleanup-mode exclusion list for why that's safe).
CATALOG_DIR = EXPORT / "catalog"

# Open Bible Stories (OBS) — a genuinely different content shape from a
# Bible edition (50 fixed stories, no book/chapter/verse/canon), so it gets
# its own root instead of living under /dbt/. Existence rows still publish
# into /catalog/ (obs-index.json) alongside index.json/audio-index.json —
# same family, same row convention — since that part genuinely is a close
# analogue. See doc/catalog-obs.md and doc/obs-media.md.
OBS_DIR = EXPORT / "obs"
