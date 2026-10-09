#!/usr/bin/env python3
"""Generate export/openbible-usj/<iso>/<edition>/<book>.json — real
book-level USJ (Unified Scripture JSON), parsed from Biblica's own USFM zips
with `usfmtc` — plus each edition's _meta.json (name, licenses, provider,
openbible link, books, formats; see edition_formats.py).

This is the openbible side of the reduced publish scheme (USJ at book
level, Sofria at chapter level, see internal design discussion 2026-09-19):
book-level USJ published here directly; chapter-level Sofria is a
separate downstream step (tools/usj-to-sofria/convert_batch.mjs) run over
this script's output.

Editions: a resolved yaapi.bible abbreviation and at least one non-ND license.
(This replaced generate_openbible_chapters.py, which wrote per-chapter verse-json
from the same zips; verse-json was retired 2026-10-09 in favour of Sofria.)

An edition that already has USJ is skipped (--force redoes it), but its _meta.json
is still written if missing, so metadata can be refreshed without re-parsing.

Output:
    export/openbible-usj/<iso>/<edition>/<book>.json  — one USJ 3.0 doc/book
    export/openbible-usj/<iso>/<edition>/_meta.json
"""
import json
import sys
from pathlib import Path

import usfmtc  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, EXPORT, CATALOG_DIR  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from usfm_to_verses import fix_adjacent_w_spacing  # noqa: E402
from edition_formats import META_FILE, write_meta  # noqa: E402

TEXT_CACHE = API_CACHE / "openbible" / "text"
ZIP_CACHE = API_CACHE / "openbible" / "text-zips"
EDITIONS_FILE = CATALOG_DIR / "openbible-editions.json"
OUT_DIR = EXPORT / "openbible-usj"

ND_LICENSES = {"CC BY-ND", "CC BY-NC-ND"}


def has_non_nd_license(licenses: list) -> bool:
    """Lenient rule (matches catalog/index.json's own gating): eligible
    if AT LEAST ONE license is non-ND, even if an ND tag is also present
    (dual-licensed content — a licensee can pick the permissive option)."""
    if not licenses:
        return False
    return any(lic.get("licenseType", "").strip("[]") not in ND_LICENSES for lic in licenses)


def edition_meta(project_id: str, detail: dict, licenses: list) -> dict:
    project = detail.get("project", {})
    return {
        "name": project.get("titleEnglish") or project.get("title"),
        "licenses": [
            {"type": lic.get("licenseType", "").strip("[]"), "url": lic.get("licenseUrl")}
            for lic in licenses
        ],
        "provider": project.get("rightsHolder"),
        "source": "biblica",
        "openbible_link": f"https://openbible-api-1.biblica.com/projects/{project_id}",
    }


def current_licenses(detail: dict) -> list:
    current_version = next((v for v in detail.get("versions", []) if v.get("current")), None)
    return current_version.get("licenses", []) if current_version else []


def main():
    force = "--force" in sys.argv
    editions = json.loads(EDITIONS_FILE.read_text())["entries"]

    written, skipped_nd, skipped_no_zip, failed_books = 0, 0, 0, 0
    total_books = metas = 0

    for project_id, edition in sorted(editions.items()):
        abbr, iso = edition["abbr"], edition["iso"]
        detail_path = TEXT_CACHE / f"{project_id}.json"
        zip_path = ZIP_CACHE / f"{project_id}.zip"

        edition_dir = OUT_DIR / iso / abbr
        if edition_dir.exists() and not force:
            if not (edition_dir / META_FILE).exists() and detail_path.exists():
                detail = json.loads(detail_path.read_text())
                write_meta(edition_dir, edition_meta(project_id, detail, current_licenses(detail)))
                metas += 1
            continue

        if not zip_path.exists() or not detail_path.exists():
            skipped_no_zip += 1
            continue

        detail = json.loads(detail_path.read_text())
        licenses = current_licenses(detail)
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
                fix_adjacent_w_spacing(usj)
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
            write_meta(edition_dir, edition_meta(project_id, detail, licenses))
            metas += 1
            written += 1

    print(f"[generate-openbible-usj] {written} editions written, {total_books} book files, "
          f"{skipped_nd} skipped (ND-only), {skipped_no_zip} skipped (no cached zip/detail), "
          f"{failed_books} book extraction failures, {metas} _meta.json written -> {OUT_DIR}")


if __name__ == "__main__":
    main()
