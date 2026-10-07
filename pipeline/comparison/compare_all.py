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

A group automatically retries with fallback probe books, per canon, when
the primary probe leaves any id unfetched — see FALLBACK_PROBES below for
why (some translations genuinely lack the primary probe book, or have a
weak-signal chapter in it) and why the retry always covers the whole
group, never a single id.

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
from fetch_sources import dbt_text, helloao_text, pkf_text, openbible_text, rclone_env  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
from confirm_text_availability import resolve_fileset  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, COMPARISON_RESULTS_DIR, CATALOG_DIR  # noqa: E402

# Added 2026-09-15: Biblica's Open Bible catalog as a fourth source
# (`openbible:`). Unlike PKF (one ambiguous manifest entry per language,
# needing empirical disambiguation), each Biblica text project is already
# a separate, named, licensed edition — so it's a LIST of candidates per
# iso, handled the same way helloAO's hao_ids list already is, not PKF's
# special-case single-slot scoring logic. 18% of Biblica text-having
# languages (75/412) have more than one project, a real, not-rare case.
OPENBIBLE_PROJECTS_FILE = API_CACHE / "openbible" / "projects.json"
OPENBIBLE_EDITIONS_FILE = CATALOG_DIR / "openbible-editions.json"

OUT_PATH = COMPARISON_RESULTS_DIR / "all-comparisons.json"

# A client (2026-07-28) reported cpy_wbt (helloAO) OT as a false-positive
# unreachable id: checked directly, PSA 117 genuinely returns a real 200
# with 0 verses for this specific translation (confirmed via the raw
# response, not a broken endpoint) — but PSA 51, GEN 1, etc. all work
# fine. PKF's own manifest for cpy confirms the same pattern independently:
# its OT PSA coverage is "5,22,40,51,89,91,103,119,148" — no 117, but 51 is
# there. PSA 117 (2 verses) has always been documented as having "weak
# discriminating power" (see doc/catalog-overlap.md's `probes` field, which
# already lists PSA51 as the OT fallback) — this generalizes that existing,
# previously narrow (4-language, PKF-vs-DBT-only) PSA51 refinement to the
# whole pipeline. Retrying is done for the WHOLE (iso,canon) group, never
# per-id: comparing one id's PSA117 text against another id's PSA51 text
# would be meaningless, so a group either uses PSA117 for everyone or PSA51
# for everyone, never a mix.
#
# NT fallback added 2026-10-07, same shape bug, different cause: lexeme-
# aligner's "orphan editions" cleanup flagged eko_wbt/lit_bbi/tke_wbt and
# PKF's ztp_ztp as unreachable (r:false). Checked directly against their
# real sources (helloAO's own API, PKF's own manifest coverage): all are
# genuinely live, just small NT-portion editions with no Revelation at all
# (eko_wbt: GEN/EXO/JON/MAT/MRK/LUK/JHN/ACT/1TI; lit_bbi: LUK/ACT; tke_wbt:
# LUK only; ztp_ztp's NT coverage is MRK/1TI/2TI/PHM/JAS/1PE/2PE/1JN/2JN/3JN,
# no Gospels at all). Unlike OT's single-translation PSA117 gap, there's no
# one NT book every small portion has, so this tries several, in the order
# a literacy-first translation project most commonly adds books, stopping
# as soon as a probe leaves nothing unfetched. Same whole-group-retry rule
# as OT: never mix probe books within one (iso,canon) comparison.
FALLBACK_PROBES = {
    # RUT/JON added 2026-10-07 alongside the NT fix: kprpkf/ztppkf's real
    # OT coverage (confirmed via PKF's own manifest) is Ruth and Jonah
    # only — the smallest, most commonly-translated-first OT portions,
    # same reasoning as the NT list below.
    "ot": [("PSA", 51), ("RUT", 1), ("JON", 1)],
    "nt": [("MRK", 1), ("LUK", 1), ("JHN", 1), ("MAT", 1), ("ACT", 1), ("JAS", 1)],
}


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


