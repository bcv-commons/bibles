#!/usr/bin/env python3
"""Unified taxonomy diagnosis — replaces the five separate diagnose_*.py
scripts (diagnose_pkf_dbt_diff.py, diagnose_helloao_dbt_diff.py,
diagnose_pkf_helloao_diff.py, diagnose_dbt_dbt_diff.py,
diagnose_helloao_helloao_diff.py), reading from compare_all.py's single
all-comparisons.json instead of five separate per-leg files.

Per the same scoping rule every prior diagnosis script used: only each id's
single BEST-MATCH partner (across ALL sources at once now, not per-leg) is
diagnosed, not every pair it was compared against. Pairs are deduplicated —
a mutual best-match only gets diagnosed once.

Uses diagnose_taxonomy.py unchanged (see its module docstring for the full
taxonomy). Text is re-fetched fresh via fetch_sources.py for each diagnosed
pair and discarded immediately after — no PKF text retained. For a PKF id,
the specific collection to re-fetch is read from the comparison entry's
pkf_source_ref (already resolved once during compare_all.py's own
disambiguation — never re-disambiguated here).

Resumable: writes incrementally, skips pairs already recorded on rerun.

Book/chapter is derived per-pair from its own canon (REV 15 for nt, PSA 117
for ot) — never a single global default, since a single run here processes
candidates from BOTH canons at once (unlike compare_all.py, which is
deliberately one-canon-per-invocation). For an OT group that used
compare_all.py's PSA51 fallback (see its OT_FALLBACK), re-fetching MUST
also use PSA51, not the plain PSA117 default — read from the comparison
entry's own recorded `probe` field, never assumed.

Usage:
    python3 diagnose_all.py [--limit N]
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comparison"))
from compare_pkf_dbt import compare  # noqa: E402
from fetch_sources import dbt_text, helloao_text, pkf_text, rclone_env  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, COMPARISON_RESULTS_DIR  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnose_taxonomy import classify  # noqa: E402
from confirm_text_availability import resolve_fileset  # noqa: E402

IN_PATH = COMPARISON_RESULTS_DIR / "all-comparisons.json"
OUT_PATH = COMPARISON_RESULTS_DIR / "all-diagnosis.json"


def best_match_pairs() -> dict:
    """(iso, canon, sorted_pair_tuple) -> recorded_score, for every id's
    single best (max-score) < 1.0 partner within its (iso,canon) group.
    Deduplicated — a mutual best-match pair is only diagnosed once."""
    data = json.loads(IN_PATH.read_text())
    out = {}
    for entry in data.values():
        scores = entry.get("scores", {})
        ids = entry.get("ids_fetched", [])
        for x in ids:
            best_score, best_partner = -1, None
            for pair, score in scores.items():
                a, b = pair.split("|")
                if x in (a, b):
                    other = b if a == x else a
                    if score > best_score:
                        best_score, best_partner = score, other
            if best_partner and best_score < 1.0:
                key = (entry["iso"], entry["canon"], tuple(sorted([x, best_partner])))
                out[key] = best_score
    return out


def fetch_for_id(sid: str, iso: str, canon: str, book: str, chapter: int,
                  catalog: dict, pkf_source_ref: str | None,
                  env: dict, bucket: str, tmpdir: Path) -> str | None:
    source, mid = sid.split(":", 1)
    if source == "dbt":
        row = next((r for r in catalog["versions"]
                    if r[0] == iso and r[1] == mid and r[2].rstrip("p") == canon), None)
        if not row:
            return None
        spec = next((f for f in row[3:] if f.split(":", 1)[0] in ("t", "T")), None)
        if not spec:
            return None
        fileset = resolve_fileset(mid, spec)
        return dbt_text(iso, canon, mid, fileset, book, chapter) if fileset else None
    if source == "helloao":
        return helloao_text(mid, book, chapter)
    if source == "pkf":
        return pkf_text(iso, pkf_source_ref, book, chapter, env, bucket, tmpdir) if pkf_source_ref else None
    return None


BOOK_FOR_CANON = {"nt": ("REV", 15), "ot": ("PSA", 117)}
OT_FALLBACK = ("PSA", 51)


def process_one(iso: str, canon: str, a: str, b: str, recorded_score: float, book: str, chapter: int,
                 catalog: dict, pkf_source_ref: str | None, env: dict, bucket: str, tmpdir: Path) -> dict:
    text_a = fetch_for_id(a, iso, canon, book, chapter, catalog, pkf_source_ref, env, bucket, tmpdir)
    text_b = fetch_for_id(b, iso, canon, book, chapter, catalog, pkf_source_ref, env, bucket, tmpdir)
    for p in tmpdir.iterdir():
        if p.name.startswith(f"{iso}_"):
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    if not text_a or not text_b:
        return {"status": "no_text"}

    live_score = compare(text_a, text_b)
    entry = classify(live_score, text_a, text_b, compare)
    entry["status"] = "diagnosed"
    entry["recorded_score"] = recorded_score
    if abs(live_score - recorded_score) > 0.001:
        entry["score_drift_warning"] = True
    return entry


def main():
    args = sys.argv[1:]
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    comparisons = json.loads(IN_PATH.read_text())
    pkf_refs = {f"{v['iso']}:{v['canon']}": v.get("pkf_source_ref") for v in comparisons.values()}
    # A comparison group may have used the PSA51 fallback (compare_all.py's
    # OT_FALLBACK, see its module docstring) instead of the default PSA117 —
    # re-fetching for diagnosis MUST use whichever probe the actual
    # comparison used, or the re-fetch fails for a group that genuinely
    # compared fine (found 2026-07-28: 7 pairs incorrectly came back
    # "no_text" here despite real scores on record, because this always
    # defaulted to PSA117 regardless of what compare_all.py actually used).
    probe_by_group = {
        f"{v['iso']}:{v['canon']}": OT_FALLBACK if v.get("probe") == "PSA51" else BOOK_FOR_CANON[v["canon"]]
        for v in comparisons.values()
    }
    catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())

    candidates = best_match_pairs()
    results = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}

    def key(iso, canon, pair):
        return f"{iso}:{canon}:{pair[0]}|{pair[1]}"

    todo = [k for k in candidates if key(*k) not in results]
    if limit:
        todo = todo[:limit]

    print(f"[diagnose-all] {len(candidates)} candidates, {len(results)} already done, "
          f"{len(todo)} to process this run")

    env, bucket = rclone_env()
    tmpdir = Path(tempfile.mkdtemp(prefix="diagnose_all_"))
    try:
        for i, (iso, canon, pair) in enumerate(todo, 1):
            a, b = pair
            pkf_source_ref = pkf_refs.get(f"{iso}:{canon}")
            book, chapter = probe_by_group.get(f"{iso}:{canon}", BOOK_FOR_CANON[canon])
            try:
                entry = process_one(iso, canon, a, b, candidates[(iso, canon, pair)], book, chapter,
                                     catalog, pkf_source_ref, env, bucket, tmpdir)
            except Exception as e:
                entry = {"status": "error", "error": str(e)[:200]}
            entry.update({"iso": iso, "canon": canon, "a": a, "b": b})
            results[key(iso, canon, pair)] = entry
            tag = entry.get("category", entry["status"])
            print(f"  [{i}/{len(todo)}] {key(iso, canon, pair)}: {tag} (score={entry.get('best_score', '-')})")
            if i % 10 == 0:
                OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    from collections import Counter
    tally = Counter(r.get("category", r["status"]) for r in results.values())
    print(f"\n[diagnose-all] done. {len(results)} total recorded.")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
