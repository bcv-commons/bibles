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

# ---------------------------------------------------------------------------
# Internal working data — entirely gitignored, entirely rebuildable
# (fetched from DBT/PKF/helloAO APIs, or computed by the comparison
# pipeline). Nothing under here is hand-authored.
# ---------------------------------------------------------------------------
INTERNAL_DATA = REPO_ROOT / "internal-data"

API_CACHE = INTERNAL_DATA / "api-cache"
DOWNLOADS = INTERNAL_DATA / "downloads"
TIMING_DIR = INTERNAL_DATA / "timing"
TEXT_DIR = INTERNAL_DATA / "text"
LEGACY_TIMING_DIR = INTERNAL_DATA / "legacy-timing-data"
ALIGN_CACHE_DIR = INTERNAL_DATA / "align-cache"
ALIGN_INGESTED_FILE = INTERNAL_DATA / ".align-ingested.json"

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

# ---------------------------------------------------------------------------
# Generated build output — rebuilt via `make dbt-metadata`, gitignored,
# never edited by hand.
# ---------------------------------------------------------------------------
EXPORT = REPO_ROOT / "export"
