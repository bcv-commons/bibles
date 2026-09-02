#!/usr/bin/env bash
#
# Publish export/obs/ to cdn.bibel.wiki/obs/ via rclone (Cloudflare R2).
#
# New root, separate from /dbt/: OBS (Open Bible Stories) is a genuinely
# different content shape (50 fixed stories, no book/chapter/verse/canon),
# so its per-language detail lives at /obs/<iso>/media.json rather than
# /dbt/<iso>/media.json. The existence-signal row (obs-index.json) still
# publishes into /catalog/ via publish-catalog.sh — no changes needed there,
# it already uploads everything under export/catalog/.
#
# Small, flat-ish file set (one media.json per staged language, currently
# 1) — no delta/state-tracking machinery needed yet; rclone's own checksum
# comparison already skips unchanged files. Revisit if this ever grows to
# DBT's scale (see publish-dbt.sh's delta machinery for that pattern).
#
# Credentials from .env (gitignored):
#   R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID, R2_BUCKET
#
# Usage:
#   make publish-obs              # upload changed files
#   make publish-obs-dry          # dry-run (no writes)
#   DRY_RUN=1 pipeline/core/publish-obs.sh   # same as above
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$ROOT_DIR"

SOURCE_DIR="export/obs"
CDN_PREFIX="obs"

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
    echo "[ERROR] $SOURCE_DIR not found. Run: make obs-metadata"
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
