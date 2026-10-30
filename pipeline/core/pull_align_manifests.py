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

2026-10-28: the manifests turned out incomplete (3,466 books in 247 filesets
on align/ with no manifest; entries whose files aren't there). Since then
align-index.json and obs-align-index.json are built from a listing of
align/ itself, the files a client actually fetches. The manifest digest
goes to align-manifest-index.json / obs-align-manifest-index.json, and what
the two disagree on to align-mismatch.json, to send to audio-sync.
align-folders.json records the align/ folder of every audio fileset.

Usage:
    python3 pipeline/core/pull_align_manifests.py            # pull + update digest
    python3 pipeline/core/pull_align_manifests.py --dry-run  # report only, no writes
    python3 pipeline/core/pull_align_manifests.py --force    # re-pull + re-fold everything
"""
import json
import os
import re
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
from paths import (  # noqa: E402
    ALIGN_FOLDERS_FILE, ALIGN_INDEX_FILE, ALIGN_INGESTED_FILE, ALIGN_MANIFEST_INDEX_FILE,
    ALIGN_MISMATCH_FILE, ALIGN_SOURCES_FILE, OBS_ALIGN_INDEX_FILE, OBS_ALIGN_MANIFEST_INDEX_FILE,
)

ALIGN_PREFIX = "align"
RUNS_PREFIX = "align/_runs"
BIBLE_FILE_RE = re.compile(r"^([0-9A-Z]{3})_\d{3}_(.+)_timing\.json$")
OBS_FILE_RE = re.compile(r"^(\d{2})_timing\.json$")


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


def list_align(env, bucket):
    """Every *_timing.json under align/ (not _runs/): what a client can actually fetch.
    Returns ({iso: {canon: {audio_fileset: {books}}}}, {raw_iso: {stories}},
    {"<canon>/<iso>/<audio_fileset>": folder}), or None if the listing failed."""
    r = subprocess.run(
        ["rclone", "lsf", f"R2:{bucket}/{ALIGN_PREFIX}/", "--recursive", "--files-only",
         "--fast-list", "--filter", "- _runs/**", "--filter", "+ *_timing.json", "--filter", "- *"],
        capture_output=True, text=True, env=env, timeout=1800,
    )
    if r.returncode != 0:
        print(f"[pull-align-manifests] listing {ALIGN_PREFIX}/ failed: {r.stderr.strip()[:500]}")
        return None
    books: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    stories: dict = defaultdict(set)
    folders: dict = {}
    for rel in r.stdout.splitlines():
        parts = rel.split("/")
        if len(parts) == 3 and parts[0] == "obs":
            m = OBS_FILE_RE.match(parts[2])
            if m:
                stories[parts[1]].add(m.group(1))
        elif len(parts) == 5:
            canon, iso, folder, book, name = parts
            m = BIBLE_FILE_RE.match(name)
            if m and m.group(1) == book:
                books[iso][canon][m.group(2)].add(book)
                folders[f"{canon}/{iso}/{m.group(2)}"] = folder
    return books, stories, folders


def plain(digest: dict) -> dict:
    return {iso: {canon: {fs: sorted(b) for fs, b in filesets.items()} for canon, filesets in canons.items()}
            for iso, canons in digest.items()}


def compare(listed: dict, manifest: dict, listed_obs: dict, manifest_obs: dict) -> dict:
    """What the listing and the manifests disagree on, for audio-sync."""
    no_manifest, manifest_no_files = [], []
    for iso, canons in sorted(listed.items()):
        for canon, filesets in sorted(canons.items()):
            for fs, books in sorted(filesets.items()):
                missing = books - set(manifest.get(iso, {}).get(canon, {}).get(fs, []))
                if missing:
                    no_manifest.append({"iso": iso, "canon": canon, "audio_fileset": fs,
                                        "books": sorted(missing)})
    for iso, canons in sorted(manifest.items()):
        for canon, filesets in sorted(canons.items()):
            for fs, books in sorted(filesets.items()):
                missing = set(books) - listed.get(iso, {}).get(canon, {}).get(fs, set())
                if missing:
                    manifest_no_files.append({"iso": iso, "canon": canon, "id": fs,
                                              "books": sorted(missing)})
    obs_no_manifest = {iso: sorted(s - set(manifest_obs.get(iso, [])))
                       for iso, s in sorted(listed_obs.items()) if s - set(manifest_obs.get(iso, []))}
    obs_manifest_no_files = {iso: sorted(set(s) - listed_obs.get(iso, set()))
                             for iso, s in sorted(manifest_obs.items()) if set(s) - listed_obs.get(iso, set())}
    return {"no_manifest": no_manifest, "manifest_no_files": manifest_no_files,
            "obs_no_manifest": obs_no_manifest, "obs_manifest_no_files": obs_manifest_no_files}


def main():
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    env, bucket = rclone_env()

    ingested = set() if force else set(
        load_json(ALIGN_INGESTED_FILE, {"ingested_batches": []})["ingested_batches"]
    )
    # Before 2026-10-28 align-index.json / obs-align-index.json WERE the manifest digests:
    # seed from them once, so the delta state stays valid without a --force re-pull.
    seed = ALIGN_MANIFEST_INDEX_FILE if ALIGN_MANIFEST_INDEX_FILE.exists() else ALIGN_INDEX_FILE
    obs_seed = OBS_ALIGN_MANIFEST_INDEX_FILE if OBS_ALIGN_MANIFEST_INDEX_FILE.exists() else OBS_ALIGN_INDEX_FILE
    index = {} if force else load_json(seed, {})
    digest: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for iso, canons in index.items():
        for canon, filesets in canons.items():
            for audio_fileset, books in filesets.items():
                digest[iso][canon][audio_fileset] = set(books)

    obs_index = {} if force else load_json(obs_seed, {})
    obs_digest: dict = defaultdict(set)
    for raw_iso, stories in obs_index.items():
        obs_digest[raw_iso] = set(stories)

    sources: dict = {} if force else load_json(ALIGN_SOURCES_FILE, {})

    r = subprocess.run(["rclone", "lsf", f"R2:{bucket}/{RUNS_PREFIX}/", "--files-only"],
                        capture_output=True, text=True, env=env, timeout=600)   # 13,000+ manifests
    if r.returncode != 0:
        sys.exit(f"[pull-align-manifests] listing {RUNS_PREFIX} failed: {r.stderr.strip()}")
    manifest_files = [ln for ln in r.stdout.splitlines() if ln.strip()]

    new_manifests = sorted(f for f in manifest_files if Path(f).stem not in ingested)
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

    print(f"[pull-align-manifests] listing {ALIGN_PREFIX}/ ...")
    listed = list_align(env, bucket)
    if listed is None:
        sys.exit("[pull-align-manifests] no listing: index files left unchanged.")
    books, stories, folders = listed
    mismatch = compare(books, plain(digest), stories, {k: sorted(v) for k, v in obs_digest.items()})
    n_books = sum(len(b) for c in books.values() for f in c.values() for b in f.values())
    print(f"[pull-align-manifests] align/: {n_books} book(s) in "
          f"{sum(len(f) for c in books.values() for f in c.values())} fileset(s), "
          f"{sum(len(s) for s in stories.values())} OBS stor(y/ies) in {len(stories)} language(s).")
    print(f"[pull-align-manifests] vs manifests: "
          f"{sum(len(x['books']) for x in mismatch['no_manifest'])} book(s) in "
          f"{len(mismatch['no_manifest'])} fileset(s) with no manifest; "
          f"{len(mismatch['manifest_no_files'])} manifest entr(y/ies) with no files; "
          f"OBS: {sum(map(len, mismatch['obs_no_manifest'].values()))} with no manifest, "
          f"{sum(map(len, mismatch['obs_manifest_no_files'].values()))} with no files.")

    if dry_run:
        print("[pull-align-manifests] dry run: no state written.")
        return

    save_json(ALIGN_INGESTED_FILE, {"ingested_batches": sorted(ingested)})
    save_json(ALIGN_MANIFEST_INDEX_FILE, plain(digest))
    save_json(OBS_ALIGN_MANIFEST_INDEX_FILE, {iso: sorted(s) for iso, s in obs_digest.items()})
    save_json(ALIGN_SOURCES_FILE, sources)
    save_json(ALIGN_INDEX_FILE, plain(books))
    save_json(OBS_ALIGN_INDEX_FILE, {iso: sorted(s) for iso, s in stories.items()})
    save_json(ALIGN_FOLDERS_FILE, folders)
    save_json(ALIGN_MISMATCH_FILE, mismatch)
    print(f"[pull-align-manifests] {ALIGN_INDEX_FILE.name}: {len(books)} language(s); "
          f"{OBS_ALIGN_INDEX_FILE.name}: {len(stories)}; differences -> {ALIGN_MISMATCH_FILE}")


if __name__ == "__main__":
    main()
