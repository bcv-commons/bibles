#!/usr/bin/env python3
"""Fetch real per-book coverage for every Biblica (Open Bible) TEXT
project's current version — needed for catalog-index.json's NT/OT/Portions
classification, the same signal DBT/helloAO already have and PKF only
approximates.

Unlike audio (whose zips are per-book, so fetch_openbible_cache.py's phase
2 already gets real book coverage for free), text zips are whole-edition —
the only way to know which books a text project actually covers is to
fetch the zip and list its filenames. Reads through the persistent zip
cache (openbible_zip_cache.py, added 2026-09-16) — the zip is fetched (and
kept) once, reused by both this script and the comparison pipeline
(fetch_sources.py's openbible_text()), instead of each re-fetching the
same content separately.

Output: internal-data/api-cache/openbible/text-book-coverage.json
    {project_id: [book_code, ...]}  -- current version's real book list

Usage:
    python3 pipeline/core/fetch_openbible_book_coverage.py [--force]
"""
import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from openbible_zip_cache import get_zip_bytes  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE  # noqa: E402

TEXT_CACHE = API_CACHE / "openbible" / "text"
OUTPUT = API_CACHE / "openbible" / "text-book-coverage.json"


def fetch_zip_book_list(project_id: str, artifact_id: str) -> list | None:
    data = get_zip_bytes(project_id, artifact_id)
    if data is None:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return sorted({n.split("/")[-1].replace(".usfm", "") for n in z.namelist() if n.endswith(".usfm")})
    except zipfile.BadZipFile:
        return None


def current_usfm_artifact(detail: dict) -> str | None:
    for v in detail.get("versions", []):
        if not v.get("current"):
            continue
        for a in v.get("artifacts", []):
            if a.get("format") == "USFM":
                return a.get("id")
    return None


def main():
    force = "--force" in sys.argv
    coverage = json.loads(OUTPUT.read_text()) if OUTPUT.exists() and not force else {}

    files = sorted(TEXT_CACHE.glob("*.json"))
    todo = [f for f in files if f.stem not in coverage]
    print(f"[fetch-openbible-book-coverage] {len(files)} text projects, {len(coverage)} cached, {len(todo)} to fetch")

    done, failed = 0, 0
    for i, f in enumerate(todo):
        project_id = f.stem
        detail = json.loads(f.read_text())
        artifact_id = current_usfm_artifact(detail)
        if not artifact_id:
            coverage[project_id] = []
            done += 1
            continue
        books = fetch_zip_book_list(project_id, artifact_id)
        if books is None:
            failed += 1
            continue
        coverage[project_id] = books
        done += 1
        if (i + 1) % 25 == 0:
            print(f"  ...{i + 1}/{len(todo)} processed")
            OUTPUT.write_text(json.dumps(coverage, separators=(",", ":")), encoding="utf-8")

    OUTPUT.write_text(json.dumps(coverage, separators=(",", ":")), encoding="utf-8")
    print(f"[fetch-openbible-book-coverage] {done} cached, {failed} failed -> {OUTPUT}")


if __name__ == "__main__":
    main()
