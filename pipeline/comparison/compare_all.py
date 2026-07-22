#!/usr/bin/env python3
"""Unified comparison pipeline — replaces the five separate leg scripts
(batch_compare_pkf_dbt.py, batch_compare_helloao_dbt.py,
batch_compare_pkf_helloao.py, batch_compare_dbt_dbt.py,
batch_compare_helloao_helloao.py) with ONE per-language pass: every
candidate id across all three sources is fetched EXACTLY ONCE (see
fetch_sources.py), then every pairwise score is computed from that
in-memory cache — collapsing what used to be up to 3 redundant fetches of
the same PKF/helloAO text (plus an inconsistent live-vs-cached DBT fetch)
into one, and replacing 5 near-duplicate ~150-line scripts with one.

Candidate population for a given canon: every iso with >=2 candidate ids
across DBT-native + helloAO + PKF (PKF counts as at most 1 id — its
multi-collection case, e.g. niy, is disambiguated internally, not exposed
as separate candidates). This single filter exactly subsumes all 5 of the
old scripts' separate candidate-selection criteria: >=1 DBT + >=1 helloAO
(old helloao-dbt leg), >=1 PKF + >=1 DBT (old pkf-dbt leg), >=1 PKF + >=1
helloAO (old pkf-helloao leg), >=2 DBT alone (old dbt-dbt leg), >=2 helloAO
alone (old helloao-helloao leg) — every one of those conditions implies
total candidate count >= 2.

Output: one row per (iso, canon) in internal-data/comparison-results/
all-comparisons.json, with a single full pairwise score matrix across every
source-prefixed id (dbt:X / helloao:Y / pkf:Z) — directly consumable by
generate_catalog_overlap.py's union-find with no per-leg-specific loader.

Verdict-only, resumable (skips (iso,canon) keys already recorded, retries
keys with any failed id — the retry-on-partial-failure fix from
batch_compare_dbt_dbt.py/batch_compare_helloao_helloao.py, carried over
here from the start rather than needing to be discovered again). No PKF
text is ever retained.

A single invocation only ever touches ONE canon, derived from --book (same
"nt" if book=="REV" else "ot" pattern the other same-source scripts use) —
this is deliberate: batch_compare_dbt_dbt.py's original bug was processing
both canons under one hardcoded book/chapter default, silently comparing
OT-tagged filesets with NT text. Never repeat that mistake here.

Usage:
    python3 compare_all.py [--book B] [--chapter N] [--limit N] [--iso ISO,ISO,...]
"""
import json
import shutil
import sys
import tempfile
from collections import defaultdict
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_pkf_dbt import compare  # noqa: E402
from fetch_sources import dbt_text, helloao_text, pkf_text, rclone_env  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
from confirm_text_availability import resolve_fileset  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, COMPARISON_RESULTS_DIR  # noqa: E402

OUT_PATH = COMPARISON_RESULTS_DIR / "all-comparisons.json"


def dbt_candidates(catalog: dict, iso: str, canon: str) -> dict:
    """distinct_id -> fileset_id for every native (non-helloAO/ebible-
    tagged) text-bearing DBT row for this (iso, canon). resolve_fileset()
    already returns None for t:helloao:/t:ebible: rows, so those are
    naturally excluded without a separate filter."""
    out = {}
    for row in catalog["versions"]:
        if row[0] != iso or row[2].rstrip("p") != canon:
            continue
        text_spec = next((f for f in row[3:] if f.split(":", 1)[0] in ("t", "T")), None)
        if not text_spec:
            continue
        fileset_id = resolve_fileset(row[1], text_spec)
        if fileset_id:
            out[row[1]] = fileset_id
    return out


def pkf_candidates(pkf_manifest: dict, iso: str, canon: str) -> list:
    entry = pkf_manifest.get(iso) or {}
    collections = entry.get("collections") or []
    if not collections:
        return []
    if canon == "ot":
        collections = [c for c in collections if (c.get("coverage") or {}).get("o")]
    return [c["pkf"] for c in collections]


