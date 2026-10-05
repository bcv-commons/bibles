#!/usr/bin/env bash
#
# Publish export/audiobiblia/ to cdn.bibel.wiki/audiobiblia/ via rclone (Cloudflare R2).
#
# New top-level CDN path (not under /dbt/ or /catalog/) — per-chapter text
# for the two audiobiblia.org Spanish editions (BLL, BES) with a genuinely
# republishable license, real text sourced from eBible.org's structured
# USFM (not audiobiblia.org's own HTML/PDF — see
# pipeline/core/generate_audiobiblia_chapters.py's own module docstring
# for the full source/license verification). Modeled on
# publish-openbible.sh/publish-catalog.sh's simple rclone-copy approach
# (rclone's own checksum comparison skips unchanged files — no custom
# delta/state-tracking script needed). Small file count (~2.6k files) —
# a first run takes under a minute.
#
# Credentials from .env (gitignored):
#   R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID, R2_BUCKET
#
# Usage:
#   make publish-audiobiblia              # upload changed files
#   make publish-audiobiblia-dry          # dry-run (no writes)
#   DRY_RUN=1 pipeline/core/publish-audiobiblia.sh   # same as above
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$ROOT_DIR"

SOURCE_DIR="export/audiobiblia"
CDN_PREFIX="audiobiblia"

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
    echo "[ERROR] $SOURCE_DIR not found. Run: python3 pipeline/core/generate_audiobiblia_chapters.py"
    exit 1
fi

echo "── Publishing $SOURCE_DIR -> ${REMOTE} (max-age=3600)..."
rclone copy "$SOURCE_DIR" "$REMOTE" \
    --header-upload "Cache-Control: max-age=3600" \
    --no-traverse \
    --transfers 16 \
    --checkers 8 \
    $DRY_FLAG \
    -v

echo "── Done."
