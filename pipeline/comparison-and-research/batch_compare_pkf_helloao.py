#!/usr/bin/env python3
"""The third and final leg of the PKF/DBT/helloAO triangle — compare PKF
directly against helloAO, so a client can be shown the true pairwise
relationship between all three sources, not just each one's relationship to
DBT (see data/pkf-dbt-comparison*.json and data/helloao-dbt-phase*.json for
the other two legs).

Uses the SAME validated char-level engine as both other legs
(compare_pkf_dbt.py's normalize_chars/compare, unchanged) — only fetching
differs: PKF via rclone+decode.mjs (reused from batch_compare_pkf_dbt.py,
including its empirical multi-collection disambiguation for niy-like cases),
helloAO via its JSON API (reused from batch_compare_helloao_dbt.py's chapter
extractor). No PKF text is retained — fetched into a temp dir, deleted
immediately after each comparison, same discipline as every other script in
this pilot.

Candidate population: every (iso, helloao_id) pair where PKF has a
collection for that iso AND helloAO has a translation for that iso — 467
languages / 488 NT pairs (some languages have >1 helloAO translation).
Independent of whether DBT has anything for that iso — this leg doesn't need
DBT at all.

Usage:
    python3 scripts/batch_compare_pkf_helloao.py <out.json> [--book B] [--chapter N] [--limit N]
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from batch_compare_pkf_dbt import rclone_env, candidate_isos  # noqa: E402
from batch_compare_helloao_dbt import extract_helloao_chapter, HELLOAO_API  # noqa: E402
from compare_pkf_dbt import extract_pkf_chapter, compare  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE  # noqa: E402


def pkf_helloao_candidates() -> dict:
    """iso -> {"pkf_files": [...], "helloao_ids": [...]}"""
    pkf = json.loads((API_CACHE / "pkf-manifest.json").read_text())["languages"]
    helloao = json.loads((API_CACHE / "helloao" / "available_translations.json").read_text())["translations"]

    helloao_by_iso = {}
    for e in helloao:
        helloao_by_iso.setdefault(e["language"], []).append(e["id"])

    out = {}
    for iso, entry in pkf.items():
        if iso not in helloao_by_iso:
            continue
        collections = entry.get("collections") or []
        if not collections:
            continue
        out[iso] = {"pkf_files": [c["pkf"] for c in collections], "helloao_ids": helloao_by_iso[iso]}
    return out


def fetch_helloao_chapter(helloao_id: str, book: str, chapter: int) -> str | None:
    try:
        r = requests.get(f"{HELLOAO_API}/{helloao_id}/{book}/{chapter}.json", timeout=15)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        payload = r.json()
    except ValueError:
        return None
    return extract_helloao_chapter(payload.get("chapter", {})) or None


def fetch_pkf_chapter(iso: str, pkf_files: list, env: dict, bucket: str, tmpdir: Path,
                       book: str, chapter: int):
    """Mirrors batch_compare_pkf_dbt.py's fetch_and_extract, generalized for
    any book/chapter (that script hardcodes NT REV15 module globals)."""
    for pkf_file in pkf_files:
        safe_tag = pkf_file.replace("/", "_")
        pkf_path = tmpdir / f"{iso}_{safe_tag}.pkf"
        result = subprocess.run(
            ["rclone", "copyto", f"R2:{bucket}/pkf/{iso}/{pkf_file}", str(pkf_path)],
            capture_output=True, text=True, env=env,
        )
        if result.returncode != 0 or not pkf_path.exists():
            continue
        out_dir = tmpdir / f"{iso}_{safe_tag}_out"
        subprocess.run(
            ["node", "tools/pkf-decode/decode.mjs", str(pkf_path), "--out", str(out_dir), "--book", book],
            capture_output=True, text=True,
        )
        matches = list(out_dir.glob(f"*-{book}.usfm")) if out_dir.is_dir() else []
        pkf_chars = extract_pkf_chapter(matches[0], chapter) if matches else None
        for p in tmpdir.iterdir():
            if p.name.startswith(f"{iso}_"):
                shutil.rmtree(p) if p.is_dir() else p.unlink()
        if pkf_chars:
            return pkf_chars, pkf_file
    return None, None


def process_one(iso: str, info: dict, env: dict, bucket: str, tmpdir: Path, book: str, chapter: int) -> dict:
    pkf_chars, winning_pkf_file = fetch_pkf_chapter(iso, info["pkf_files"], env, bucket, tmpdir, book, chapter)
    if not pkf_chars:
        return {"status": "no_pkf_text"}

    scores = {}
    for hid in info["helloao_ids"]:
        hao_chars = fetch_helloao_chapter(hid, book, chapter)
        scores[hid] = round(compare(pkf_chars, hao_chars), 4) if hao_chars else None

    valid = {k: v for k, v in scores.items() if v is not None}
    if not valid:
        return {"status": "no_helloao_text", "attempted_helloao_ids": info["helloao_ids"]}

    best_id = max(valid, key=valid.get)
    return {"status": "compared", "pkf_file": winning_pkf_file, "best_match": best_id,
            "best_score": valid[best_id], "all_scores": scores}


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit("usage: batch_compare_pkf_helloao.py <out.json> [--book B] [--chapter N] [--limit N]")
    out_path = Path(args[0])
    book, chapter = "REV", 15
    if "--book" in args:
        book = args[args.index("--book") + 1]
    if "--chapter" in args:
        chapter = int(args[args.index("--chapter") + 1])
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    env, bucket = rclone_env()
    candidates = pkf_helloao_candidates()
    results = json.loads(out_path.read_text()) if out_path.exists() else {}

    todo = [iso for iso in candidates if iso not in results]
    if limit:
        todo = todo[:limit]

    print(f"[batch-pkf-helloao] {len(candidates)} total candidates, {len(results)} already done, "
          f"{len(todo)} to process this run ({book} {chapter})")

    tmpdir = Path(tempfile.mkdtemp(prefix="pkf_helloao_"))
    try:
        for i, iso in enumerate(todo, 1):
            try:
                entry = process_one(iso, candidates[iso], env, bucket, tmpdir, book, chapter)
            except Exception as e:
                entry = {"status": "error", "error": str(e)[:200]}
            results[iso] = entry
            print(f"  [{i}/{len(todo)}] {iso}: {entry.get('status')} (best_score={entry.get('best_score', '-')})")
            for p in tmpdir.iterdir():
                if p.name.startswith(f"{iso}_"):
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
            if i % 10 == 0:
                out_path.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        out_path.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    from collections import Counter
    tally = Counter(r.get("status") for r in results.values())
    print(f"\n[batch-pkf-helloao] done. {len(results)} total recorded.")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")
    dup = sum(1 for r in results.values() if r.get("best_score") == 1.0)
    print(f"  exact duplicates: {dup}")


if __name__ == "__main__":
    main()
