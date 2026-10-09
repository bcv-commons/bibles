#!/usr/bin/env bash
#
# Publish the cross-scheme verse maps in export/_vrs/map/ to cdn.bibel.wiki/_vrs/map/
# and verify each live file's sha256 against the local build.
#
# Scoped to the maps this repo owns (see MAPS below). publish-dbt.sh Pass 0 would
# also upload these, but it uploads the whole _vrs/ tree; this script touches only
# the maps, so a map-only change does not push unrelated files.
#
# Prerequisite: `make vrs-map` (or `make dbt-metadata`) has written export/_vrs/map/.
#
# Usage:
#   make publish-vrs-maps-dry     # dry-run + sha256 plan (no writes)
#   make publish-vrs-maps         # upload, then verify live sha256 == local
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$ROOT_DIR"

MAP_DIR="export/_vrs/map"
CDN_BASE="https://cdn.bibel.wiki/_vrs/map"
MAPS=(org-to-eng.json orgw-to-eng.json catm-to-eng.json rso-to-eng.json vul-to-eng.json lxx-to-eng.json nt-variants.json org-to-eng.multiverse.json rso-to-eng.multiverse.json
      orgw-to-eng.multiverse.json catm-to-eng.multiverse.json vul-to-eng.multiverse.json lxx-to-eng.multiverse.json)

if [ -f .env ]; then
    # shellcheck disable=SC1091
    set -a; source .env; set +a
fi

R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID:-${CLOUDFLARE_ACCESS_KEY_ID:-}}"
R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY:-${CLOUDFLARE_SECRET_ACCESS_KEY:-}}"
R2_ACCOUNT_ID="${R2_ACCOUNT_ID:-${CLOUDFLARE_ACCOUNT_ID:-}}"
R2_BUCKET="${R2_BUCKET:-${CLOUDFLARE_BUCKET:-}}"
if [ -z "$R2_ACCESS_KEY_ID" ] || [ -z "$R2_SECRET_ACCESS_KEY" ] || [ -z "$R2_ACCOUNT_ID" ] || [ -z "$R2_BUCKET" ]; then
    echo "[ERROR] Missing R2 credentials in .env"
    exit 1
fi

export RCLONE_CONFIG_R2_TYPE=s3
export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
export RCLONE_CONFIG_R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export RCLONE_CONFIG_R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
export RCLONE_CONFIG_R2_NO_CHECK_BUCKET=true

# rso-to-eng.multiverse.json has real hand-curated content (built with
# lexeme-aligner's input) with no deriver of its own, so unlike the other
# multiverse files here it's tracked under data/vrs/, not export/ (which
# make clean wipes with nothing to regenerate it from). Stage it before
# the existence check below.
cp data/vrs/rso-to-eng.multiverse.json "$MAP_DIR/rso-to-eng.multiverse.json"

for m in "${MAPS[@]}"; do
    [ -f "$MAP_DIR/$m" ] || { echo "[ERROR] $MAP_DIR/$m missing. Run: make vrs-map"; exit 1; }
done

echo "── Local maps to publish:"
shasum -a 256 "${MAPS[@]/#/$MAP_DIR/}"

DRY_FLAG=""
if [ "${DRY_RUN:-}" = "1" ]; then
    DRY_FLAG="--dry-run"
    echo "[DRY RUN] No files will be written to CDN."
fi

INCLUDES=()
for m in "${MAPS[@]}"; do INCLUDES+=(--include "$m"); done

echo "── Uploading to R2:${R2_BUCKET}/_vrs/map ..."
rclone copy "$MAP_DIR" "R2:${R2_BUCKET}/_vrs/map" \
    "${INCLUDES[@]}" \
    --header-upload "Cache-Control: max-age=3600" \
    --no-traverse $DRY_FLAG -v

if [ -n "$DRY_FLAG" ]; then
    echo "── Dry run done. Nothing verified (nothing was uploaded)."
    exit 0
fi

echo "── Verifying live sha256 against local ..."
fail=0
for m in "${MAPS[@]}"; do
    local_sha=$(shasum -a 256 "$MAP_DIR/$m" | cut -d' ' -f1)
    live_sha=$(curl -s -H "User-Agent: Mozilla/5.0" "$CDN_BASE/$m?v=$(date +%s)" | shasum -a 256 | cut -d' ' -f1)
    if [ "$local_sha" = "$live_sha" ]; then
        echo "  OK    $m  $local_sha"
    else
        echo "  FAIL  $m  local=$local_sha live=$live_sha"
        fail=1
    fi
done
if [ "$fail" -ne 0 ]; then
    echo "[ERROR] Live CDN does not match local build. Investigate before announcing."
    exit 1
fi
echo "── Done. Announce the new sha256s to lexeme-aligner."
