#!/usr/bin/env python3
"""New Testament numbering probes for DBT and helloAO editions in dbt/_vrs/index.json.

For each edition, the last verse of every chapter TVTMS tests (the chapters in
_vrs/map/nt-variants.json) is fetched and cached. fingerprint_versification.py reads
the cache (no network) and writes the editions' `nt` entries (nt_versification.py).

Revelation 12 with 17 verses is KJV/NIV (12:18's text starts 13:1) or ESV (it ends
12:17). The probe also stores the lengths of 12:17 and 13:1, and the edition is read as
ESV when its 12:17 / 13:1 ratio is nearer the ESV ratio than the KJV ratio, both taken
from an English text that has all 18 verses (helloAO eng_ulb).

A chapter the source doesn't have (404, no data) is cached as absent (null); a network
error isn't cached, so a rerun retries it.

Usage:
    python3 pipeline/core/nt_probes.py --fetch [--workers 8]
"""
import json
import math
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import download_language_content as dl  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, EXPORT  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comparison"))
from compare_all import dbt_candidates  # noqa: E402

CACHE = API_CACHE / "versification" / "nt-probes.json"
HELLOAO_API = "https://bible.helloao.org/api"
REF_TRANSLATION = "eng_ulb"  # has a real REV 12:18 (most English editions end at 12:17)
MIN_CHAPTERS = 8
ABSENT = None


def _helloao(tid: str, book: str, chapter: int):
    """{verse number: text} for a helloAO chapter; {} when absent; raises on network error."""
    r = requests.get(f"{HELLOAO_API}/{tid}/{book}/{chapter}.json", timeout=20)
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    out = {}
    for b in r.json().get("chapter", {}).get("content", []):
        if b.get("type") == "verse" and "number" in b:
            out[int(b["number"])] = " ".join(x if isinstance(x, str) else x.get("text", "")
                                             for x in b.get("content", []))
    return out


def _dbt(fileset: str, book: str, chapter: int):
    res = dl.get_text_content(fileset, book, chapter)
    if not res:
        if dl._classify_api_failure() in ("http_404_not_found", "empty_data"):
            return {}
        raise RuntimeError("DBT request failed")
    if res.get("type") != "verses":
        return {}
    out = {}
    for item in res["data"]:
        end = int(item.get("verse_end") or item.get("verse_start") or 0)
        start = int(item.get("verse_start") or end)
        out[end] = out.get(end, "") + " " + (item.get("verse_text") or "")
        out.setdefault(start, out[end])
    return out


def probe(fetch_chapter, chapters) -> dict:
    """{"BOOK c": last verse | None, ..., "rev": [len 12:17, len 13:1]}."""
    out = {}
    for book, c in chapters:
        verses = fetch_chapter(book, c)
        out[f"{book} {c}"] = max(verses) if verses else ABSENT
        if (book, c) == ("REV", 12) and verses and max(verses) == 17:
            nxt = fetch_chapter("REV", 13)
            if nxt.get(1) and verses.get(17):
                out["rev"] = [len(verses[17].strip()), len(nxt[1].strip())]
    return out


def esv_like(rev: list | None, ref: dict | None) -> bool:
    """True when 12:17 holds 12:18's text (ESV), judged against the English reference."""
    if not rev or not ref or not all(rev):
        return False
    l17, l18, l13 = ref["17"], ref["18"], ref["13:1"]
    r = math.log(rev[0] / rev[1])
    r_kjv = math.log(l17 / (l18 + l13))
    r_esv = math.log((l17 + l18) / l13)
    return abs(r - r_esv) < abs(r - r_kjv)


def nt_entries(index: dict, ntc) -> dict:
    """`nt` entries for DBT/helloAO keys of index, from the cache (no network)."""
    cache = json.loads(CACHE.read_text()) if CACHE.is_file() else {}
    ref = cache.get("_reference")
    out = {}
    for key, label in index.items():
        p = cache.get(key)
        if not p:
            continue
        lengths = {}
        for k, v in p.items():
            if k == "rev" or v is None:
                continue
            book, c = k.split()
            lengths[(book, int(c))] = v
        if len(lengths) < MIN_CHAPTERS:
            continue
        swap = {"REV12-17": "REV12-17esv"} if esv_like(p.get("rev"), ref) else None
        e = ntc.entry(lengths, label if label not in ("irregular", "undetermined") else "eng", swap)
        if e:
            out[key] = e
    return out


def main() -> None:
    args = sys.argv[1:]
    if "--fetch" not in args:
        print("[nt-probes] pass --fetch")
        return
    workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 8
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import derive_tvtms_org_eng as tv
    from nt_versification import NtClassifier
    schemes = {"eng": tv._shape(tv.REPO_ROOT / "data" / "vrs" / "eng.vrs")}
    ntc = NtClassifier(schemes, json.loads((EXPORT / "_vrs" / "map" / "nt-variants.json").read_text()))
    chapters = sorted(ntc.tested)
    index = json.loads((EXPORT / "dbt" / "_vrs" / "index.json").read_text())["l"]
    catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())

    cache = json.loads(CACHE.read_text()) if CACHE.is_file() else {}
    if "_reference" not in cache:
        rv12, rv13 = _helloao(REF_TRANSLATION, "REV", 12), _helloao(REF_TRANSLATION, "REV", 13)
        cache["_reference"] = {"17": len(rv12[17]), "18": len(rv12[18]), "13:1": len(rv13[1])}

    todo = []
    for key in index:
        if key in cache:
            continue
        if key.startswith("helloao:"):
            tid = key.split(":", 1)[1]
            todo.append((key, lambda b, c, t=tid: _helloao(t, b, c)))
        elif "/" in key:
            iso, abbr = key.split("/", 1)
            fs = dbt_candidates(catalog, iso, "nt").get(abbr)
            if fs:
                todo.append((key, lambda b, c, f=fs: _dbt(f, b, c)))
    print(f"[nt-probes] {len(chapters)} chapters per edition; {len(todo)} editions to probe "
          f"({len(cache) - 1} cached)", flush=True)
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
    print(f"[nt-probes] probed {done}, not probed {failed} -> {CACHE}")


if __name__ == "__main__":
    main()
