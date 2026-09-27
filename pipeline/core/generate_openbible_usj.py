#!/usr/bin/env python3
"""Generate export/openbible-usj/<iso>/<edition>/<book>.json — real
book-level USJ (Unified Scripture JSON), extracted via the same `usfmtc`
parse already used by generate_openbible_chapters.py (usfm_to_verses.py's
`extract_verses_from_file` discards the USJ tree after walking it for
verse text — this script keeps it instead).

This is the openbible side of the reduced publish scheme (USJ at book
level, Sofria at chapter level, see internal design discussion 2026-09-19):
book-level USJ published here directly; chapter-level Sofria is a
separate downstream step (tools/usj-to-sofria/convert_batch.mjs) run over
this script's output.

Same edition scope/gating as generate_openbible_chapters.py (resolved
yaapi.bible abbreviation + at least one non-ND license) — kept identical
on purpose so the two artifact trees (verse-json and USJ) always cover
the same edition set.

Output:
    export/openbible-usj/<iso>/<edition>/<book>.json  — one USJ 3.0 doc/book
"""
import json
import sys
from pathlib import Path

import usfmtc  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, EXPORT, CATALOG_DIR  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_openbible_chapters import has_non_nd_license  # noqa: E402

TEXT_CACHE = API_CACHE / "openbible" / "text"
ZIP_CACHE = API_CACHE / "openbible" / "text-zips"
EDITIONS_FILE = CATALOG_DIR / "openbible-editions.json"
OUT_DIR = EXPORT / "openbible-usj"


def main():
    force = "--force" in sys.argv
    editions = json.loads(EDITIONS_FILE.read_text())["entries"]

    written, skipped_nd, skipped_no_zip, failed_books = 0, 0, 0, 0
    total_books = 0

    for project_id, edition in sorted(editions.items()):
        abbr, iso = edition["abbr"], edition["iso"]
        detail_path = TEXT_CACHE / f"{project_id}.json"
        zip_path = ZIP_CACHE / f"{project_id}.zip"

        edition_dir = OUT_DIR / iso / abbr
        if edition_dir.exists() and not force:
            continue

        if not zip_path.exists() or not detail_path.exists():
            skipped_no_zip += 1
            continue

        detail = json.loads(detail_path.read_text())
        current_version = next((v for v in detail.get("versions", []) if v.get("current")), None)
        licenses = current_version.get("licenses", []) if current_version else []
        if not has_non_nd_license(licenses):
            skipped_nd += 1
            continue

        import zipfile, tempfile
        try:
            z = zipfile.ZipFile(zip_path)
        except zipfile.BadZipFile:
            continue

        edition_dir.mkdir(parents=True, exist_ok=True)
        books_written = 0
        for name in z.namelist():
            if not name.endswith(".usfm"):
                continue
            book = name.split("/")[-1].replace(".usfm", "")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".usfm", delete=False, encoding="utf-8") as tf:
                tf.write(z.read(name).decode("utf-8"))
                tmp_path = tf.name
            try:
                doc = usfmtc.readFile(tmp_path)
                usj = doc.outUsj()
            except Exception as e:
                print(f"  WARNING: {abbr}/{book} USJ extraction failed: {e}")
                failed_books += 1
                continue
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            out_path = edition_dir / f"{book}.json"
            out_path.write_text(
                json.dumps(usj, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            books_written += 1
            total_books += 1

        if books_written:
            written += 1

    print(f"[generate-openbible-usj] {written} editions written, {total_books} book files, "
          f"{skipped_nd} skipped (ND-only), {skipped_no_zip} skipped (no cached zip/detail), "
          f"{failed_books} book extraction failures -> {OUT_DIR}")


if __name__ == "__main__":
    main()
