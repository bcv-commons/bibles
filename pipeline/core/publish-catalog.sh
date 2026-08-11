#!/usr/bin/env bash
#
# Publish export/catalog/ to cdn.bibel.wiki/catalog/ via rclone (Cloudflare R2).
#
# Separate from publish-dbt.sh on purpose: the four files here
# (index.json/overlap.json/text.json/audio.json) are genuinely multi-source
# (DBT+PKF+helloAO), so they publish under their own /catalog/ namespace
# instead of /dbt/ — see pipeline/paths.py's CATALOG_DIR comment for the
# 2026-08-11 migration this completes. Small, flat file set (a handful of
# files, no per-language sharding here) — no delta/state-tracking machinery
# needed; rclone's own checksum comparison already skips unchanged files.
#
# Credentials from .env (gitignored):
#   R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID, R2_BUCKET
#
# Usage:
#   make publish-catalog              # upload changed files
#   make publish-catalog-dry          # dry-run (no writes)
#   DRY_RUN=1 pipeline/core/publish-catalog.sh   # same as above
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$ROOT_DIR"

SOURCE_DIR="export/catalog"
CDN_PREFIX="catalog"

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
    echo "[ERROR] $SOURCE_DIR not found. Run: make dbt-catalog (or the catalog-index/overlap generators)"
    exit 1
fi

echo "── Publishing $SOURCE_DIR -> ${REMOTE} (max-age=300)..."
rclone copy "$SOURCE_DIR" "$REMOTE" \
    --header-upload "Cache-Control: max-age=300" \
    --no-traverse \
    --transfers 8 \
    $DRY_FLAG \
    -v

echo "── Done."
