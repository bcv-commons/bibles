#!/usr/bin/env python3
"""Compare helloAO translations against DBT's own native versions, for
languages where helloAO offers a translation DBT's catalog doesn't reference
under any id (native or t:helloao: tagged) — i.e. a helloAO offering DBT's
own catalog structure doesn't already account for.

Triggered by a real question raised while building the PKF/DBT pilot: DBT's
catalog explicitly tags 49 rows as helloAO-sourced (t:helloao:<id>), 9 of
which sit alongside native DBT rows for the same language — verified (see
data/helloao-dbt-phase3.json) that 3 of those 9 are genuine catalog-internal
duplicates (maj/mam/poh — same translation listed twice under different
project codes). That raised the question of whether DBT's tagging is
exhaustive — it isn't: comparing helloAO's FULL catalog (1256 translations)
against DBT's by id-derivation (helloAO id = DBT id lowercased with '_'
inserted) found 779 helloAO translations with no id-match anywhere in DBT's
catalog, 527 of which are for a language where DBT already has >=1 native
version under a different id — a real, much larger duplicate-vs-distinct
question of the same shape as the whole PKF-vs-DBT pilot.

Uses the SAME validated char-level engine as PKF-vs-DBT (compare_pkf_dbt.py's
normalize_chars/compare, unchanged) — only the extraction step differs,
since helloAO serves structured JSON, not USFM. helloAO's chapter JSON shape:
  chapter.content = [ {type: "heading", ...} | {type: "verse", number, content: [...]} ]
  verse content items are either a plain string, {"text":..., "poem":N}, or
  markup-only dicts ({"noteId":...}, {"lineBreak":true}) — headings and
  markup-only items are skipped, matching how PKF's \\s headings are skipped.

No login/API key needed for helloAO (bible.helloao.org, unauthenticated,
no documented rate limit — still paced with a short sleep to be a good
citizen). DBT native text reuses whatever's already locally sampled in
data/text/BB/{nt,ot}; falls back to a live DBT fetch (get_text_content())
for any native id not yet sampled.

Usage:
    python3 scripts/batch_compare_helloao_dbt.py <targets.json> <out.json> [--limit N]

<targets.json> is a list of {"iso", "canon", "helloao_id", "native_ids": [...]}
(or single "native_id" — normalized to a list).
"""
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import download_language_content as dl  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_pkf_dbt import normalize_chars, compare  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import TEXT_DIR  # noqa: E402

HELLOAO_API = "https://bible.helloao.org/api"
SAMPLE_DIR = TEXT_DIR / "BB"


def extract_helloao_chapter(chapter_json: dict) -> str:
    parts = []
    for block in chapter_json.get("content", []):
        if block.get("type") != "verse":
            continue
        for item in block.get("content", []):
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
    return normalize_chars(" ".join(parts))


def dbt_native_chars(iso: str, canon: str, native_id: str, book: str, chapter: int) -> str | None:
    canon_dir = "nt" if canon == "nt" else "ot"
    base = SAMPLE_DIR / canon_dir / iso / native_id
    probe = f"{book}_{chapter:03d}_"
    local_files = list(base.rglob(f"{probe}*.txt")) if base.is_dir() else []
    if local_files:
        return "".join(normalize_chars(f.read_text(encoding="utf-8")) for f in local_files)

    result = dl.get_text_content(native_id, book, chapter)
    time.sleep(0.1)
    if not result or result.get("type") != "verses":
        return None
    text = " ".join(" ".join(item.get("verse_text", "").split()) for item in result["data"])
    return normalize_chars(text) or None


def process_one(target: dict) -> dict:
    iso, canon, helloao_id = target["iso"], target["canon"], target["helloao_id"]
    native_ids = target.get("native_ids") or ([target["native_id"]] if target.get("native_id") else [])
    book, chapter = ("REV", 15) if canon == "nt" else ("PSA", 117)

    try:
        r = requests.get(f"{HELLOAO_API}/{helloao_id}/{book}/{chapter}.json", timeout=15)
    except requests.RequestException as e:
        return {"status": "helloao_fetch_failed", "error": str(e)[:200]}
    if r.status_code != 200:
        return {"status": "helloao_fetch_failed", "error": f"http_{r.status_code}"}
    try:
        payload = r.json()
    except ValueError:
        # some ids return 200 with an empty/non-JSON body (e.g. book not
        # actually present despite the catalog listing it) — not a crash.
        return {"status": "helloao_no_text"}
    hao_chars = extract_helloao_chapter(payload.get("chapter", {}))
    if not hao_chars:
        return {"status": "helloao_no_text"}

    scores = {}
    for native_id in native_ids:
        dbt_chars = dbt_native_chars(iso, canon, native_id, book, chapter)
        scores[native_id] = round(compare(hao_chars, dbt_chars), 4) if dbt_chars else None

    valid_scores = {k: v for k, v in scores.items() if v is not None}
    if not valid_scores:
        return {"status": "no_dbt_sample", "attempted_native_ids": native_ids}

    best_id = max(valid_scores, key=valid_scores.get)
    return {"status": "compared", "best_match": best_id, "best_score": valid_scores[best_id],
            "all_scores": scores}


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit("usage: batch_compare_helloao_dbt.py <targets.json> <out.json> [--limit N]")
    targets_path, out_path = Path(args[0]), Path(args[1])
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    targets = json.loads(targets_path.read_text())
    results = json.loads(out_path.read_text()) if out_path.exists() else {}

    def key(t):
        return f"{t['iso']}:{t['canon']}:{t['helloao_id']}"

    todo = [t for t in targets if key(t) not in results]
    if limit:
        todo = todo[:limit]

    print(f"[batch-helloao] {len(targets)} total candidates, {len(results)} already done, "
          f"{len(todo)} to process this run")

    for i, t in enumerate(todo, 1):
        try:
            entry = process_one(t)
        except Exception as e:
            entry = {"status": "error", "error": str(e)[:200]}
        results[key(t)] = {**t, **entry}
        print(f"  [{i}/{len(todo)}] {key(t)}: {entry.get('status')} (best_score={entry.get('best_score', '-')})")
        if i % 10 == 0:
            out_path.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    out_path.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    from collections import Counter
    tally = Counter(r.get("status") for r in results.values())
    print(f"\n[batch-helloao] done. {len(results)} total recorded.")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")
    dup = [k for k, r in results.items() if r.get("best_score") == 1.0]
    if dup:
        print(f"  exact duplicates found: {len(dup)}")


if __name__ == "__main__":
    main()
