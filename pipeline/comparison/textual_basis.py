#!/usr/bin/env python3
"""Textual-basis classification (tr / byzantine / critical / mixed / indeterminate),
simplified from lexeme-aligner's eval/textual_basis.py to fit this repo's own catalog
data instead of their ingested-USJ pipeline.

Method and the 15 diagnostic verses are lexeme-aligner's own (handed over 2026-10-07,
internal-docs/edition-side-methods-for-bibles.md) — classify() below is unchanged from
theirs. Only the INPUT layer differs: rather than reading an ingested USJ file by book
number (their _BOOK_FILE_NUM/usj_source.read_verses, which we don't have or need), this
fetches per-verse text straight from the same DBT/helloAO/PKF/openbible sources
compare_all.py already talks to, reusing its candidate-gathering. No spine selection
here — that only matters for lexeme-aligner's own alignment runs, not for us.

No PKF text is retained, same verdict-only discipline the rest of this pipeline uses.

Usage:
    python3 pipeline/comparison/textual_basis.py --iso ind,eng
    python3 pipeline/comparison/textual_basis.py --scan           # every NT candidate
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_all import all_candidates, dbt_candidates, pkf_candidates, openbible_candidates  # noqa: E402
from fetch_sources import HELLOAO_API, rclone_env, openbible_current_usfm_artifact  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
from openbible_zip_cache import get_zip_bytes  # noqa: E402
import download_language_content as dl  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, COMPARISON_RESULTS_DIR  # noqa: E402

# Internal build artifact only — NOT under export/catalog/, so it never gets
# swept into publish-catalog.sh's whole-directory CDN sync. edition_struct.py
# reads this and folds textual_basis in as a per-edition field in the one
# file we do publish (export/catalog/edition-struct.json); nothing external
# needs this file standalone. Same reasoning lexeme-aligner's own split uses:
# this is the slow, rarely-recomputed base; edition_struct.py's merge is the
# cheap, frequently-recomputed one built on top of it.
OUT_PATH = COMPARISON_RESULTS_DIR / "textual-basis.json"

# (book, chapter, verse, tr_only) — tr_only marks the four that separate TR from
# Byzantine. Verbatim from lexeme-aligner's textual_basis.py.
DIAGNOSTIC_VERSES = [
    ("MAT", 17, 21, False), ("MAT", 18, 11, False), ("MAT", 23, 14, False),
    ("MRK", 7, 16, False), ("MRK", 9, 44, False), ("MRK", 9, 46, False),
    ("MRK", 11, 26, False), ("MRK", 15, 28, False),
    ("LUK", 17, 36, True), ("LUK", 23, 17, False),
    ("ACT", 8, 37, True), ("ACT", 15, 34, True), ("ACT", 24, 7, True),
    ("ACT", 28, 29, False), ("ROM", 16, 24, False),
]
_BRACKETED = re.compile(r"^\s*[\[\(【]")
_VERSE_RE = re.compile(r"\\v\s+(\d+)(?:-(\d+))?\s*")


def dbt_verse(fileset_id: str, book: str, chapter: int, verse: int, cache: dict) -> str | None:
    key = ("dbt", fileset_id, book, chapter)
    if key not in cache:
        result = dl.get_text_content(fileset_id, book, chapter)
        time.sleep(0.1)
        by_verse = {}
        if result and result.get("type") == "verses":
            for item in result["data"]:
                vs = item.get("verse_start")
                if vs is not None:
                    by_verse[int(vs)] = item.get("verse_text", "")
        cache[key] = by_verse
    return cache[key].get(verse)


def helloao_verse(translation_id: str, book: str, chapter: int, verse: int, cache: dict) -> str | None:
    key = ("helloao", translation_id, book, chapter)
    if key not in cache:
        by_verse = {}
        try:
            r = requests.get(f"{HELLOAO_API}/{translation_id}/{book}/{chapter}.json", timeout=15)
            time.sleep(0.1)
            if r.status_code == 200:
                for block in r.json().get("chapter", {}).get("content", []):
                    if block.get("type") != "verse" or "number" not in block:
                        continue
                    parts = [i if isinstance(i, str) else i.get("text", "")
                             for i in block.get("content", [])]
                    by_verse[int(block["number"])] = " ".join(parts)
        except (requests.RequestException, ValueError):
            pass
        cache[key] = by_verse
    return cache[key].get(verse)


def _usfm_chapter_verses(text: str, chapter: int) -> dict[int, str]:
    """Verse number -> text, for one \\c block of raw USFM. A merged range
    (`\\v 12-13`) is recorded under both numbers with the same text, matching
    how the original textual_basis.py's single-verse lookup would see either
    half as present."""
    lines, in_chapter, buf = text.splitlines(), False, []
    for line in lines:
        if line.startswith("\\c "):
            in_chapter = line.strip() == f"\\c {chapter}"
            continue
        if in_chapter:
            buf.append(line)
    chapter_text = "\n".join(buf)
    parts = _VERSE_RE.split(chapter_text)
    out: dict[int, str] = {}
    i = 1
    while i + 2 < len(parts) + 1 and i < len(parts):
        vnum, vend, vtext = parts[i], parts[i + 1] if i + 1 < len(parts) else None, parts[i + 2] if i + 2 < len(parts) else ""
        out[int(vnum)] = vtext.strip()
        if vend:
            out[int(vend)] = vtext.strip()
        i += 3
    return out


def _chapter_from(entry: dict, chapter: int) -> dict[int, str]:
    """Verses of one chapter from a cached book, parsed on first use. (Fixed
    2026-10-08: the cache used to hold only the first chapter asked for, so every
    later chapter of the same book came back empty: PKF and openbible editions
    were checked on 5 of the 15 diagnostic verses at most.)"""
    if chapter not in entry["chapters"]:
        entry["chapters"][chapter] = _usfm_chapter_verses(entry["text"], chapter) if entry["text"] else {}
    return entry["chapters"][chapter]


def pkf_verse(iso: str, pkf_file: str, book: str, chapter: int, verse: int,
              env: dict, bucket: str, tmpdir: Path, cache: dict) -> str | None:
    # One download and one decode per collection, all books at once (decoding per
    # book loaded the whole PKF again for each of the 5 test books). The decoded
    # text stays in memory for this language's run only and is never written out.
    coll_key = ("pkf-collection", iso, pkf_file)
    if coll_key not in cache:
        books: dict[str, str] = {}
        safe_tag = pkf_file.replace("/", "_")
        pkf_path = tmpdir / f"{iso}_{safe_tag}.pkf"
        result = subprocess.run(
            ["rclone", "copyto", f"R2:{bucket}/pkf/{iso}/{pkf_file}", str(pkf_path)],
            capture_output=True, text=True, env=env,
        )
        if result.returncode == 0 and pkf_path.exists():
            out_dir = tmpdir / f"{iso}_{safe_tag}_out"
            subprocess.run(
                ["node", "tools/pkf-decode/decode.mjs", str(pkf_path), "--out", str(out_dir)],
                capture_output=True, text=True,
            )
            for f in (out_dir.glob("*.usfm") if out_dir.is_dir() else []):
                code = f.stem.split("-")[-1]
                books[code] = f.read_text(encoding="utf-8")
        for p in tmpdir.iterdir():
            if p.name.startswith(f"{iso}_"):
                shutil.rmtree(p) if p.is_dir() else p.unlink()
        cache[coll_key] = books
    key = ("pkf", iso, pkf_file, book)
    if key not in cache:
        cache[key] = {"text": cache[coll_key].get(book), "chapters": {}}
    return _chapter_from(cache[key], chapter).get(verse)


def openbible_verse(project_id: str, book: str, chapter: int, verse: int, tmpdir: Path, cache: dict) -> str | None:
    key = ("openbible", project_id, book)
    if key not in cache:
        book_text = None
        artifact_id = openbible_current_usfm_artifact(project_id)
        if artifact_id:
            data = get_zip_bytes(project_id, artifact_id)
            if data:
                import io
                import zipfile
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        matches = [n for n in z.namelist() if n.endswith(f"/{book}.usfm") or n.endswith(f"{book}.usfm")]
                        if matches:
                            book_text = z.read(matches[0]).decode("utf-8", errors="replace")
                except zipfile.BadZipFile:
                    pass
        cache[key] = {"text": book_text, "chapters": {}}
    return _chapter_from(cache[key], chapter).get(verse)


def classify(get_verse) -> dict:
    """get_verse(book, chapter, verse) -> text|None. Unchanged from lexeme-aligner's
    own classify(), just parameterized over a verse-lookup callable instead of a
    USJ directory."""
    present = bracketed = checked = tr_present = tr_checked = 0
    hits: list[str] = []
    for book, ch, v, tr_only in DIAGNOSTIC_VERSES:
        text = get_verse(book, ch, v)
        if text is None:
            continue
        checked += 1
        if tr_only:
            tr_checked += 1
        if not text.strip():
            continue
        if _BRACKETED.match(text):
            bracketed += 1
            continue
        present += 1
        hits.append(f"{book} {ch}:{v}")
        if tr_only:
            tr_present += 1

    verdict = "indeterminate"
    if checked >= 8:
        rate = present / checked
        if bracketed >= 3 and rate < 0.5:
            verdict = "mixed"
        elif rate < 0.2:
            verdict = "critical"
        elif tr_checked and tr_present / tr_checked >= 0.5:
            verdict = "tr"
        elif rate >= 0.6:
            verdict = "byzantine"
        else:
            verdict = "mixed"
    return {"verdict": verdict, "present": present, "bracketed": bracketed, "checked": checked,
            "tr_only_present": tr_present, "tr_only_checked": tr_checked, "verses": hits}


def classify_language(iso: str, catalog: dict, helloao_by_iso: dict, pkf_manifest: dict,
                      openbible_by_iso: dict, openbible_abbr: dict,
                      env: dict, bucket: str, tmpdir: Path, have: set = frozenset()) -> dict:
    """Editions whose tag is in `have` already have a verdict and are skipped."""
    cache: dict = {}
    results: dict[str, dict] = {}

    for distinct_id, fileset_id in dbt_candidates(catalog, iso, "nt").items():
        if f"dbt:{distinct_id}" in have:
            continue
        results[f"dbt:{distinct_id}"] = classify(
            lambda b, c, v, fs=fileset_id: dbt_verse(fs, b, c, v, cache))

    for hid in helloao_by_iso.get(iso, []):
        if f"helloao:{hid}" in have:
            continue
        results[f"helloao:{hid}"] = classify(
            lambda b, c, v, h=hid: helloao_verse(h, b, c, v, cache))

    for pkf_file in pkf_candidates(pkf_manifest, iso, "nt"):
        if f"pkf:{iso.upper()}PKF" in have:
            continue
        results[f"pkf:{iso.upper()}PKF"] = classify(
            lambda b, c, v, pf=pkf_file: pkf_verse(iso, pf, b, c, v, env, bucket, tmpdir, cache))

    for project_id, abbr in openbible_candidates(openbible_by_iso, openbible_abbr, iso):
        if f"openbible:{abbr}" in have:
            continue
        results[f"openbible:{abbr}"] = classify(
            lambda b, c, v, p=project_id: openbible_verse(p, b, c, v, tmpdir, cache))

    return results


def main() -> None:
    args = sys.argv[1:]
    iso_filter = set(args[args.index("--iso") + 1].split(",")) if "--iso" in args else None
    scan = "--scan" in args

    catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())
    helloao_translations = json.loads((API_CACHE / "helloao" / "available_translations.json").read_text())["translations"]
    helloao_by_iso = defaultdict(list)
    for e in helloao_translations:
        helloao_by_iso[e["language"]].append(e["id"])
    pkf_manifest = json.loads((API_CACHE / "pkf-manifest.json").read_text())["languages"]
    from compare_all import OPENBIBLE_PROJECTS_FILE, OPENBIBLE_EDITIONS_FILE
    openbible_projects = json.loads(OPENBIBLE_PROJECTS_FILE.read_text()) if OPENBIBLE_PROJECTS_FILE.exists() else []
    openbible_by_iso = defaultdict(list)
    for p in openbible_projects:
        if p.get("type") == "text" and not p.get("disabled"):
            openbible_by_iso[p["languageCode"]].append(p["id"])
    openbible_abbr = (json.loads(OPENBIBLE_EDITIONS_FILE.read_text())["entries"]
                      if OPENBIBLE_EDITIONS_FILE.exists() else {})

    candidates = all_candidates(catalog, helloao_by_iso, pkf_manifest, openbible_by_iso, openbible_abbr, "nt")
    isos = sorted(iso_filter) if iso_filter else sorted(candidates) if scan else []
    if not isos:
        print("[textual-basis] pass --iso ISO[,ISO...] or --scan")
        return

    # Resumable: a full --scan is many hours (3,945 candidate editions, each
    # needing up to 14 chapter fetches — timed 2026-10-07 at ~15-30s/edition).
    # done_isos tracks which languages have ALL their current candidates
    # already recorded, so a rerun (after a crash, a kill, or just stopping
    # it) only (re)does what's missing, the same resumability compare_all.py
    # already has. Progress is also saved periodically, not only at the end,
    # so an interrupted run never loses everything done so far.
    doc = json.loads(OUT_PATH.read_text(encoding="utf-8")) if OUT_PATH.is_file() else {}
    editions: dict = doc.get("editions", {})

    def expected_tags(iso: str) -> set[str]:
        dbt_ids, hao_ids, pkf_files, ob_ids = candidates[iso]
        tags = {f"dbt:{d}" for d in dbt_ids} | {f"helloao:{h}" for h in hao_ids} | {f"openbible:{a}" for _, a in ob_ids}
        if pkf_files:
            tags.add(f"pkf:{iso.upper()}PKF")
        return tags

    def save() -> None:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps({
            "method": "lexeme-aligner's 15-diagnostic-verse textual-basis check, applied to our own catalog sources",
            "diagnostic_verses": [f"{b} {c}:{v}{'*' if tr else ''}" for b, c, v, tr in DIAGNOSTIC_VERSES],
            "editions": dict(sorted(editions.items())),
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    todo = [iso for iso in isos if iso in candidates
            and not expected_tags(iso) <= {k[len(iso) + 1:] for k in editions if k.startswith(f"{iso}:")}]
    print(f"[textual-basis] {len(isos)} requested, {len(isos) - len(todo)} already fully done, "
          f"{len(todo)} to process this run")

    env, bucket = rclone_env()
    tmpdir = Path(tempfile.mkdtemp(prefix="textual_basis_"))
    try:
        for i, iso in enumerate(todo, 1):
            have = {k[len(iso) + 1:] for k in editions if k.startswith(f"{iso}:")}
            per_edition = classify_language(iso, catalog, helloao_by_iso, pkf_manifest,
                                            openbible_by_iso, openbible_abbr, env, bucket, tmpdir, have)
            for tag, r in per_edition.items():
                editions[f"{iso}:{tag}"] = r
                print(f"  [{i}/{len(todo)}] {iso}:{tag}: {r['verdict']} "
                      f"(present={r['present']}/{r['checked']} tr_only={r['tr_only_present']}/{r['tr_only_checked']})")
            if i % 10 == 0:
                save()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        save()
    print(f"[textual-basis] {len(editions)} editions recorded -> {OUT_PATH}")


if __name__ == "__main__":
    main()