def all_candidates(catalog: dict, helloao_by_iso: dict, pkf_manifest: dict, canon: str) -> dict:
    """iso -> (dbt_ids, hao_ids, pkf_files), restricted to isos with >=1
    total candidate id for this canon. The threshold is deliberately >=1,
    not >=2: even a single known id (e.g. niy:ot, which has only a PKF
    collection and no DBT/helloAO OT content) still gets a placeholder row
    in the published output — matching the original generate_catalog_overlap.py's
    behavior (it built its node set from catalog/manifest presence directly,
    independent of whether anything existed to compare against). Losing
    that placeholder would be a real, silent regression for any client
    checking "does this id exist at all" via catalog-overlap.json."""
    isos = {row[0] for row in catalog["versions"] if row[2].rstrip("p") == canon}
    isos |= set(helloao_by_iso.keys())
    isos |= set(pkf_manifest.keys())

    out = {}
    for iso in sorted(isos):
        dbt_ids = dbt_candidates(catalog, iso, canon)
        hao_ids = helloao_by_iso.get(iso, [])
        pkf_files = pkf_candidates(pkf_manifest, iso, canon)
        n = len(dbt_ids) + len(hao_ids) + (1 if pkf_files else 0)
        if n >= 1:
            out[iso] = (dbt_ids, hao_ids, pkf_files)
    return out


def sole_candidate_id(iso: str, dbt_ids: dict, hao_ids: list, pkf_files: list) -> str:
    """The single source-prefixed id for an (iso,canon) with exactly one
    total candidate — nothing to compare against, so no fetch is needed at
    all; the published row is the same bare placeholder regardless of
    whether the id would have fetched successfully. Whichever of the three
    is non-empty is, by construction (all_candidates() only calls this when
    the total count is exactly 1), the sole candidate."""
    if dbt_ids:
        return f"dbt:{next(iter(dbt_ids))}"
    if hao_ids:
        return f"helloao:{hao_ids[0]}"
    return f"pkf:{iso.upper()}PKF"


