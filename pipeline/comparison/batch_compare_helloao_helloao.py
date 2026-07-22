#!/usr/bin/env python3
"""Compare helloAO's own translations against EACH OTHER, for every
language where helloAO has >=2 translations - the same-source gap for
helloAO that batch_compare_dbt_dbt.py fills for DBT. Found by direct
question after building the DBT leg: "is helloAO vs helloAO covered too?"
It wasn't - 109 languages have >=2 helloAO translations (eng alone has 51),
and nothing had ever checked whether any of them duplicate each other.

(The fourth same-source pairing, PKF-vs-PKF, is a non-issue: only niy has
more than one PKF collection in the whole manifest, and that case is
already resolved via the earlier collection-identity investigation - one
collection is French, the other genuinely niy.)

Uses the SAME validated char-level engine as every other leg
(compare_pkf_dbt.py's normalize_chars/compare, unchanged) - only fetching
differs: helloAO's own chapter JSON API, reusing extract_helloao_chapter
from batch_compare_helloao_dbt.py.

Each translation's text is fetched once and compared against every other
translation in its language group in memory - no repeat fetches for a
group of N translations (N fetches, not N^2).

Usage:
    python3 batch_compare_helloao_helloao.py [--book B] [--chapter N] [--limit N]
"""
import json
import sys
import time
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from batch_compare_helloao_dbt import extract_helloao_chapter, HELLOAO_API  # noqa: E402
from compare_pkf_dbt import compare  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, COMPARISON_RESULTS_DIR  # noqa: E402

OUT_PATH = COMPARISON_RESULTS_DIR / "helloao-helloao-comparison.json"


def candidate_groups():
    """iso -> [translation_id, ...] for every language with >=2 helloAO
    translations."""
    hao = json.loads((API_CACHE / "helloao" / "available_translations.json").read_text())["translations"]
    by_lang = defaultdict(list)
    for e in hao:
        by_lang[e["language"]].append(e["id"])
    return {k: v for k, v in by_lang.items() if len(v) >= 2}


def fetch_chapter(translation_id: str, book: str, chapter: int) -> str | None:
    try:
        r = requests.get(f"{HELLOAO_API}/{translation_id}/{book}/{chapter}.json", timeout=15)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        payload = r.json()
    except ValueError:
        return None
    return extract_helloao_chapter(payload.get("chapter", {})) or None


def process_group(iso: str, translation_ids: list, book: str, chapter: int) -> dict:
    texts = {}
    for tid in translation_ids:
        chars = fetch_chapter(tid, book, chapter)
        time.sleep(0.1)
        if chars:
            texts[tid] = chars

    scores = {}
    for a, b in combinations(sorted(texts), 2):
        scores[f"{a}|{b}"] = round(compare(texts[a], texts[b]), 4)

    return {
        "status": "compared" if scores else "no_text",
        "translations_fetched": sorted(texts.keys()),
        "translations_failed": sorted(set(translation_ids) - set(texts)),
        "scores": scores,
    }


def main():
    args = sys.argv[1:]
    book, chapter = "REV", 15
    if "--book" in args:
        book = args[args.index("--book") + 1]
    if "--chapter" in args:
        chapter = int(args[args.index("--chapter") + 1])
    canon = "nt" if book == "REV" else "ot"
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    groups = candidate_groups()
    results = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}

    def key(iso):
        return f"{iso}:{canon}"

    todo = [iso for iso in groups if key(iso) not in results]
    if limit:
        todo = todo[:limit]

    print(f"[batch-helloao-helloao] {len(groups)} candidate groups ({canon}), "
          f"{len(results)} already done, {len(todo)} to process this run")

    for i, iso in enumerate(todo, 1):
        try:
            entry = process_group(iso, groups[iso], book, chapter)
        except Exception as e:
            entry = {"status": "error", "error": str(e)[:200]}
        entry.update({"iso": iso, "canon": canon})
        results[key(iso)] = entry
        n_pairs = len(entry.get("scores", {}))
        dup = sum(1 for s in entry.get("scores", {}).values() if s == 1.0)
        print(f"  [{i}/{len(todo)}] {key(iso)}: {entry['status']} "
              f"({n_pairs} pair(s), {dup} exact duplicate(s))")
        if i % 10 == 0:
            OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    from collections import Counter
    tally = Counter(r["status"] for r in results.values())
    total_dup = sum(1 for r in results.values() for s in r.get("scores", {}).values() if s == 1.0)
    total_pairs = sum(len(r.get("scores", {})) for r in results.values())
    print(f"\n[batch-helloao-helloao] done. {len(results)} groups recorded.")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")
    print(f"  {total_pairs} total pairs compared, {total_dup} exact duplicates found")


if __name__ == "__main__":
    main()
