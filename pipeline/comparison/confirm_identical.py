#!/usr/bin/env python3
"""Confirm "identical" pairs on more chapters before the catalog clusters them.

compare_all.py scores every pair in an (iso, canon) group on ONE probe chapter, and
generate_catalog_overlap.py merges a pair into one cluster when that score is exactly 1.0.
One chapter isn't enough to call two editions identical: the Open English Bible's US and
Commonwealth spelling editions are identical on Jonah 1 but differ in 180 Old Testament
verses (savor/savour, plow/plough), and the KJV printings ENGKJV / eng_kjv / eng_cpb were
identical on Revelation 15 but differ on Mark 1 (Judaea / Judaea / Judea). Found 2026-10-16.

So each pair scoring 1.0 is compared again on the CONFIRM chapters both editions have
(skipping the group's own probe). It stays at 1.0 only if every one of those is identical
too. Otherwise its score becomes the lowest one found, and `confirmations` records the
chapter, so diagnose_all.py classifies the pair on the chapter where it actually differs.
A pair with no further chapter in common keeps its 1.0, marked `confirmed: false` with
the reason, so "identical on the probe only" stays visible.

Writes back into all-comparisons.json:
    entry["confirmations"]["<a>|<b>"] = {"confirmed": bool, "checked": ["GEN1", ...],
                                          "differs_on": "PSA51", "score": 0.9937}
Pairs already confirmed are skipped on a rerun.

Usage:
    python3 confirm_identical.py [--iso ISO,ISO] [--workers 6]
"""
import json
import shutil
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_pkf_dbt import compare  # noqa: E402
from fetch_sources import rclone_env  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
from diagnose_all import fetch_for_id  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, ALL_COMPARISONS_FILE  # noqa: E402

CONFIRM = {"ot": [("GEN", 1), ("PSA", 51), ("RUT", 1)],
           "nt": [("MRK", 1), ("JHN", 3), ("REV", 15)]}
DEFAULT_PROBE = {"nt": "REV15", "ot": "PSA117"}


def confirm_group(entry: dict, catalog: dict, env: dict, bucket: str) -> dict:
    """Confirm one (iso, canon) group's 1.0 pairs in place; returns counts."""
    iso, canon = entry["iso"], entry["canon"]
    probe = entry.get("probe") or DEFAULT_PROBE[canon]
    checks = entry.setdefault("confirmations", {})
    pairs = [p for p, s in entry["scores"].items() if s == 1.0 and p not in checks]
    stats = {"pairs": 0, "confirmed": 0, "differ": 0, "nothing_to_check": 0}
    if not pairs:
        return stats
    tmpdir = Path(tempfile.mkdtemp(prefix=f"confirm_{iso}_"))
    cache: dict = {}

    def text(sid, book, chapter):
        k = (sid, book, chapter)
        if k not in cache:
            try:
                cache[k] = fetch_for_id(sid, iso, canon, book, chapter, catalog,
                                        entry.get("pkf_source_ref"), env, bucket, tmpdir)
            except Exception:
                cache[k] = None
        return cache[k]

    try:
        for pair in pairs:
            a, b = pair.split("|")
            checked, worst = [], None
            scored_on = (entry.get("pair_probes") or {}).get(pair, probe)  # compare_all.py's per-pair rescue
            for book, chapter in CONFIRM[canon]:
                if f"{book}{chapter}" == scored_on:
                    continue
                ta, tb = text(a, book, chapter), text(b, book, chapter)
                if not ta or not tb:
                    continue
                s = round(compare(ta, tb), 4)
                checked.append(f"{book}{chapter}")
                if s < 1.0 and (worst is None or s < worst[1]):
                    worst = (f"{book}{chapter}", s)
            stats["pairs"] += 1
            if worst:
                checks[pair] = {"confirmed": False, "checked": checked, "differs_on": worst[0], "score": worst[1]}
                entry["scores"][pair] = worst[1]
                stats["differ"] += 1
            elif checked:
                checks[pair] = {"confirmed": True, "checked": checked}
                stats["confirmed"] += 1
            else:
                checks[pair] = {"confirmed": False, "checked": [], "reason": "no further chapter in common"}
                stats["nothing_to_check"] += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return stats


def main():
    args = sys.argv[1:]
    only = set(args[args.index("--iso") + 1].split(",")) if "--iso" in args else None
    workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 6
    data = json.loads(ALL_COMPARISONS_FILE.read_text())
    catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())
    env, bucket = rclone_env()
    todo = [e for k, e in sorted(data.items())
            if e.get("status") == "compared" and not (only and e["iso"] not in only)
            and any(s == 1.0 and p not in (e.get("confirmations") or {}) for p, s in e["scores"].items())]
    print(f"[confirm-identical] {len(todo)} groups with unconfirmed 1.0 pairs", flush=True)
    totals = {"pairs": 0, "confirmed": 0, "differ": 0, "nothing_to_check": 0}
    lock = threading.Lock()
    done = 0

    def one(entry):
        nonlocal done
        st = confirm_group(entry, catalog, env, bucket)
        with lock:
            for k, v in st.items():
                totals[k] += v
            done += 1
            if done % 25 == 0 or done == len(todo):
                ALL_COMPARISONS_FILE.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                                encoding="utf-8")
                print(f"  {done}/{len(todo)} groups; {totals}", flush=True)

    try:
        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(one, todo))
    finally:
        with lock:
            ALL_COMPARISONS_FILE.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    print(f"[confirm-identical] {totals}")


if __name__ == "__main__":
    main()
