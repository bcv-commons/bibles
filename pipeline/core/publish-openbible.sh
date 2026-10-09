#!/usr/bin/env bash
#
# Publish the staged openbible Sofria + USJ + _meta.json (make stage-sofria) to
# cdn.bibel.wiki/openbible/ via rclone (Cloudflare R2). Verse-json is no longer published.
#
# New top-level CDN path (not under /dbt/ or /catalog/) — per-chapter text
# extracted locally from Biblica's own USFM zips (see doc/openbible-chapters.md).
# Modeled on publish-catalog.sh's simple approach (rclone's own checksum
# comparison skips unchanged files — no custom delta/state-tracking script
# needed) rather than publish-dbt.sh's custom delta machinery, which exists
# for reasons specific to that pipeline. Larger file count here (~130k
# chapter files) than catalog/'s handful, so --transfers is higher and a
# first run will take a while — that's expected, not a hang.
#
# Credentials from .env (gitignored):
#   R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID, R2_BUCKET
#
# Usage:
#   make publish-openbible              # upload changed files
#   make publish-openbible-dry          # dry-run (no writes)
#   FULL_LIST=1 ...                           # republishing most files: compare by checksum
#   RCLONE_EXTRA="--include */*/_meta.json"   # extra rclone flags, e.g. a filter
#   DRY_RUN=1 pipeline/core/publish-openbible.sh   # same as above
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$ROOT_DIR"

# The staged Sofria + USJ + _meta.json (make stage-sofria). The verse-json tree
# (export/openbible) is no longer published: Sofria replaced it on the CDN (2026-10-09).
SOURCE_DIR="${SOURCE_DIR:-export/publish/stage/openbible}"
CDN_PREFIX="openbible"

# ── Load credentials ──
if [ -f .env ]; then
    # shellcheck disable=SC1091
    set -a; source .env; set +a
fi

# Support both R2_* and CLOUDFLARE_* naming
R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID:-${CLOUDFLARE_ACCESS_KEY_ID:-}}"
R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY:-${CLOUDFLARE_SECRET_ACCESS_KEY:-}}"
R2_ACCOUNT_ID="${R2_ACCOUNT_ID:-${CLOUDFLARE_ACCOUNT_ID:-}}"
R2_BUCKET="${R2_BUCKET:-${CLOUDFLARE_BUCKET:-}}"

if [ -z "$R2_ACCESS_KEY_ID" ] || [ -z "$R2_SECRET_ACCESS_KEY" ] || [ -z "$R2_ACCOUNT_ID" ] || [ -z "$R2_BUCKET" ]; then
    echo "[ERROR] Missing R2 credentials. Set R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID, R2_BUCKET in .env"
    exit 1
fi

# ── Assemble rclone remote from env vars (no rclone.conf needed) ──
export RCLONE_CONFIG_R2_TYPE=s3
export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
export RCLONE_CONFIG_R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export RCLONE_CONFIG_R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
export RCLONE_CONFIG_R2_ACL=private
export RCLONE_CONFIG_R2_NO_CHECK_BUCKET=true

REMOTE="R2:${R2_BUCKET}/${CDN_PREFIX}"

DRY_FLAG=""
if [ "${DRY_RUN:-}" = "1" ]; then
    DRY_FLAG="--dry-run"
    echo "[DRY RUN] No files will be written to CDN."
fi

if [ ! -d "$SOURCE_DIR" ]; then
    echo "[ERROR] $SOURCE_DIR not found. Run: make stage-sofria"
    exit 1
fi

# Default: check each file on its own (fast for a few changed files). FULL_LIST=1 lists
# the whole remote once and compares checksums instead: much faster when most files
# are being republished.
LIST_FLAGS="--no-traverse"
[ "${FULL_LIST:-}" = "1" ] && LIST_FLAGS="--fast-list --checksum"

# split RCLONE_EXTRA into words without glob-expanding a filter like */*/_meta.json
read -r -a EXTRA <<< "${RCLONE_EXTRA:-}"

echo "── Publishing $SOURCE_DIR -> ${REMOTE} (max-age=3600)..."
rclone copy "$SOURCE_DIR" "$REMOTE" \
    --header-upload "Cache-Control: max-age=3600" \
    $LIST_FLAGS \
    --transfers "${TRANSFERS:-32}" \
    --checkers 16 \
    $DRY_FLAG \
    ${EXTRA[@]+"${EXTRA[@]}"} \
    -v

echo "── Done."
