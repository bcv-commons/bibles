#!/usr/bin/env python3
"""Check which DBT audio filesets have DBT's own verse timing, one probe per testament,
into internal-data/dbt-timing-index.json.

Replaces internal-data/timing/BB (a bulk copy of DBT's timing files, mostly from
2026-04-08/09) as the record of DBT timing. Since 2026-09-15 bibles publishes no DBT
timing (clients fetch it from DBT with their own key), so only the existence is kept.

Filesets checked: every audio fileset in internal-data/timing/BB, plus every audio fileset
on DBT's own list (GET /timestamps; video filesets, ...DV/...PV, left out). DBT's list is
incomplete (2026-10-28: ACRWBTN2SA has timing and is not on it), so the BB filesets are
checked too, not only the list.

Probe (the convention for DBT samples): NT -> REV 15, OT -> PSA 117. Where that has no
timing, a second probe, NT -> MRK 1, OT -> GEN 1: DBT timed only some books of some
filesets (2026-10-28: 13 filesets with timing for the Gospels or Mark, none for REV 15). The
testament of a fileset is its directory in BB (nt/ot), else the 7th letter of its id (N, O;
P = portions, both are probed). A probe answering with verse rows means the testament has
DBT timing; empty answers or 404s to both mean it has none.

    {"checked_at": "...", "probe": {"nt": "REV 15, MRK 1", "ot": "PSA 117, GEN 1"},
     "filesets": {"<audio fileset>": {"nt": true, "ot": false}, ...}}

Resumable: results are written as they come; a rerun skips filesets already checked
unless --force. Usage: python3 pipeline/core/fetch_dbt_timing_index.py [--force] [--dry-run]
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import INTERNAL_DATA, REPO_ROOT, TIMING_DIR  # noqa: E402

OUT = INTERNAL_DATA / "dbt-timing-index.json"
BB_DIR = TIMING_DIR / "BB"
API = "https://4.dbt.io/api"
PROBE = {"nt": [("REV", 15), ("MRK", 1)], "ot": [("PSA", 117), ("GEN", 1)]}
PROBE_TEXT = {c: ", ".join(f"{b} {ch}" for b, ch in probes) for c, probes in PROBE.items()}
VIDEO = ("DV", "PV")


def get(key, path):
    """(status, json or None). Never logs the URL: it carries the key."""
    for attempt in range(3):
        try:
            r = requests.get(f"{API}/{path}", params={"v": "4", "key": key}, timeout=30)
        except requests.RequestException as e:
            if attempt == 2:
                return f"network:{type(e).__name__}", None
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
            time.sleep(2 * (attempt + 1))
            continue
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, None
    return "retries", None


def candidates(key):
    """{fileset: {canons}}: BB's audio filesets with their directory's testament, plus DBT's list."""
    want = {}
    if BB_DIR.exists():
        for canon_dir in BB_DIR.iterdir():
            if canon_dir.name not in PROBE:
                continue
            for f in canon_dir.rglob("*_timing.json"):
                fs = f.stem.replace("_timing", "").split("_", 2)[2]
                if not fs.endswith(VIDEO):
                    want.setdefault(fs, set()).add(canon_dir.name)
    status, listed = get(key, "timestamps")
    if status != 200 or not isinstance(listed, list):
        sys.exit(f"[ERROR] DBT /timestamps list: {status}")
    n_listed = 0
    for row in listed:
        fs = row.get("fileset_id") or ""
        if not fs or fs.endswith(VIDEO):
            continue
        n_listed += 1
        letter = fs[6:7]
        want.setdefault(fs, set()).update({"N": {"nt"}, "O": {"ot"}}.get(letter, {"nt", "ot"}))
    print(f"[INFO] {len(want)} audio filesets to check ({n_listed} on DBT's list)")
    return want


def probe(key, fs, canon):
    for book, chapter in PROBE[canon]:
        status, data = get(key, f"timestamps/{fs}/{book}/{chapter}")
        if status == 200 and isinstance(data, dict) and data.get("data"):
            return True
        if status not in (200, 404):
            return f"error:{status}"
    return False


def main():
    force, dry = "--force" in sys.argv, "--dry-run" in sys.argv
    load_dotenv(REPO_ROOT / ".env")
    key = os.getenv("BIBLE_API_KEY") or os.getenv("DBT_API_KEY")
    if not key:
        sys.exit("[ERROR] BIBLE_API_KEY (or DBT_API_KEY) not set in .env")

    state = {} if force or not OUT.exists() else json.loads(OUT.read_text())
    done = state.get("filesets", {})
    # A "no" from fewer probes than today's is checked again; a "yes" stands.
    same = state.get("probe") == PROBE_TEXT
    todo = [(fs, c) for fs, canons in sorted(candidates(key).items()) for c in sorted(canons)
            if not (done.get(fs, {}).get(c) is True or (same and done.get(fs, {}).get(c) is False))]
    print(f"[INFO] {len(todo)} probes to run")
    if dry:
        return

    def save():
        state.update({"checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "probe": PROBE_TEXT,
                      "filesets": dict(sorted(done.items()))})
        OUT.write_text(json.dumps(state, indent=1) + "\n")

    errors = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i, ((fs, c), res) in enumerate(zip(todo, pool.map(lambda t: probe(key, *t), todo)), 1):
            done.setdefault(fs, {})[c] = res
            errors += not isinstance(res, bool)
            if i % 200 == 0:
                save()
                print(f"[INFO] {i}/{len(todo)}", flush=True)
    save()
    have = {c: sum(v.get(c) is True for v in done.values()) for c in PROBE}
    print(f"[OK] {OUT}: {len(done)} filesets; with timing: NT {have['nt']}, OT {have['ot']}; "
          f"{errors} probes failed (rerun to retry them)")


if __name__ == "__main__":
    main()
