#!/usr/bin/env python3
"""Full-population run of the PKF/DBT version-comparison pilot
(scripts/compare_pkf_dbt.py) — see CLAUDE.local.md for the pilot history
(48 -> 96 languages, 4 bugs found and fixed) this scales up.

For every DBT/PKF overlap language with a local DBT REV15 sample: fetch its
PKF collection via rclone, decode via tools/pkf-decode/, compare against
every locally-sampled DBT version, record a verdict. No PKF text is
retained anywhere — the .pkf and decoded .usfm are deleted immediately
after each language is scored.

Verdict tiers (automatic, score-based — see module docstring in
compare_pkf_dbt.py for the char-level/homoglyph/heading-stripped algorithm
these scores come from):
  identical       score == 1.0
  near_identical  0.98 <= score < 1.0
  uncertain       0.5 <= score < 0.98 (dialect/orthography-variant/distinct
                  all live here — genuinely ambiguous at scale without
                  manual diff reading, same as the pilot's "middle" cases)
  distinct        score < 0.5
  no_pkf_text     PKF collection claims NT coverage but has 0 REV chapters
  no_dbt_sample   no local DBT REV15 sample to compare against at all

Bug-detection heuristic (replaces manually reading every diff): for any
non-1.0 score, if a single (pkf_fragment, dbt_fragment) substitution pair
accounts for >=80% of all diff hunks, flag possible_encoding_issue=true —
this is the exact signature that caught 3 of the pilot's 4 bugs.

Resumable: writes incrementally, skips isos already recorded in the output
file on rerun.

Defaults to the NT probe (REV 15). For an OT probe, pass --book/--chapter
matching the catalog's OT reference book (PSA 117) and --canon-dir ot so
local DBT samples/output land in the right places:
    python3 scripts/batch_compare_pkf_dbt.py --book PSA --chapter 117 \\
        --canon-dir ot --out data/pkf-dbt-comparison-ot.json

Usage:
    python3 scripts/batch_compare_pkf_dbt.py [--limit N] [--book B] [--chapter N]
                                              [--canon-dir nt|ot] [--out PATH]
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_pkf_dbt import extract_pkf_chapter, dbt_samples, compare  # noqa: E402
from confirm_text_availability import fetch_catalog  # noqa: E402
from fill_dbt_text_samples import fetch_pkf_manifest  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import PKF_DBT_COMPARISON_FILE, TEXT_DIR  # noqa: E402

OUT_PATH = PKF_DBT_COMPARISON_FILE
BOOK, CHAPTER = "REV", 15
CANON_DIR = TEXT_DIR / "BB" / "nt"


def rclone_env():
    load_dotenv()
    access = os.getenv("R2_ACCESS_KEY_ID") or os.getenv("CLOUDFLARE_ACCESS_KEY_ID", "")
    secret = os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("CLOUDFLARE_SECRET_ACCESS_KEY", "")
    account = os.getenv("R2_ACCOUNT_ID") or os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    bucket = os.getenv("R2_BUCKET") or os.getenv("CLOUDFLARE_BUCKET", "")
    env = os.environ.copy()
    env.update({
        "RCLONE_CONFIG_R2_TYPE": "s3",
        "RCLONE_CONFIG_R2_PROVIDER": "Cloudflare",
        "RCLONE_CONFIG_R2_ACCESS_KEY_ID": access,
        "RCLONE_CONFIG_R2_SECRET_ACCESS_KEY": secret,
        "RCLONE_CONFIG_R2_ENDPOINT": f"https://{account}.r2.cloudflarestorage.com",
        "RCLONE_CONFIG_R2_ACL": "private",
        "RCLONE_CONFIG_R2_NO_CHECK_BUCKET": "true",
    })
    return env, bucket


def candidate_isos() -> dict:
    """iso -> {pkf_files: [...], has_dbt_sample}, for every overlap language.

    The manifest's "pkf" filename is an opaque internal build label (per
    se-regional-pwa's own confirmation, after we flagged aom/uth as a
    possible mismatch and they investigated in depth: e.g. aom ships as
    "lwm_C01...", uth as "dud_C01..." — both verified correct content,
    "not a bug", the iso KEY in the manifest is the sole trusted
    identifier). So: NEVER infer or validate anything from the filename
    prefix — just read whatever collections the manifest lists for this
    iso, verbatim, as documented.

    The one real remaining question the filename can't answer is niy's
    case: its manifest entry lists TWO collections for one iso. Since
    filenames carry no reliable signal (confirmed above), disambiguation
    there is done empirically in process_one() — fetch+compare ALL listed
    collections against DBT and keep whichever actually scores as a real
    match, rather than guessing from metadata."""
    catalog = fetch_catalog()
    pkf = fetch_pkf_manifest()["languages"]
    dbt_isos = {row[0] for row in catalog["versions"]}
    overlap = dbt_isos & set(pkf.keys())

    local_isos = set()
    for f in CANON_DIR.rglob(f"{BOOK}_{CHAPTER:03d}_*.txt"):
        local_isos.add(f.relative_to(CANON_DIR).parts[0])

    out = {}
    for iso in sorted(overlap):
        collections = pkf[iso].get("collections") or []
        if not collections:
            continue  # PKF manifest lists the language but has no actual collection
        out[iso] = {"pkf_files": [c["pkf"] for c in collections],
                     "has_dbt_sample": iso in local_isos}
    return out


def classify(score: float) -> str:
    if score == 1.0:
        return "identical"
    if score >= 0.98:
        return "near_identical"
    if score >= 0.5:
        return "uncertain"
    return "distinct"


def dominant_pair_fraction(pkf_chars: str, dbt_chars: str) -> tuple[float, int]:
    import difflib
    sm = difflib.SequenceMatcher(a=pkf_chars, b=dbt_chars, autojunk=False)
    diffs = [op for op in sm.get_opcodes() if op[0] != "equal"]
    if not diffs:
        return 0.0, 0
    pairs = Counter((pkf_chars[i1:i2], dbt_chars[j1:j2]) for _, i1, i2, j1, j2 in diffs)
    top = pairs.most_common(1)[0][1]
    return top / len(diffs), len(diffs)


def fetch_and_extract(iso: str, pkf_file: str, env: dict, bucket: str, tmpdir: Path):
    """Fetch + decode one collection, return (pkf_chars, status_if_failed).
    status_if_failed is None on success."""
    safe_tag = pkf_file.replace("/", "_")
    pkf_path = tmpdir / f"{iso}_{safe_tag}.pkf"
    result = subprocess.run(
        ["rclone", "copyto", f"R2:{bucket}/pkf/{iso}/{pkf_file}", str(pkf_path)],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0 or not pkf_path.exists():
        return None, {"status": "fetch_failed", "error": result.stderr.strip()[:200]}

    out_dir = tmpdir / f"{iso}_{safe_tag}_out"
    result = subprocess.run(
        ["node", "tools/pkf-decode/decode.mjs", str(pkf_path), "--out", str(out_dir), "--book", BOOK],
        capture_output=True, text=True,
    )
    # decode.mjs numbers output files by USFM book order (e.g. 67-REV.usfm,
    # 19-PSA.usfm) — glob rather than hardcode the number, since it differs
    # per book (needed once OT books like PSA entered the picture).
    matches = list(out_dir.glob(f"*-{BOOK}.usfm")) if out_dir.is_dir() else []
    if not matches:
        # decode.mjs exits 0 with "0 book(s)" when the collection genuinely
        # doesn't include this book (confirmed via puu/qvo: their own PKF
        # manifest `coverage` fields list only other books) — that's
        # equivalent to no_pkf_text, not a real decode failure.
        status = "decode_failed" if result.returncode != 0 else "no_pkf_text"
        return None, {"status": status, "error": result.stderr.strip()[:200]}
    usfm_path = matches[0]

    pkf_chars = extract_pkf_chapter(usfm_path, CHAPTER)
    if not pkf_chars:
        return None, {"status": "no_pkf_text"}
    return pkf_chars, None


def process_one(iso: str, pkf_files: list, env: dict, bucket: str, tmpdir: Path) -> dict:
    dbt = dbt_samples(iso, BOOK, CHAPTER, sample_dir=CANON_DIR)
    if not dbt:
        return {"status": "no_dbt_sample"}

    # Single collection (the overwhelming majority): fetch once, no
    # disambiguation needed — the manifest's iso key is trusted as-is per
    # se-regional-pwa's confirmation (aom/uth filenames don't reflect iso,
    # and that's expected, not a mismatch to second-guess).
    #
    # Multiple collections under one iso (currently only niy): filenames
    # carry no reliable signal either way, so disambiguate empirically —
    # fetch + compare EVERY listed collection against DBT and keep
    # whichever actually scores as a real match. Confirmed via niy itself:
    # its two collections scored 0.102 vs 0.999 against the same DBT
    # text — an unambiguous empirical answer, not a guess.
    best_overall = None
    tried = []
    for pkf_file in pkf_files:
        pkf_chars, failure = fetch_and_extract(iso, pkf_file, env, bucket, tmpdir)
        if failure is not None:
            tried.append({"pkf_file": pkf_file, **failure})
            continue

        best_id, best_score = None, -1.0
        scores = {}
        for distinct_id, dbt_chars in dbt.items():
            s = compare(pkf_chars, dbt_chars)
            scores[distinct_id] = round(s, 4)
            if s > best_score:
                best_id, best_score = distinct_id, s

        candidate = {
            "pkf_file": pkf_file, "pkf_chars": pkf_chars,
            "best_match": best_id, "best_score": best_score, "all_scores": scores,
        }
        tried.append({k: v for k, v in candidate.items() if k != "pkf_chars"})
        if best_overall is None or best_score > best_overall["best_score"]:
            best_overall = candidate

    if best_overall is None:
        # every collection failed to fetch/decode
        return {"status": tried[0]["status"] if tried else "fetch_failed", "attempts": tried}

    entry = {
        "status": "compared",
        "verdict": classify(best_overall["best_score"]),
        "pkf_file": best_overall["pkf_file"],
        "best_match": best_overall["best_match"],
        "best_score": round(best_overall["best_score"], 4),
        "dbt_versions_compared": len(dbt),
        "all_scores": best_overall["all_scores"],
    }
    if len(pkf_files) > 1:
        entry["collections_tried"] = len(pkf_files)
        entry["collection_disambiguated"] = True
    if best_overall["best_score"] < 1.0:
        frac, n_hunks = dominant_pair_fraction(best_overall["pkf_chars"], dbt[best_overall["best_match"]])
        entry["diff_hunks"] = n_hunks
        entry["dominant_pair_fraction"] = round(frac, 3)
        if frac >= 0.8 and n_hunks >= 3:
            entry["possible_encoding_issue"] = True
    return entry


def main():
    global BOOK, CHAPTER, CANON_DIR, OUT_PATH
    args = sys.argv[1:]
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    if "--book" in args:
        BOOK = args[args.index("--book") + 1]
    if "--chapter" in args:
        CHAPTER = int(args[args.index("--chapter") + 1])
    if "--canon-dir" in args:
        CANON_DIR = TEXT_DIR / "BB" / args[args.index("--canon-dir") + 1]
    if "--out" in args:
        OUT_PATH = Path(args[args.index("--out") + 1])

    env, bucket = rclone_env()
    candidates = candidate_isos()

    results = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}

    todo = [iso for iso, info in candidates.items()
            if info["has_dbt_sample"] and iso not in results]
    no_sample = [iso for iso, info in candidates.items() if not info["has_dbt_sample"]]
    for iso in no_sample:
        results.setdefault(iso, {"status": "no_dbt_sample"})

    if limit:
        todo = todo[:limit]

    print(f"[batch] {len(candidates)} total candidates, {len(no_sample)} no_dbt_sample, "
          f"{len(results) - len(no_sample)} already done, {len(todo)} to process this run")

    tmpdir = Path(tempfile.mkdtemp(prefix="pkf_batch_"))
    try:
        for i, iso in enumerate(todo, 1):
            entry = process_one(iso, candidates[iso]["pkf_files"], env, bucket, tmpdir)
            results[iso] = entry
            tag = entry.get("verdict", entry["status"])
            flag = " [POSSIBLE ENCODING ISSUE]" if entry.get("possible_encoding_issue") else ""
            print(f"  [{i}/{len(todo)}] {iso}: {tag} "
                  f"(score={entry.get('best_score', '-')}){flag}")
            # Cleanup this language's fetched/decoded files immediately —
            # verdict-only, never retain PKF text.
            for p in tmpdir.iterdir():
                if p.name.startswith(iso):
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
            if i % 10 == 0:
                OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        OUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    tally = Counter(r.get("verdict", r["status"]) for r in results.values())
    flagged = [iso for iso, r in results.items() if r.get("possible_encoding_issue")]
    print(f"\n[batch] done. {len(results)} total languages recorded.")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")
    if flagged:
        print(f"  possible_encoding_issue flagged: {flagged}")


if __name__ == "__main__":
    main()
