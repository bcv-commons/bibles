#!/usr/bin/env python3
"""Pull audio-sync's align/_runs/<batch_id>.json manifests and distill them
into small local existence digests — internal-data/align-index.json
(Bible text) and internal-data/obs-align-index.json (OBS).

Replaces pull_align_cache.py (2026-09-14): that script downloaded the
actual *_timing.json content bytes into a local mirror
(internal-data/align-cache) before generate_timing_index.py could build a
client-facing pointer index from them. Both the mirror and the pointer
index are gone now — audio-sync's manifests already carry everything a
client needs to compute the real URL themselves (confirmed: `status`,
`audio_fileset`, and stable path components on every result, per session
history) and already ARE the existence signal (`status: "ok"` on a result
means that chapter is real). Publishing our own copy of that fact was
redundant. See doc/dbt-timing.md for the published standard.

Also replaces pull_obs_align_index.py (2026-09-14, same day): that was a
live-listing stopgap because OBS had no completion manifest yet. Audio-sync
added one the same day (`obs-migrated-*.json` for the historical backlog,
`obs-local-*.json` going forward), reusing this exact stream rather than a
parallel format — results are distinguished by which fields are present,
`story` for OBS vs `book`/`chapter` for Bible text, confirmed live
2026-09-14. No separate script, no OBS-specific pulling logic: one pass
over the same manifests, branching only on which shape each result is.

What this script pulls is genuinely small — manifest JSON only (a few KB
each), never the timing/words content. What it keeps locally is smaller
still: not even the manifests themselves, just {iso: {canon: {audio_fileset:
[book, ...]}}} (Bible text) and {raw_iso: [story, ...]} (OBS) distilled
from every "ok" result, for generate_audio_metadata.py's media-code
classification and its timingBooks/timingBooksSet counts,
generate_sync_candidates.py's dedup, and generate_obs_metadata.py's
timingStories/timingStoriesSet — the one legitimate remaining internal use
of this data (deciding OUR OWN output), as opposed to publishing a
resolved index for clients.

Delta-pull: tracks which batch ids have already been folded into the
digest (state file below) so re-runs only process new manifests. This
assumes a batch's content is immutable once published — confirmed NOT
always true (2026-09-14: audio-sync corrected a manifest in place, same
batch_id, after finding BSBHAY's audio_fileset values were fake). Use
--force to re-pull and re-fold every manifest from scratch when you know
or suspect an in-place correction happened; there's no way to detect one
automatically from delta state alone.

Results without `audio_fileset` (manually-imported editions like
ENGBSBHAY, resolved instead via the manifest's own `text_sources`/
`audio_sources` maps, or a per-edition
align/<canon>/<iso>/<distinct_id>/_source.json sidecar — see
doc/dbt-timing.md) still fold into the same digest, keyed by `distinct_id`
itself — confirmed live 2026-09-14 that for these editions `distinct_id`
IS the real filename component (e.g. `..._ENGBSBHAY_timing.json`), same
role `audio_fileset` plays for DBT editions, audio-sync just doesn't
duplicate the field when the two would be identical. This lets
generate_audio_metadata.py treat a real, fully-confirmed non-DBT edition
exactly like a DBT one once it also has source-pairing info (see
ALIGN_SOURCES_FILE below) telling it where the actual content lives.

The manifest's own `text_sources`/`audio_sources` maps (keyed
"<iso>/<distinct_id>") are also captured here, into
internal-data/align-sources.json — the data that makes a non-DBT edition
like ENGBSBHAY (or a DBT-audio-but-non-DBT-text edition, the far more
common case: 157+ real DBT editions where audio-sync had to pull text
from helloAO because DBT itself has none) actually discoverable in
media.json, instead of just resolvable once you already know its id.

Usage:
    python3 pipeline/core/pull_align_manifests.py            # pull + update digest
    python3 pipeline/core/pull_align_manifests.py --dry-run  # report only, no writes
    python3 pipeline/core/pull_align_manifests.py --force    # re-pull + re-fold everything
"""
import json
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Error: missing module {e.name}. Run: pip install -r requirements.txt")
    sys.exit(1)

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import ALIGN_INDEX_FILE, ALIGN_INGESTED_FILE, ALIGN_SOURCES_FILE, OBS_ALIGN_INDEX_FILE  # noqa: E402

RUNS_PREFIX = "align/_runs"


def rclone_env():
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


def load_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":"), sort_keys=True), encoding="utf-8")


