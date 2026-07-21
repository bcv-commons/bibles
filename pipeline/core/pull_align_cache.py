#!/usr/bin/env python3
"""Pull new audio-sync alignment output (Contract B) from cdn.bibel.wiki/align/
into a local cache, so generate_timing_by_book.py can consume it as a source.

Delta-pull only: tracks which align/_runs/<batch_id>.json manifests have
already been ingested (state file below); for each new manifest, pulls only
the specific *_timing.json files its `results` list references — not a full
align/ tree sync. Mirrors scripts/cdn_dbt_delta.py's state-diff pattern, but
for the inbound direction.

Spec: internal-docs/audio-sync-interface.md (MONO) §3 "Contract B".
Only *_timing.json is pulled (not *_words.json) — nothing here consumes word
alignment yet.

Usage:
    python3 scripts/pull_align_cache.py            # pull new manifests
    python3 scripts/pull_align_cache.py --dry-run   # list what would be pulled
"""
import json
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
from paths import ALIGN_CACHE_DIR, ALIGN_INGESTED_FILE  # noqa: E402

STATE_FILE = ALIGN_INGESTED_FILE
CACHE_DIR = ALIGN_CACHE_DIR
ALIGN_PREFIX = "align"
RUNS_PREFIX = f"{ALIGN_PREFIX}/_runs"


def rclone_env():
    """Same R2/Cloudflare credential resolution as scripts/publish-dbt.sh."""
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


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"ingested_batches": []}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rclone_lsf(env: dict, bucket: str, remote_path: str) -> list[str]:
    result = subprocess.run(
        ["rclone", "lsf", f"R2:{bucket}/{remote_path}", "--files-only"],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        # S3-backed remotes return an empty listing (exit 0) for a prefix with
        # no objects — a nonzero exit here means a real error, not "empty".
        print(f"[ERROR] rclone lsf {remote_path} failed: {result.stderr.strip()}", file=sys.stderr)
        return []
    return [ln for ln in result.stdout.splitlines() if ln.strip()]


def rclone_cat_json(env: dict, bucket: str, remote_path: str) -> dict | None:
    result = subprocess.run(
        ["rclone", "cat", f"R2:{bucket}/{remote_path}"],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        print(f"[ERROR] rclone cat {remote_path} failed: {result.stderr.strip()}", file=sys.stderr)
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"[ERROR] bad JSON in {remote_path}: {e}", file=sys.stderr)
        return None


def resolve_remote_files(env: dict, bucket: str, entry: dict) -> list[str]:
    """Remote align/ paths (relative, no bucket prefix) for one manifest result.

    Prefers building the *_timing.json filename directly from the entry's
    `audioFileset` field (one call saved). Falls back to listing the chapter's
    version/book directory when that field is absent — tolerates schema
    drift between the interface doc (which lists `audioFileset`) and any
    trimmed manifest payload that omits it.
    """
    canon = entry.get("canon")
    iso = entry.get("iso")
    version = entry.get("version") or entry.get("distinct_id")
    book = entry.get("book")
    chapter = entry.get("chapter")
    if not all((canon, iso, version, book)) or chapter is None:
        return []

    book_dir = f"{ALIGN_PREFIX}/{canon}/{iso}/{version}/{book}"
    audio_fileset = entry.get("audioFileset")
    if audio_fileset:
        return [f"{book_dir}/{book}_{int(chapter):03d}_{audio_fileset}_timing.json"]

    ch_tag = f"{book}_{int(chapter):03d}_"
    listed = rclone_lsf(env, bucket, book_dir)
    return [f"{book_dir}/{f}" for f in listed if f.startswith(ch_tag) and f.endswith("_timing.json")]


def pull_file(env: dict, bucket: str, remote_rel_path: str, dry_run: bool) -> bool:
    dest = CACHE_DIR / Path(remote_rel_path).relative_to(ALIGN_PREFIX)
    if dry_run:
        print(f"    would pull: {remote_rel_path} -> {dest}")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["rclone", "copyto", f"R2:{bucket}/{remote_rel_path}", str(dest), "--no-traverse"],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        print(f"    [ERROR] pull failed for {remote_rel_path}: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    env, bucket = rclone_env()
    state = load_state()
    ingested = set(state.get("ingested_batches", []))

    manifest_files = rclone_lsf(env, bucket, RUNS_PREFIX)
    if not manifest_files:
        print("[align-pull] No run manifests found at align/_runs/ yet "
              "(audio-sync hasn't published a batch).")
        return

    new_manifests = sorted(f for f in manifest_files if Path(f).stem not in ingested)
    if not new_manifests:
        print(f"[align-pull] {len(manifest_files)} manifest(s) found, all already ingested.")
        return

    print(f"[align-pull] {len(new_manifests)} new manifest(s) of {len(manifest_files)} total.")

    total_pulled, total_failed = 0, 0
    for mf in new_manifests:
        batch_id = Path(mf).stem
        manifest = rclone_cat_json(env, bucket, f"{RUNS_PREFIX}/{mf}")
        if manifest is None:
            print(f"  skip {batch_id}: unreadable manifest")
            continue

        results = manifest.get("results", [])
        ok_results = [r for r in results if r.get("status") == "ok"]
        print(f"  {batch_id}: {len(ok_results)}/{len(results)} ok result(s)")

        pulled, failed = 0, 0
        for entry in ok_results:
            for remote_path in resolve_remote_files(env, bucket, entry):
                if pull_file(env, bucket, remote_path, dry_run):
                    pulled += 1
                else:
                    failed += 1

        print(f"    pulled {pulled}, failed {failed}")
        total_pulled += pulled
        total_failed += failed

        if not dry_run and failed == 0:
            ingested.add(batch_id)

    if dry_run:
        print(f"[align-pull] dry run: {total_pulled} file(s) would be pulled, "
              f"{total_failed} would fail.")
        return

    state["ingested_batches"] = sorted(ingested)
    save_state(state)
    print(f"[align-pull] done: {total_pulled} pulled, {total_failed} failed. "
          f"{len(ingested)} batch(es) ingested total.")


if __name__ == "__main__":
    main()
