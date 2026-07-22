#!/usr/bin/env python3
"""Compare DBT's own native versions against EACH OTHER, for every
language where DBT has >=2 native text-bearing versions for a canon —
the one comparison leg the whole pilot never actually ran. PKF-vs-DBT,
helloAO-vs-DBT, and PKF-vs-helloAO all assume DBT's own multiple versions
are already known-distinct from each other; nothing ever verified that.

Triggered by a client spot-check request on spa's DBT-only editions
(SPARVC's name, "Reina Valera 1909", matches SPNR02's — worth checking
directly rather than trusting the catalog's implicit "these are all
different" assumption). A quick manual check before building this found
two real, previously-undetected findings in that one language alone:
SPAWTC vs SPAERV scored an exact 1.0 (a genuine DBT-catalog-internal
duplicate, same shape as the earlier maj/mam/poh finding — just never
caught because this specific comparison had never been run), and SPARVC
vs SPNR02 scored 0.9394 (confirms the naming hunch — same base edition
family, not a literal duplicate, but close enough to need a proper
taxonomy diagnosis rather than being left as a bare score).

Uses the SAME validated char-level engine as every other leg
(compare_pkf_dbt.py's normalize_chars/compare, unchanged) — only fetching
differs: DBT's own get_text_content() (download_language_content.py),
resolving each catalog row's t:/T: tag to an actual fetchable fileset id
via resolve_fileset() (confirm_text_availability.py) rather than assuming
the bare distinct_id is fetchable (it isn't, for most rows - confirmed
directly: 5 of 7 spa NT versions 404'd until this was applied).

Each version's text is fetched once and compared against every other
version in its (iso, canon) group in memory - no repeat fetches for a
group of N versions (N fetches, not N^2).

Usage:
    python3 batch_compare_dbt_dbt.py [--book B] [--chapter N] [--limit N]
"""
import json
import sys
import time
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import download_language_content as dl  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
from confirm_text_availability import resolve_fileset  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_pkf_dbt import normalize_chars, compare  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, COMPARISON_RESULTS_DIR  # noqa: E402

OUT_PATH = COMPARISON_RESULTS_DIR / "dbt-dbt-comparison.json"


def candidate_groups():
    """(iso, canon) -> {distinct_id: fileset_id}, for every group with
    >=2 native (non-helloAO/ebible, text-bearing) DBT versions."""
    catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())
    groups = {}
    for row in catalog["versions"]:
        iso, distinct_id, canon = row[0], row[1], row[2]
        canon_plain = canon.rstrip("p")
        text_spec = next((f for f in row[3:] if f.split(":", 1)[0] in ("t", "T")), None)
        if not text_spec:
            continue
        fileset_id = resolve_fileset(distinct_id, text_spec)
        if not fileset_id:
            continue
        groups.setdefault((iso, canon_plain), {})[distinct_id] = fileset_id
    return {k: v for k, v in groups.items() if len(v) >= 2}


def process_group(iso: str, canon: str, version_filesets: dict, book: str, chapter: int) -> dict:
    texts = {}
    for distinct_id, fileset_id in version_filesets.items():
        result = dl.get_text_content(fileset_id, book, chapter)
        time.sleep(0.1)
        if result and result.get("type") == "verses":
            text = " ".join(item.get("verse_text", "") for item in result["data"])
            norm = normalize_chars(text)
            if norm:
                texts[distinct_id] = norm

    scores = {}
    for a, b in combinations(sorted(texts), 2):
        scores[f"{a}|{b}"] = round(compare(texts[a], texts[b]), 4)

    return {
        "status": "compared" if scores else "no_text",
        "versions_fetched": sorted(texts.keys()),
        "versions_failed": sorted(set(version_filesets) - set(texts)),
        "scores": scores,
    }


def main():
    args = sys.argv[1:]
    book, chapter = "REV", 15
    if "--book" in args:
        book = args[args.index("--book") + 1]
    if "--chapter" in args:
        chapter = int(args[args.index("--chapter") + 1])
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    groups = candidate_groups()
    results = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}

    def key(iso, canon):
        return f"{iso}:{canon}"

    todo = [(iso, canon) for (iso, canon) in groups if key(iso, canon) not in results]
    if limit:
        todo = todo[:limit]

    print(f"[batch-dbt-dbt] {len(groups)} candidate groups, {len(results)} already done, "
          f"{len(todo)} to process this run ({book} {chapter})")

    for i, (iso, canon) in enumerate(todo, 1):
        try:
            entry = process_group(iso, canon, groups[(iso, canon)], book, chapter)
        except Exception as e:
            entry = {"status": "error", "error": str(e)[:200]}
        entry.update({"iso": iso, "canon": canon})
        results[key(iso, canon)] = entry
        n_pairs = len(entry.get("scores", {}))
        dup = sum(1 for s in entry.get("scores", {}).values() if s == 1.0)
        print(f"  [{i}/{len(todo)}] {key(iso, canon)}: {entry['status']} "
              f"({n_pairs} pair(s), {dup} exact duplicate(s))")
        if i % 10 == 0:
            OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    from collections import Counter
    tally = Counter(r["status"] for r in results.values())
    total_dup = sum(1 for r in results.values() for s in r.get("scores", {}).values() if s == 1.0)
    total_pairs = sum(len(r.get("scores", {})) for r in results.values())
    print(f"\n[batch-dbt-dbt] done. {len(results)} groups recorded.")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")
    print(f"  {total_pairs} total pairs compared, {total_dup} exact duplicates found")


if __name__ == "__main__":
    main()