def main():
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    env, bucket = rclone_env()

    ingested = set() if force else set(
        load_json(ALIGN_INGESTED_FILE, {"ingested_batches": []})["ingested_batches"]
    )
    index = {} if force else load_json(ALIGN_INDEX_FILE, {})
    digest: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for iso, canons in index.items():
        for canon, filesets in canons.items():
            for audio_fileset, books in filesets.items():
                digest[iso][canon][audio_fileset] = set(books)

    obs_index = {} if force else load_json(OBS_ALIGN_INDEX_FILE, {})
    obs_digest: dict = defaultdict(set)
    for raw_iso, stories in obs_index.items():
        obs_digest[raw_iso] = set(stories)

    sources: dict = {} if force else load_json(ALIGN_SOURCES_FILE, {})

    r = subprocess.run(["rclone", "lsf", f"R2:{bucket}/{RUNS_PREFIX}/", "--files-only"],
                        capture_output=True, text=True, env=env, timeout=120)
    if r.returncode != 0:
        sys.exit(f"[pull-align-manifests] listing {RUNS_PREFIX} failed: {r.stderr.strip()}")
    manifest_files = [ln for ln in r.stdout.splitlines() if ln.strip()]

    new_manifests = sorted(f for f in manifest_files if Path(f).stem not in ingested)
    if not new_manifests:
        print(f"[pull-align-manifests] {len(manifest_files)} manifest(s), all already digested.")
        return

    print(f"[pull-align-manifests] {len(new_manifests)} new manifest(s) of {len(manifest_files)} total.")

    # One bulk transfer (rclone handles parallelism/retries itself) instead
    # of one `rclone cat` per manifest — thousands of individual calls was
    # slow and a single slow/hung one used to take the whole run down with
    # it (verified: a 60s-timeout `cat` killed the process mid-run).
    ok_results = 0
    obs_ok_results = 0
    skipped = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        files_from = tmp_dir / "files.txt"
        files_from.write_text("\n".join(new_manifests) + "\n")
        r = subprocess.run(
            ["rclone", "copy", f"R2:{bucket}/{RUNS_PREFIX}/", str(tmp_dir),
             "--files-from", str(files_from), "--transfers", "16", "--retries", "2"],
            capture_output=True, text=True, env=env, timeout=600,
        )
        if r.returncode != 0:
            print(f"[pull-align-manifests] bulk copy had errors (continuing with what arrived): "
                  f"{r.stderr.strip()[:500]}")

        for mf in new_manifests:
            batch_id = Path(mf).stem
            local = tmp_dir / mf
            if not local.exists():
                skipped.append(batch_id)
                continue
            try:
                manifest = json.loads(local.read_text())
            except json.JSONDecodeError:
                print(f"  skip {batch_id}: bad JSON")
                continue

            for key, val in manifest.get("text_sources", {}).items():
                sources.setdefault(key, {})["text"] = val
            for key, val in manifest.get("audio_sources", {}).items():
                sources.setdefault(key, {})["audio"] = val

            for res in manifest.get("results", []):
                if res.get("status") != "ok":
                    continue
                iso = res.get("iso")
                story = res.get("story")
                if iso and story:
                    # OBS result — distinguished by `story` (no book/chapter
                    # for this shape at all), same stream as Bible text.
                    obs_digest[iso].add(story)
                    obs_ok_results += 1
                    continue

                canon, book, distinct_id = res.get("canon"), res.get("book"), res.get("distinct_id")
                # audio_fileset absent -> distinct_id IS the real filename
                # component for this result (confirmed live 2026-09-14,
                # e.g. ENGBSBHAY) — same role, just not duplicated when
                # the two would be identical.
                audio_fileset = res.get("audio_fileset") or distinct_id
                if not (iso and canon and audio_fileset and book):
                    continue
                digest[iso][canon][audio_fileset].add(book)
                ok_results += 1

            if not dry_run:
                ingested.add(batch_id)

    print(f"[pull-align-manifests] {ok_results} Bible-text + {obs_ok_results} OBS ok result(s) "
          f"folded into their digests.")
    if skipped:
        print(f"[pull-align-manifests] {len(skipped)} manifest(s) didn't arrive in the bulk copy "
              f"(will retry next run — not marked ingested): {skipped[:10]}"
              + (f" ... +{len(skipped) - 10} more" if len(skipped) > 10 else ""))

    if dry_run:
        print("[pull-align-manifests] dry run: no state written.")
        return

    save_json(ALIGN_INGESTED_FILE, {"ingested_batches": sorted(ingested)})
    save_json(ALIGN_INDEX_FILE, {
        iso: {canon: {fs: sorted(books) for fs, books in filesets.items()} for canon, filesets in canons.items()}
        for iso, canons in digest.items()
    })
    save_json(OBS_ALIGN_INDEX_FILE, {iso: sorted(stories) for iso, stories in obs_digest.items()})
    save_json(ALIGN_SOURCES_FILE, sources)
    print(f"[pull-align-manifests] digest covers {len(digest)} Bible-text language(s) -> {ALIGN_INDEX_FILE}")
    print(f"[pull-align-manifests] digest covers {len(obs_digest)} OBS language(s) -> {OBS_ALIGN_INDEX_FILE}")
    print(f"[pull-align-manifests] {len(sources)} source-pairing entr(y/ies) -> {ALIGN_SOURCES_FILE}")


if __name__ == "__main__":
    main()
