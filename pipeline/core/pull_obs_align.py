#!/usr/bin/env python3
"""Pull audio-sync's real OBS alignment output
(cdn.bibel.wiki/align/obs/<iso>/<story>_timing.json) into a local cache, so
generate_obs_timing.py can consume it.

Unlike pull_align_cache.py's Bible-text alignment pull (Contract B, gated
by align/_runs/<batch_id>.json manifests), there is no run-manifest for OBS
yet — audio-sync publishes directly under align/obs/. Full recursive
resync every run: rclone's own checksum comparison already skips unchanged
files, and the population is small (currently ~200 files / 4 languages) —
not worth building manifest-gated delta machinery for until it's needed.

Usage:
    python3 pipeline/core/pull_obs_align.py            # pull all
    python3 pipeline/core/pull_obs_align.py --dry-run   # list only
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
from paths import OBS_ALIGN_CACHE_DIR  # noqa: E402

ALIGN_OBS_PREFIX = "align/obs"


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


def main():
    dry_run = "--dry-run" in sys.argv
    env, bucket = rclone_env()

    OBS_ALIGN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cmd = ["rclone", "copy", f"R2:{bucket}/{ALIGN_OBS_PREFIX}/", str(OBS_ALIGN_CACHE_DIR),
           "--transfers", "8"]
    if dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        print(f"[ERROR] rclone copy failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    langs = sorted(p.name for p in OBS_ALIGN_CACHE_DIR.iterdir() if p.is_dir()) if OBS_ALIGN_CACHE_DIR.exists() else []
    print(f"[pull-obs-align] synced align/obs/ -> {OBS_ALIGN_CACHE_DIR} "
          f"({len(langs)} language(s): {', '.join(langs)})")


if __name__ == "__main__":
    main()