def openbible_candidates(openbible_by_iso: dict, openbible_abbr: dict, iso: str) -> list:
    """(project_id, abbr) pairs for every Biblica text project for this
    iso that has a resolved yaapi.bible abbreviation — canon membership
    isn't filtered here (Biblica's cached project data has no NT/OT scope
    field); a project's zip either has the requested book or
    openbible_text() returns None for it, same as any other source's
    ordinary fetch failure.

    Restricted to abbr-mapped projects only, decided 2026-09-19: a raw
    Biblica hex project id was judged a dangerous id to publish (once a
    client depends on it, migrating away later is costly) — unmapped
    projects are excluded from comparison entirely here, the same
    restriction already applied to catalog-index.json/overlap.json's `o`
    rows, so this candidate list stays consistent with what actually gets
    published rather than producing ids that would need filtering out
    downstream."""
    project_ids = openbible_by_iso.get(iso, [])
    out = []
    for pid in project_ids:
        entry = openbible_abbr.get(pid)
        if entry:
            out.append((pid, entry["abbr"]))
    return out


def all_candidates(catalog: dict, helloao_by_iso: dict, pkf_manifest: dict,
                    openbible_by_iso: dict, openbible_abbr: dict, canon: str) -> dict:
    """iso -> (dbt_ids, hao_ids, pkf_files, ob_ids), restricted to isos with
    >=1 total candidate id for this canon. The threshold is deliberately
    >=1, not >=2: even a single known id (e.g. niy:ot, which has only a PKF
    collection and no DBT/helloAO OT content) still gets a placeholder row
    in the published output — matching the original generate_catalog_overlap.py's
    behavior (it built its node set from catalog/manifest presence directly,
    independent of whether anything existed to compare against). Losing
    that placeholder would be a real, silent regression for any client
    checking "does this id exist at all" via catalog-overlap.json."""
    isos = {row[0] for row in catalog["versions"] if row[2].rstrip("p") == canon}
    isos |= set(helloao_by_iso.keys())
    isos |= set(pkf_manifest.keys())
    isos |= set(openbible_by_iso.keys())

    out = {}
    for iso in sorted(isos):
        dbt_ids = dbt_candidates(catalog, iso, canon)
        hao_ids = helloao_by_iso.get(iso, [])
        pkf_files = pkf_candidates(pkf_manifest, iso, canon)
        ob_ids = openbible_candidates(openbible_by_iso, openbible_abbr, iso)
        n = len(dbt_ids) + len(hao_ids) + (1 if pkf_files else 0) + len(ob_ids)
        if n >= 1:
            out[iso] = (dbt_ids, hao_ids, pkf_files, ob_ids)
    return out


def sole_candidate_id(iso: str, dbt_ids: dict, hao_ids: list, pkf_files: list, ob_ids: list) -> str:
    """The single source-prefixed id for an (iso,canon) with exactly one
    total candidate — nothing to compare against, so no fetch is needed at
    all; the published row is the same bare placeholder regardless of
    whether the id would have fetched successfully. Whichever of the four
    is non-empty is, by construction (all_candidates() only calls this when
    the total count is exactly 1), the sole candidate."""
    if dbt_ids:
        return f"dbt:{next(iter(dbt_ids))}"
    if hao_ids:
        return f"helloao:{hao_ids[0]}"
    if pkf_files:
        return f"pkf:{iso.upper()}PKF"
    return f"openbible:{ob_ids[0][1]}"


