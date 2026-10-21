#!/usr/bin/env bash
#
# Publish the staged CrossWire Sofria + USJ + _meta.json (make stage-crosswire) to
# cdn.bibel.wiki/crosswire/ via rclone (Cloudflare R2).
#
# The editions are the ones generate_crosswire_usj.py writes: CrossWire SWORD modules with a
# public-domain or non-NC/ND Creative Commons licence and plain text, whose text isn't already
# reachable from another source. catalog/index.json lists them as source `c`.
# Same simple rclone-copy approach as publish-openbible.sh / publish-audiobiblia.sh.
#
# Credentials from .env (gitignored):
#   R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID, R2_BUCKET
#
# Usage:
#   make publish-crosswire              # upload changed files
#   make publish-crosswire-dry          # dry-run (no writes)
#   FULL_LIST=1 ...                           # republishing most files: compare by checksum
#   RCLONE_EXTRA="--include */*/_meta.json"   # extra rclone flags, e.g. a filter
#   DRY_RUN=1 pipeline/core/publish-crosswire.sh   # same as above
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$ROOT_DIR"

# The staged Sofria + USJ + _meta.json (make stage-crosswire). The verse-json tree
# (export/crosswire) is no longer published: Sofria replaced it on the CDN (2026-10-09).
SOURCE_DIR="${SOURCE_DIR:-export/publish/stage/crosswire}"
CDN_PREFIX="crosswire"

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
    --transfers 16 \
    --checkers 8 \
    $DRY_FLAG \
    ${EXTRA[@]+"${EXTRA[@]}"} \
    -v

echo "── Done."
