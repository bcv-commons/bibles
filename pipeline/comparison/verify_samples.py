#!/usr/bin/env python3
"""Verify whether previously-sampled DBT text is still live-fetchable, and
prune confirmed-dead content out of the published comparison data.

Motivated by a real case (2026-07-23): `BENBIB` (Bengali) was locally
sampled and verified byte-identical to `BNGDIP` back in Dec 2025
(data/text/BB local sample cache), and compare_all.py's local-cache-first
fetch strategy (see fetch_sources.py) means it has been silently treated
as "known good" in every comparison run since — even though DBT's live API
for this exact fileset id now 404s, while the catalog itself still lists
it unchanged. Since compare_all.py only ever re-fetches an id when its
(iso,canon) group is brand new or has a recorded `ids_failed` entry, a
fileset that goes offline AFTER being locally sampled is never
automatically re-checked. This script closes that gap.

For each given DBT distinct_id: finds every (iso, canon) where a local
sample exists for it, does a REAL live fetch (bypassing the cache
entirely — the whole point, since the cache is exactly what's stale),
and if it fails:
  - deletes the stale local sample file(s) for that (iso, canon, id)
  - removes the id from all-comparisons.json's ids_fetched + every score
    pair mentioning it, for that (iso, canon), and records it in a NEW
    `ids_removed` list — deliberately NOT the same as `ids_failed`.
    `ids_failed` still means "catalog-known, never positively confirmed
    reachable" (e.g. AUSWBT, which has 404'd every time it's ever been
    tried) and correctly keeps producing a bare placeholder row in
    catalog-overlap.json (see doc/catalog-overlap.md). `ids_removed` means
    "was POSITIVELY confirmed with real content, and is now POSITIVELY
    confirmed gone" — generate_catalog_overlap.py doesn't read this field
    at all, so a removed id produces no row whatsoever, not even a
    placeholder. Continuing to list it, even empty, would misrepresent a
    confirmed-gone edition as "maybe still an option."
  - strips any all-diagnosis.json entries mentioning the removed id
  - appends an audit record to internal-data/dead-dbt-filesets.json (why
    something disappeared — never published, just a local paper trail)

This only edits internal-data/comparison-results/*.json — run
generate_catalog_overlap.py again afterward to actually update the
published artifact, and republish separately once you've checked the diff.

Usage:
    python3 verify_samples.py --id BENBIB [--id OTHER_ID ...]
    python3 verify_samples.py --all   # sweep every locally-sampled DBT id
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import download_language_content as dl  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
from confirm_text_availability import resolve_fileset  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import ALL_COMPARISONS_FILE, ALL_DIAGNOSIS_FILE, API_CACHE, INTERNAL_DATA, TEXT_DIR  # noqa: E402

SAMPLE_DIR = TEXT_DIR / "BB"
DEAD_FILESETS_LOG = INTERNAL_DATA / "dead-dbt-filesets.json"
BOOK_FOR_CANON = {"nt": ("REV", 15), "ot": ("PSA", 117)}


def find_sampled_locations(distinct_id: str) -> list:
    """Every (iso, canon) where a local sample directory exists for this
    distinct_id, found by scanning rather than trusting the catalog (a
    sample can exist even if the catalog row has since changed)."""
    out = []
    for canon in ("nt", "ot"):
        base = SAMPLE_DIR / canon
        if not base.is_dir():
            continue
        for iso_dir in base.iterdir():
            if (iso_dir / distinct_id).is_dir():
                out.append((iso_dir.name, canon))
    return out


def all_sampled_ids() -> set:
    out = set()
    for canon in ("nt", "ot"):
        base = SAMPLE_DIR / canon
        if not base.is_dir():
            continue
        for iso_dir in base.iterdir():
            for id_dir in iso_dir.iterdir():
                if id_dir.is_dir():
                    out.add(id_dir.name)
    return out


def live_reachable(catalog: dict, iso: str, canon: str, distinct_id: str) -> bool:
    row = next((r for r in catalog["versions"]
                if r[0] == iso and r[1] == distinct_id and r[2].rstrip("p") == canon), None)
    if not row:
        # No longer even a catalog row for this (iso,canon,id) — treat as
        # gone, same as a live fetch failure.
        return False
    spec = next((f for f in row[3:] if f.split(":", 1)[0] in ("t", "T")), None)
    if not spec:
        return False
    fileset = resolve_fileset(distinct_id, spec)
    if not fileset:
        return False
    book, chapter = BOOK_FOR_CANON[canon]
    result = dl.get_text_content(fileset, book, chapter)
    time.sleep(0.1)
    return bool(result and result.get("type") == "verses" and result.get("data"))


def prune(comparisons: dict, diagnosis: dict, iso: str, canon: str, distinct_id: str) -> bool:
    key = f"{iso}:{canon}"
    sid = f"dbt:{distinct_id}"
    entry = comparisons.get(key)
    if not entry or sid not in entry.get("ids_fetched", []):
        return False

    entry["ids_fetched"] = [i for i in entry["ids_fetched"] if i != sid]
    entry["scores"] = {p: s for p, s in entry.get("scores", {}).items()
                        if sid not in p.split("|")}
    entry.setdefault("ids_removed", [])
    if sid not in entry["ids_removed"]:
        entry["ids_removed"].append(sid)
    entry["ids_removed"].sort()
    if not entry["ids_fetched"] and not entry.get("ids_failed"):
        entry["status"] = "no_text"

    removed_diag_keys = [k for k in diagnosis
                          if k.startswith(f"{iso}:{canon}:") and sid in k.split(":", 2)[2].split("|")]
    for k in removed_diag_keys:
        del diagnosis[k]

    return True


def main():
    args = sys.argv[1:]
    ids = []
    i = 0
    while i < len(args):
        if args[i] == "--id" and i + 1 < len(args):
            ids.append(args[i + 1])
            i += 2
        else:
            i += 1
    sweep_all = "--all" in args

    if not ids and not sweep_all:
        sys.exit("usage: verify_samples.py --id ID [--id ID ...] | --all")

    catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())
    comparisons = json.loads(ALL_COMPARISONS_FILE.read_text())
    diagnosis = json.loads(ALL_DIAGNOSIS_FILE.read_text()) if ALL_DIAGNOSIS_FILE.exists() else {}
    dead_log = json.loads(DEAD_FILESETS_LOG.read_text()) if DEAD_FILESETS_LOG.exists() else {}

    target_ids = sorted(all_sampled_ids()) if sweep_all else ids

    print(f"[verify-samples] checking {len(target_ids)} distinct_id(s)")
    total_checked, total_dead = 0, 0
    for distinct_id in target_ids:
        locations = find_sampled_locations(distinct_id)
        if not locations:
            print(f"  {distinct_id}: no local sample found anywhere, nothing to verify")
            continue
        for iso, canon in locations:
            total_checked += 1
            ok = live_reachable(catalog, iso, canon, distinct_id)
            if ok:
                print(f"  {iso}:{canon}:{distinct_id}  still reachable")
                continue

            total_dead += 1
            print(f"  {iso}:{canon}:{distinct_id}  CONFIRMED DEAD — pruning")

            sample_dir = SAMPLE_DIR / canon / iso / distinct_id
            if sample_dir.is_dir():
                for f in sample_dir.rglob("*"):
                    if f.is_file():
                        f.unlink()

            pruned = prune(comparisons, diagnosis, iso, canon, distinct_id)
            dead_log.setdefault(distinct_id, {})[f"{iso}:{canon}"] = {
                "confirmed_dead_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "was_pruned_from_comparisons": pruned,
            }

    ALL_COMPARISONS_FILE.write_text(json.dumps(comparisons, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    ALL_DIAGNOSIS_FILE.write_text(json.dumps(diagnosis, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    DEAD_FILESETS_LOG.parent.mkdir(parents=True, exist_ok=True)
    DEAD_FILESETS_LOG.write_text(json.dumps(dead_log, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\n[verify-samples] done. {total_checked} (iso,canon,id) location(s) checked, "
          f"{total_dead} confirmed dead and pruned.")
    print("Run generate_catalog_overlap.py to update the published artifact.")


if __name__ == "__main__":
    main()