def process_language(iso: str, canon: str, dbt_ids: dict, hao_ids: list, pkf_files: list, ob_ids: list,
                      book: str, chapter: int, env: dict, bucket: str, tmpdir: Path) -> dict:
    texts = {}
    failed = []

    for distinct_id, fileset_id in dbt_ids.items():
        t = dbt_text(iso, canon, distinct_id, fileset_id, book, chapter)
        (texts.__setitem__(f"dbt:{distinct_id}", t) if t else failed.append(f"dbt:{distinct_id}"))

    for hid in hao_ids:
        t = helloao_text(hid, book, chapter)
        (texts.__setitem__(f"helloao:{hid}", t) if t else failed.append(f"helloao:{hid}"))

    for project_id, abbr in ob_ids:
        t = openbible_text(iso, project_id, book, chapter, tmpdir)
        (texts.__setitem__(f"openbible:{abbr}", t) if t else failed.append(f"openbible:{abbr}"))

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
    openbible_projects = json.loads(OPENBIBLE_PROJECTS_FILE.read_text()) if OPENBIBLE_PROJECTS_FILE.exists() else []
    openbible_by_iso = defaultdict(list)
    for p in openbible_projects:
        if p.get("type") == "text" and not p.get("disabled"):
            openbible_by_iso[p["languageCode"]].append(p["id"])
    openbible_abbr = (
        json.loads(OPENBIBLE_EDITIONS_FILE.read_text())["entries"]
        if OPENBIBLE_EDITIONS_FILE.exists() else {}
    )

    candidates = all_candidates(catalog, helloao_by_iso, pkf_manifest, openbible_by_iso, openbible_abbr, canon)
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
    # New source added after this iso was already fully compared (found
    # 2026-09-15 adding openbible: a "compared" entry with zero ids_failed
    # otherwise looks permanently done, and never gets a candidate-count
    # recheck — so a language that succeeded on 2 sources yesterday would
    # silently never pick up a 3rd source added today). Recompare whenever
    # today's real candidate count exceeds what was actually attempted
    # (fetched + failed) last time.
    def total_candidate_count(iso):
        dbt_ids, hao_ids, pkf_files, ob_ids = candidates[iso]
        return len(dbt_ids) + len(hao_ids) + (1 if pkf_files else 0) + len(ob_ids)

    growing_candidates = [
        iso for iso in candidates
        if key(iso) in results and not results[key(iso)].get("ids_failed")
        and iso not in retry_candidates
        and total_candidate_count(iso)
            > len(results[key(iso)].get("ids_fetched", [])) + len(results[key(iso)].get("ids_failed", []))
    ]
    todo = never_attempted + retry_candidates + growing_candidates
    if limit:
        todo = todo[:limit]

    print(f"[compare-all] {len(candidates)} candidate languages ({canon}), {len(results)} already done, "
          f"{len(never_attempted)} unattempted, {len(retry_candidates)} retrying failed ids, "
          f"{len(todo)} to process this run ({book} {chapter})")

    env, bucket = rclone_env()
    tmpdir = Path(tempfile.mkdtemp(prefix="compare_all_"))
    try:
        for i, iso in enumerate(todo, 1):
            dbt_ids, hao_ids, pkf_files, ob_ids = candidates[iso]
            n = len(dbt_ids) + len(hao_ids) + (1 if pkf_files else 0) + len(ob_ids)
            if n < 2:
                # Nothing to compare against — skip the fetch entirely
                # (the published row is the same bare placeholder either
                # way). This is the majority case (roughly half the full
                # population): most languages have exactly one DBT version
                # and no PKF/helloAO/openbible coverage at all.
                entry = {"status": "single_source", "ids_fetched": [sole_candidate_id(iso, dbt_ids, hao_ids, pkf_files, ob_ids)],
                         "ids_failed": [], "scores": {}}
                results[key(iso)] = {**entry, "iso": iso, "canon": canon}
                print(f"  [{i}/{len(todo)}] {key(iso)}: single_source (no fetch needed)")
                continue
            try:
                entry = process_language(iso, canon, dbt_ids, hao_ids, pkf_files, ob_ids, book, chapter, env, bucket, tmpdir)
                if entry.get("ids_failed"):
                    for fb_book, fb_chapter in FALLBACK_PROBES.get(canon, []):
                        if (fb_book, fb_chapter) == (book, chapter):
                            continue
                        fb_entry = process_language(iso, canon, dbt_ids, hao_ids, pkf_files, ob_ids, fb_book, fb_chapter, env, bucket, tmpdir)
                        if len(fb_entry.get("ids_fetched", [])) > len(entry.get("ids_fetched", [])):
                            fb_entry["probe"] = f"{fb_book}{fb_chapter}"
                            entry = fb_entry
                        if not entry.get("ids_failed"):
                            break
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
