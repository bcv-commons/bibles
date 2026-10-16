#!/usr/bin/env python3
"""Old Testament layout probes for DBT and helloAO editions in dbt/_vrs/index.json.

For each edition with an Old Testament, the last verse of every chapter in an
_vrs/map/ot-variants.json block (Job 38-41, Ecclesiastes 11-12, Hosea 13-14) is fetched
and cached. fingerprint_versification.py reads the cache (no network) and writes the
editions' `ot` entries (ot_versification.py). Same conventions as nt_probes.py: a chapter
the source doesn't have is cached as absent (null); a network error isn't cached, so a
rerun retries it.

Usage:
    python3 pipeline/core/ot_probes.py --fetch [--workers 8]
"""
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nt_probes  # noqa: E402  (same fetchers)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, EXPORT  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comparison"))
from compare_all import dbt_candidates  # noqa: E402

CACHE = API_CACHE / "versification" / "ot-probes.json"
VARIANTS = EXPORT / "_vrs" / "map" / "ot-variants.json"


def probe(fetch_chapter, chapters) -> dict:
    """{"BOOK c": last verse | None}. Stops early for an edition without the first book."""
    out = {}
    for book, c in chapters:
        verses = fetch_chapter(book, c)
        out[f"{book} {c}"] = max(verses) if verses else None
    return out


def ot_entries(index: dict, otc) -> dict:
    """`ot` entries for DBT/helloAO keys of index, from the cache (no network)."""
    cache = json.loads(CACHE.read_text()) if CACHE.is_file() else {}
    out = {}
    for key, label in index.items():
        p = cache.get(key)
        if not p:
            continue
        lengths = {(k.split()[0], int(k.split()[1])): v for k, v in p.items() if v is not None}
        e = otc.entry(lengths, label)
        if e:
            out[key] = e
    return out


def main() -> None:
    args = sys.argv[1:]
    if "--fetch" not in args:
        print("[ot-probes] pass --fetch")
        return
    workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 8
    from ot_versification import OtClassifier
    otc = OtClassifier({}, json.loads(VARIANTS.read_text()))
    chapters = otc.tested
    index = json.loads((EXPORT / "dbt" / "_vrs" / "index.json").read_text())["l"]
    catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())
    cache = json.loads(CACHE.read_text()) if CACHE.is_file() else {}

    todo = []
    for key in index:
        if key in cache:
            continue
        if key.startswith("helloao:"):
            tid = key.split(":", 1)[1]
            todo.append((key, lambda b, c, t=tid: nt_probes._helloao(t, b, c)))
        elif "/" in key:
            iso, abbr = key.split("/", 1)
            fs = dbt_candidates(catalog, iso, "ot").get(abbr)
            if fs:
                todo.append((key, lambda b, c, f=fs: nt_probes._dbt(f, b, c)))
    print(f"[ot-probes] {len(chapters)} chapters per edition; {len(todo)} editions to probe "
          f"({len(cache)} cached)", flush=True)
    lock = threading.Lock()
    done = failed = 0

    def save():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def one(item):
        nonlocal done, failed
        key, fetch = item
        try:
            result = probe(fetch, chapters)
        except Exception as e:  # network trouble: not cached, retried next run
            with lock:
                failed += 1
                print(f"  {key}: not probed ({str(e)[:80]})", flush=True)
            return
        with lock:
            cache[key] = result
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(todo)}", flush=True)
                save()
        time.sleep(0.05)

    try:
        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(one, todo))
    finally:
        with lock:
            save()
    print(f"[ot-probes] probed {done}, not probed {failed} -> {CACHE}")


if __name__ == "__main__":
    main()