def process_language(iso: str, canon: str, dbt_ids: dict, hao_ids: list, pkf_files: list,
                      book: str, chapter: int, env: dict, bucket: str, tmpdir: Path) -> dict:
    texts = {}
    failed = []

    for distinct_id, fileset_id in dbt_ids.items():
        t = dbt_text(iso, canon, distinct_id, fileset_id, book, chapter)
        (texts.__setitem__(f"dbt:{distinct_id}", t) if t else failed.append(f"dbt:{distinct_id}"))

    for hid in hao_ids:
        t = helloao_text(hid, book, chapter)
        (texts.__setitem__(f"helloao:{hid}", t) if t else failed.append(f"helloao:{hid}"))

    pkf_source_ref = None
    if pkf_files:
        best_chars, best_file, best_score = None, None, -1.0
        for pkf_file in pkf_files:
            chars = pkf_text(iso, pkf_file, book, chapter, env, bucket, tmpdir)
            for p in tmpdir.iterdir():
                if p.name.startswith(f"{iso}_"):
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
            if not chars:
                continue
            # Single collection (overwhelming majority): use it directly.
            # Multiple collections (currently only niy): disambiguate
            # empirically by scoring against whatever's already fetched —
            # same principle as the original pkf-dbt pilot's niy handling,
            # just generalized to score against ANY already-fetched source,
            # not only DBT.
            if len(pkf_files) == 1:
                best_chars, best_file, best_score = chars, pkf_file, 1.0
                break
            local_best = max((compare(chars, t) for t in texts.values()), default=0.0)
            if local_best > best_score:
                best_chars, best_file, best_score = chars, pkf_file, local_best
        if best_chars:
            texts[f"pkf:{iso.upper()}PKF"] = best_chars
            pkf_source_ref = best_file
        else:
            failed.append(f"pkf:{iso.upper()}PKF")

    scores = {}
    for a, b in combinations(sorted(texts), 2):
        scores[f"{a}|{b}"] = round(compare(texts[a], texts[b]), 4)

    entry = {
        "status": "compared" if scores else "no_text",
        "ids_fetched": sorted(texts.keys()),
        "ids_failed": sorted(failed),
        "scores": scores,
    }
    if pkf_source_ref:
        entry["pkf_source_ref"] = pkf_source_ref
    return entry


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
    iso_filter = None
    if "--iso" in args:
        iso_filter = set(args[args.index("--iso") + 1].split(","))

    catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())
    helloao_translations = json.loads((API_CACHE / "helloao" / "available_translations.json").read_text())["translations"]
    helloao_by_iso = defaultdict(list)
    for e in helloao_translations:
        helloao_by_iso[e["language"]].append(e["id"])
    pkf_manifest = json.loads((API_CACHE / "pkf-manifest.json").read_text())["languages"]

    candidates = all_candidates(catalog, helloao_by_iso, pkf_manifest, canon)
    if iso_filter:
        candidates = {iso: v for iso, v in candidates.items() if iso in iso_filter}

    results = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}

    def key(iso):
        return f"{iso}:{canon}"

    # Retry any iso whose recorded entry has a non-empty ids_failed the same
    # as an unattempted one — see batch_compare_dbt_dbt.py's CLAUDE.local.md
    # history for why a group marked "done" after one attempt must not skip
    # retrying genuinely-transient failures forever.
    never_attempted = [iso for iso in candidates if key(iso) not in results]
    retry_candidates = [iso for iso in candidates
                         if key(iso) in results and results[key(iso)].get("ids_failed")]
    todo = never_attempted + retry_candidates
    if limit:
        todo = todo[:limit]

    print(f"[compare-all] {len(candidates)} candidate languages ({canon}), {len(results)} already done, "
          f"{len(never_attempted)} unattempted, {len(retry_candidates)} retrying failed ids, "
          f"{len(todo)} to process this run ({book} {chapter})")

    env, bucket = rclone_env()
    tmpdir = Path(tempfile.mkdtemp(prefix="compare_all_"))
    try:
        for i, iso in enumerate(todo, 1):
            dbt_ids, hao_ids, pkf_files = candidates[iso]
            n = len(dbt_ids) + len(hao_ids) + (1 if pkf_files else 0)
            if n < 2:
                # Nothing to compare against — skip the fetch entirely
                # (the published row is the same bare placeholder either
                # way). This is the majority case (roughly half the full
                # population): most languages have exactly one DBT version
                # and no PKF/helloAO coverage at all.
                entry = {"status": "single_source", "ids_fetched": [sole_candidate_id(iso, dbt_ids, hao_ids, pkf_files)],
                         "ids_failed": [], "scores": {}}
                results[key(iso)] = {**entry, "iso": iso, "canon": canon}
                print(f"  [{i}/{len(todo)}] {key(iso)}: single_source (no fetch needed)")
                continue
            try:
                entry = process_language(iso, canon, dbt_ids, hao_ids, pkf_files, book, chapter, env, bucket, tmpdir)
            except Exception as e:
                entry = {"status": "error", "error": str(e)[:200]}
            entry.update({"iso": iso, "canon": canon})
            results[key(iso)] = entry
            n_ids = len(entry.get("ids_fetched", []))
            n_pairs = len(entry.get("scores", {}))
            dup = sum(1 for s in entry.get("scores", {}).values() if s == 1.0)
            print(f"  [{i}/{len(todo)}] {key(iso)}: {entry['status']} "
                  f"({n_ids} id(s), {n_pairs} pair(s), {dup} exact duplicate(s))")
            if i % 10 == 0:
                OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    from collections import Counter
    tally = Counter(r["status"] for r in results.values())
    total_pairs = sum(len(r.get("scores", {})) for r in results.values())
    total_dup = sum(1 for r in results.values() for s in r.get("scores", {}).values() if s == 1.0)
    print(f"\n[compare-all] done. {len(results)} (iso,canon) entries recorded.")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")
    print(f"  {total_pairs} total pairs compared, {total_dup} exact duplicates found")


if __name__ == "__main__":
    main()
