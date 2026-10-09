#!/usr/bin/env python3
"""How each edition presents psalm titles (superscriptions), for lexeme-aligner.

  numbered  - the title is counted as a verse (Psalm 3 has 9 verses, Psalm 51 has 21;
              English numbering has 8 and 19)
  heading   - a title marker before verse 1, not counted as a verse (USFM \\d,
              helloAO's `hebrew_subtitle` block)
  mixed     - numbered in one probe psalm and not in the other (e.g. isl: Psalm 51's
              title is a verse, Psalm 3's is not), so titles must be checked per psalm
  note      - the title is given only as a footnote before verse 1 (e.g. GNT-style
              "HEBREW TITLE: ..." notes)
  unmarked  - no title marker and not numbered: the title is inline in verse 1, or
              the edition leaves it out. Structure can't tell these apart.

Probes Psalms 3 and 51 only. `basis` says what the value rests on: `markup` (the
source carries heading markup) or `verse-count` (DBT's plain-text API carries no
heading markup, so only `numbered` vs `unmarked` can be told there).

No PKF text is kept: each collection is decoded in a temporary folder and only the
two chapters' verse counts and title markers are read.

Usage:
    python3 pipeline/comparison/psalm_titles.py --iso eng,rus
    python3 pipeline/comparison/psalm_titles.py --scan [--workers 8]
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_all import all_candidates, dbt_candidates, openbible_candidates  # noqa: E402
from fetch_sources import HELLOAO_API, rclone_env, openbible_current_usfm_artifact  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
from openbible_zip_cache import get_zip_bytes  # noqa: E402
import download_language_content as dl  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, COMPARISON_RESULTS_DIR  # noqa: E402

OUT_PATH = COMPARISON_RESULTS_DIR / "psalm-titles.json"
# chapter -> {verse count: title counted as a verse?}. Psalm 51 in LXX/Vulgate numbering
# is English Psalm 52 (9 verses, 11 with its two-verse title). Any other count says
# nothing about the title (a versification difference), so that chapter is not used.
PROBES = {3: {8: False, 9: True}, 51: {19: False, 21: True, 9: False, 11: True}}
_VERSE = re.compile(r"\\v\s+(\d+)")


def classify(counts: dict, marked: dict) -> str | None:
    """counts: chapter -> number of verses; marked: chapter -> "heading", "note" or None
    (no marker, or the source can't say)."""
    usable = [c for c in PROBES if counts.get(c) in PROBES[c]]
    if not usable:
        return None
    numbered = {PROBES[c][counts[c]] for c in usable}
    if numbered == {True, False}:
        return "mixed"
    if True in numbered:
        return "numbered"
    for kind in ("heading", "note"):
        if any(marked.get(c) == kind for c in usable):
            return kind
    return "unmarked"


def usfm_probe(usfm: str, chapter: int) -> tuple:
    """(verse count, title marker before verse 1: "heading" for \\d, "note" for a
    footnote, None) for one chapter of a book's USFM."""
    m = re.search(rf"\\c\s+{chapter}\b(.*?)(?=\\c\s+\d+\b|\Z)", usfm, re.S)
    if not m:
        return None, None
    body = m.group(1)
    nums = [int(n) for n in _VERSE.findall(body)]
    count = max(nums) if nums else None
    v1 = re.search(r"\\v\s+1\b", body)
    before = body[: v1.start()] if v1 else body
    # \d before verse 1 is a heading; "\d \v 1 ..." (verse 1 inside \d) is a numbered title
    if re.search(r"\\d\b", before) and not re.search(r"\\d\s*$", before):
        return count, "heading"
    if re.search(r"\\f\s", before):
        return count, "note"
    return count, None


def pkf_probe(iso: str, pkf_file: str, env: dict, bucket: str, tmpdir: Path) -> tuple[dict, dict] | None:
    safe = pkf_file.replace("/", "_")
    p = tmpdir / f"{iso}_{safe}.pkf"
    try:
        r = subprocess.run(["rclone", "copyto", f"R2:{bucket}/pkf/{iso}/{pkf_file}", str(p)], capture_output=True, text=True, env=env)
        if r.returncode != 0 or not p.exists():
            return None
        out = tmpdir / f"{iso}_{safe}_out"
        subprocess.run(["node", "tools/pkf-decode/decode.mjs", str(p), "--out", str(out), "--book", "PSA"], capture_output=True, text=True)
        files = list(out.glob("*-PSA.usfm")) if out.is_dir() else []
        if not files:
            return None
        usfm = files[0].read_text(encoding="utf-8")
        counts, marked = {}, {}
        for c in PROBES:
            counts[c], marked[c] = usfm_probe(usfm, c)
        return counts, marked
    finally:
        for x in tmpdir.iterdir():
            if x.name.startswith(f"{iso}_"):
                shutil.rmtree(x) if x.is_dir() else x.unlink()


def openbible_probe(project_id: str) -> tuple[dict, dict] | None:
    import io
    import zipfile
    artifact = openbible_current_usfm_artifact(project_id)
    data = get_zip_bytes(project_id, artifact) if artifact else None
    if not data:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = [n for n in z.namelist() if n.endswith("PSA.usfm")]
            if not names:
                return None
            usfm = z.read(names[0]).decode("utf-8", errors="replace")
    except zipfile.BadZipFile:
        return None
    counts, marked = {}, {}
    for c in PROBES:
        counts[c], marked[c] = usfm_probe(usfm, c)
    return counts, marked


def helloao_probe(tid: str) -> tuple[dict, dict] | None:
    counts, marked = {}, {}
    for c in PROBES:
        try:
            r = requests.get(f"{HELLOAO_API}/{tid}/PSA/{c}.json", timeout=15)
            time.sleep(0.1)
        except requests.RequestException:
            r = None
        if r is None or r.status_code != 200:
            counts[c], marked[c] = None, None
            continue
        blocks = r.json().get("chapter", {}).get("content", [])
        nums = [b["number"] for b in blocks if b.get("type") == "verse" and "number" in b]
        counts[c] = max(nums) if nums else None
        first = next((i for i, b in enumerate(blocks) if b.get("type") == "verse"), len(blocks))
        marked[c] = "heading" if any(b.get("type") == "hebrew_subtitle" for b in blocks[:first]) else None
    return counts, marked


def dbt_probe(fileset_id: str) -> tuple[dict, dict] | None:
    counts, marked = {}, {}
    for c in PROBES:
        res = dl.get_text_content(fileset_id, "PSA", c)
        time.sleep(0.1)
        if res and res.get("type") == "verses":
            ends = [int(v.get("verse_end") or v.get("verse_start") or 0) for v in res["data"]]
            counts[c] = max(ends) if ends else None
        else:
            counts[c] = None
        marked[c] = None  # the plain-text API has no heading markup
    return counts, marked


def pkf_psalm_collections(pkf_manifest: dict, iso: str) -> list:
    """The language's PKF collections whose manifest coverage includes Psalms."""
    out = []
    for c in (pkf_manifest.get(iso) or {}).get("collections", []):
        ot = (c.get("coverage") or {}).get("o")
        if ot == "full" or (isinstance(ot, dict) and "PSA" in ot):
            out.append(c["pkf"])
    return out


def classify_language(iso, catalog, helloao_by_iso, pkf_manifest, openbible_by_iso, openbible_abbr, env, bucket, tmpdir, have):
    out = {}

    def record(tag, probe, basis):
        if tag in have or probe is None:
            return
        counts, marked = probe
        value = classify(counts, marked)
        if value:
            out[tag] = {"psalm_titles": value, "basis": basis,
                        "verses": {str(c): counts.get(c) for c in PROBES}}

    for did, fs in dbt_candidates(catalog, iso, "ot").items():
        if f"dbt:{did}" not in have:
            record(f"dbt:{did}", dbt_probe(fs), "verse-count")
    for hid in helloao_by_iso.get(iso, []):
        if f"helloao:{hid}" not in have:
            record(f"helloao:{hid}", helloao_probe(hid), "markup")
    tag = f"pkf:{iso.upper()}PKF"
    for pkf_file in pkf_psalm_collections(pkf_manifest, iso):
        if tag not in have and tag not in out:
            record(tag, pkf_probe(iso, pkf_file, env, bucket, tmpdir), "markup")
    for pid, abbr in openbible_candidates(openbible_by_iso, openbible_abbr, iso):
        if f"openbible:{abbr}" not in have:
            record(f"openbible:{abbr}", openbible_probe(pid), "markup")
    return out


def main() -> None:
    args = sys.argv[1:]
    iso_filter = set(args[args.index("--iso") + 1].split(",")) if "--iso" in args else None
    catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())
    hao = json.loads((API_CACHE / "helloao" / "available_translations.json").read_text())["translations"]
    helloao_by_iso = defaultdict(list)
    for e in hao:
        helloao_by_iso[e["language"]].append(e["id"])
    pkf_manifest = json.loads((API_CACHE / "pkf-manifest.json").read_text())["languages"]
    from compare_all import OPENBIBLE_PROJECTS_FILE, OPENBIBLE_EDITIONS_FILE
    projects = json.loads(OPENBIBLE_PROJECTS_FILE.read_text()) if OPENBIBLE_PROJECTS_FILE.exists() else []
    openbible_by_iso = defaultdict(list)
    for p in projects:
        if p.get("type") == "text" and not p.get("disabled"):
            openbible_by_iso[p["languageCode"]].append(p["id"])
    openbible_abbr = json.loads(OPENBIBLE_EDITIONS_FILE.read_text())["entries"] if OPENBIBLE_EDITIONS_FILE.exists() else {}

    candidates = all_candidates(catalog, helloao_by_iso, pkf_manifest, openbible_by_iso, openbible_abbr, "ot")
    isos = sorted(iso_filter) if iso_filter else sorted(candidates) if "--scan" in args else []
    if not isos:
        print("[psalm-titles] pass --iso ISO[,ISO...] or --scan")
        return

    doc = json.loads(OUT_PATH.read_text()) if OUT_PATH.is_file() else {}
    done_isos = set(doc.get("done_isos", []))
    editions = doc.get("editions", {})

    def save():
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps({
            "probes": ["PSA 3", "PSA 51"],
            "values": ["numbered", "mixed", "heading", "note", "unmarked"],
            "done_isos": sorted(done_isos),
            "editions": dict(sorted(editions.items())),
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    todo = [i for i in isos if i in candidates and i not in done_isos]
    print(f"[psalm-titles] {len(isos)} requested, {len(isos) - len(todo)} already done, {len(todo)} to process", flush=True)
    env, bucket = rclone_env()
    tmpdir = Path(tempfile.mkdtemp(prefix="psalm_titles_"))
    workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 8
    lock = threading.Lock()
    finished = 0

    def one(iso):
        nonlocal finished
        have = {k[len(iso) + 1:] for k in editions if k.startswith(f"{iso}:")}
        res = classify_language(iso, catalog, helloao_by_iso, pkf_manifest, openbible_by_iso, openbible_abbr, env, bucket, tmpdir, have)
        with lock:
            finished += 1
            for tag, r in res.items():
                editions[f"{iso}:{tag}"] = r
                print(f"  [{finished}/{len(todo)}] {iso}:{tag}: {r['psalm_titles']} ({r['basis']}, PSA3={r['verses']['3']} PSA51={r['verses']['51']})", flush=True)
            done_isos.add(iso)
            if finished % 20 == 0:
                save()

    # languages are independent and the time goes into waiting on the network
    try:
        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(one, todo))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        with lock:
            save()
    print(f"[psalm-titles] {len(editions)} editions -> {OUT_PATH}")


if __name__ == "__main__":
    main()
