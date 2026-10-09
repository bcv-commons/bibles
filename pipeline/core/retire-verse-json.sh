#!/usr/bin/env bash
#
# Remove the verse-json chapter files (<iso>/<edition>/<BOOK>/<chapter>.json) from
# cdn.bibel.wiki/openbible/ and /audiobiblia/. Sofria (<chapter>.sofria.json)
# replaces them. Keeps everything else: Sofria, USJ (<BOOK>.usj.json), _meta.json.
#
# Dry run by default. Run for real only once clients have moved to Sofria:
#   make retire-verse-json-dry                  # list what would be deleted
#   CONFIRM=delete make retire-verse-json       # delete
#
# Credentials from .env, as in publish-openbible.sh.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$ROOT_DIR"

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

DRY_FLAG="--dry-run"
if [ "${CONFIRM:-}" = "delete" ]; then
    DRY_FLAG=""
    echo "[DELETE] Removing verse-json chapter files from the CDN."
else
    echo "[DRY RUN] Nothing is deleted. Set CONFIRM=delete to delete."
fi

# Ordered rules (first match wins): keep Sofria, take only numbered chapter files exactly
# four levels down, leave everything else. (Mixing --include/--exclude leaves their
# order undefined and, tested 2026-10-09, selects the Sofria files too.)
FILTERS=(--filter "- *.sofria.json" --filter "+ /*/*/*/[0-9]*.json" --filter "- *")

for prefix in openbible audiobiblia; do
    remote="R2:${R2_BUCKET}/${prefix}"
    list="$(mktemp)"
    rclone lsf -R --files-only --fast-list "$remote" "${FILTERS[@]}" > "$list"
    bad="$(grep -c -v -E '^[^/]+/[^/]+/[^/]+/[0-9]+\.json$' "$list" || true)"
    echo "── ${prefix}/: $(wc -l < "$list" | tr -d ' ') verse-json chapter files; ${bad} other paths matched"
    if [ "$bad" != "0" ]; then
        echo "[ERROR] the filter matched files that are not verse-json chapters; nothing deleted:"
        grep -v -E '^[^/]+/[^/]+/[^/]+/[0-9]+\.json$' "$list" | head
        rm -f "$list"; exit 1
    fi
    head -3 "$list" | sed 's/^/   e.g. /'
    if [ -z "$DRY_FLAG" ]; then
        rclone delete "$remote" --files-from "$list" --no-traverse --checkers 32 -v 2>&1 | grep -c "Deleted" | sed 's/^/   deleted: /' || true
    fi
    rm -f "$list"
done
echo "── Done."
