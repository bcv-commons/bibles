#!/usr/bin/env bash
#
# Publish export/dbt/ to cdn.bibel.wiki/dbt/ via rclone (Cloudflare R2).
#
# Credentials from .env (gitignored):
#   R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID, R2_BUCKET
#
# Usage:
#   make publish-dbt              # upload changed files
#   make publish-dbt-dry          # dry-run (no writes)
#   DRY_RUN=1 scripts/publish-dbt.sh   # same as above
#   CLEANUP=1 scripts/publish-dbt.sh   # delete orphaned files from CDN
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$ROOT_DIR"

SOURCE_DIR="export/dbt"
STATE_FILE="export/.dbt-published.json"
MEDIA_LIST="export/.dbt-upload-media.txt"
TIMING_LIST="export/.dbt-upload-timing.txt"
CDN_PREFIX="dbt"

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

# ── Cleanup mode: delete orphaned files from CDN ──
#
# FROZEN_LEGACY_PATHS: catalog-index.json/catalog-overlap.json/
# catalog-text.json/catalog-audio.json moved to /catalog/{index,overlap,
# text,audio}.json on 2026-08-11 (hard cutover — see pipeline/paths.py's
# CATALOG_DIR comment). The generators no longer write these paths under
# export/dbt/_app/ at all, so without this exclusion list a routine
# cleanup-dbt run would treat the still-live old copies as orphans and
# delete them — exactly what the cutover was designed NOT to do (old
# location stays live and working, just frozen/un-updated). Remove this
# list (and the old CDN copies) only as a deliberate, separate decision
# later, not as a side effect of an unrelated cleanup run.
FROZEN_LEGACY_PATHS=(
    "_app/catalog-index.json"
    "_app/catalog-overlap.json"
    "_app/catalog-text.json"
    "_app/catalog-audio.json"
)
if [ "${CLEANUP:-}" = "1" ]; then
    if [ ! -d "$SOURCE_DIR" ]; then
        echo "[ERROR] $SOURCE_DIR not found. Run: make dbt-metadata"
        exit 1
    fi
    echo "── Listing remote files..."
    remote_files=$(rclone lsf "$REMOTE" --recursive --files-only)
    orphans=()
    while IFS= read -r rel; do
        [ -z "$rel" ] && continue
        is_frozen=0
        for frozen in "${FROZEN_LEGACY_PATHS[@]}"; do
            if [ "$rel" = "$frozen" ]; then
                is_frozen=1
                break
            fi
        done
        [ "$is_frozen" = "1" ] && continue
        if [ ! -f "$SOURCE_DIR/$rel" ]; then
            orphans+=("$rel")
        fi
    done <<< "$remote_files"
    if [ ${#orphans[@]} -eq 0 ]; then
        echo "── No orphaned files found."
        exit 0
    fi
    echo "── Found ${#orphans[@]} orphaned files on CDN:"
    printf '  %s\n' "${orphans[@]}"
    ORPHAN_LIST=$(mktemp)
    printf '%s\n' "${orphans[@]}" > "$ORPHAN_LIST"
    echo "── Deleting orphans..."
    rclone delete "$REMOTE" \
        --files-from "$ORPHAN_LIST" \
        --no-traverse \
        $DRY_FLAG \
        -v
    rm -f "$ORPHAN_LIST"
    echo "── Cleanup done."
    exit 0
fi

# ── Pass 0: standard versification schemes -> /_vrs/ (central, DBT-owned) ──
# Small stable set; rclone skips unchanged. Independent of the dbt/ delta.
VRS_DIR="export/_vrs"
if [ -d "$VRS_DIR" ]; then
    echo "── Pass 0: Publishing standard .vrs schemes + /_vrs/map/ to /_vrs/ (max-age=3600)..."
    # Recursive: also uploads export/_vrs/map/*.json (cross-scheme maps). Exclude
    # the *.crosswalked.tsv validation intermediates — publish only the .json maps.
    rclone copy "$VRS_DIR" "R2:${R2_BUCKET}/_vrs" \
        --header-upload "Cache-Control: max-age=3600" \
        --exclude "map/*.tsv" \
        --no-traverse \
        --transfers 8 \
        $DRY_FLAG \
        -v
else
    echo "── Pass 0: No $VRS_DIR (run: make dbt-metadata) — skipping schemes."
fi

# ── Pass 0b: version-exclude.toml -> /dbt/ (small stable file, owned by this repo) ──
VERSION_EXCLUDE_FILE="data/version-exclude.toml"
if [ -f "$VERSION_EXCLUDE_FILE" ]; then
    echo "── Pass 0b: Publishing version-exclude.toml (max-age=3600)..."
    rclone copyto "$VERSION_EXCLUDE_FILE" "${REMOTE}/version-exclude.toml" \
        --header-upload "Cache-Control: max-age=3600" \
        $DRY_FLAG \
        -v
else
    echo "── Pass 0b: No $VERSION_EXCLUDE_FILE — skipping."
fi

# ── Verify source exists ──
if [ ! -d "$SOURCE_DIR" ]; then
    echo "[ERROR] $SOURCE_DIR not found. Run: make dbt-metadata"
    exit 1
fi

# ── Compute delta ──
echo "── Computing delta..."
.venv/bin/python pipeline/core/cdn_dbt_delta.py
delta_exit=$?

if [ "$delta_exit" -eq 2 ]; then
    echo "── Nothing to upload."
    exit 0
elif [ "$delta_exit" -ne 0 ]; then
    echo "[ERROR] Delta computation failed."
    exit 1
fi

# ── Pass 1: media.json files (max-age=300) ──
if [ -s "$MEDIA_LIST" ]; then
    count=$(wc -l < "$MEDIA_LIST" | tr -d ' ')
    echo "── Pass 1: Uploading $count media.json files (max-age=300)..."
    rclone copy "$SOURCE_DIR" "$REMOTE" \
        --files-from "$MEDIA_LIST" \
        --header-upload "Cache-Control: max-age=300" \
        --no-traverse \
        --transfers 16 \
        --checkers 16 \
        $DRY_FLAG \
        -v
else
    echo "── Pass 1: No media.json changes."
fi

# ── Pass 2: timing files (max-age=3600) ──
if [ -s "$TIMING_LIST" ]; then
    count=$(wc -l < "$TIMING_LIST" | tr -d ' ')
    echo "── Pass 2: Uploading $count timing files (max-age=3600)..."
    rclone copy "$SOURCE_DIR" "$REMOTE" \
        --files-from "$TIMING_LIST" \
        --header-upload "Cache-Control: max-age=3600" \
        --no-traverse \
        --transfers 16 \
        --checkers 16 \
        $DRY_FLAG \
        -v
else
    echo "── Pass 2: No timing changes."
fi

# ── Commit state (only after success, and not on dry-run) ──
if [ -z "$DRY_FLAG" ]; then
    echo "── Saving publish state..."
    .venv/bin/python -c "
import json
from pathlib import Path

source_dir = Path('export/dbt')
state_file = Path('export/.dbt-published.json')

state = {}
for p in sorted(source_dir.rglob('*.json')):
    rel = str(p.relative_to(source_dir))
    st = p.stat()
    state[rel] = {'size': st.st_size, 'mtime': st.st_mtime}

with open(state_file, 'w') as f:
    json.dump(state, f, separators=(',', ':'), sort_keys=True)

print(f'  {len(state)} files tracked')
"
    echo "── Done. State saved to $STATE_FILE"
else
    echo "── Dry run complete. No state saved."
fi
