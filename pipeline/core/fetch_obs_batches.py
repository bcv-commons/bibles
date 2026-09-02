#!/usr/bin/env python3
"""Fetch audio-sync's OBS narration batch manifests
(cdn.bibel.wiki/_obs_batches/<iso>.json) into a local cache, so
generate_obs_metadata.py / generate_obs_index.py can consume them.

These are audio-sync's producer-side staging files (see
obs_batch_manifest.py in the audio-sync repo) — this script only reads
them, never writes to that namespace. Full re-fetch every run: the
population is small (currently 1 of ~92 target languages staged) and
there's no per-file change-tracking need yet at this scale, unlike
align-cache's delta-pull machinery.

Usage:
    python3 pipeline/core/fetch_obs_batches.py            # fetch all
    python3 pipeline/core/fetch_obs_batches.py --dry-run   # list only
"""
import os
import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Error: missing module {e.name}. Run: pip install -r requirements.txt")
    sys.exit(1)

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import OBS_BATCHES_CACHE_DIR  # noqa: E402

OBS_BATCHES_PREFIX = "_obs_batches"


def rclone_env():
    """Same R2/Cloudflare credential resolution as pull_align_cache.py."""
    access = os.getenv("R2_ACCESS_KEY_ID") or os.getenv("CLOUDFLARE_ACCESS_KEY_ID", "")
    secret = os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("CLOUDFLARE_SECRET_ACCESS_KEY", "")
    account = os.getenv("R2_ACCOUNT_ID") or os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    bucket = os.getenv("R2_BUCKET") or os.getenv("CLOUDFLARE_BUCKET", "")
    if not all((access, secret, account, bucket)):
        sys.exit("[ERROR] Missing R2 credentials. Set R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, "
                  "R2_ACCOUNT_ID, R2_BUCKET in .env")
    env = os.environ.copy()
    env.update({
        "RCLONE_CONFIG_R2_TYPE": "s3",
        "RCLONE_CONFIG_R2_PROVIDER": "Cloudflare",
        "RCLONE_CONFIG_R2_ACCESS_KEY_ID": access,
        "RCLONE_CONFIG_R2_SECRET_ACCESS_KEY": secret,
        "RCLONE_CONFIG_R2_ENDPOINT": f"https://{account}.r2.cloudflarestorage.com",
        "RCLONE_CONFIG_R2_ACL": "private",
        "RCLONE_CONFIG_R2_NO_CHECK_BUCKET": "true",
    })
    return env, bucket


def rclone_lsf(env: dict, bucket: str, remote_path: str) -> list[str]:
    result = subprocess.run(
        ["rclone", "lsf", f"R2:{bucket}/{remote_path}", "--files-only"],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        print(f"[ERROR] rclone lsf {remote_path} failed: {result.stderr.strip()}", file=sys.stderr)
        return []
    return [ln for ln in result.stdout.splitlines() if ln.strip()]


def main():
    dry_run = "--dry-run" in sys.argv
    env, bucket = rclone_env()

    files = rclone_lsf(env, bucket, OBS_BATCHES_PREFIX)
    if not files:
        print(f"[fetch-obs-batches] No files found at {OBS_BATCHES_PREFIX}/ yet.")
        return

    print(f"[fetch-obs-batches] {len(files)} manifest(s) found.")
    if dry_run:
        for f in sorted(files):
            print(f"  would pull: {OBS_BATCHES_PREFIX}/{f}")
        return

    OBS_BATCHES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    pulled, failed = 0, 0
    for f in sorted(files):
        remote = f"{OBS_BATCHES_PREFIX}/{f}"
        dest = OBS_BATCHES_CACHE_DIR / f
        result = subprocess.run(
            ["rclone", "copyto", f"R2:{bucket}/{remote}", str(dest), "--no-traverse"],
            capture_output=True, text=True, env=env,
        )
        if result.returncode != 0:
            print(f"  [ERROR] pull failed for {remote}: {result.stderr.strip()}", file=sys.stderr)
            failed += 1
        else:
            pulled += 1

    print(f"[fetch-obs-batches] done: {pulled} pulled, {failed} failed.")


if __name__ == "__main__":
    main()
