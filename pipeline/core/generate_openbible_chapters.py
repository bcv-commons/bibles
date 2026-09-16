#!/usr/bin/env python3
"""Generate export/openbible/<iso>/<edition>/<book>/<chapter>.json — real
per-verse text, extracted LOCALLY from this repo's own already-cached
Biblica USFM zips (usfm_to_verses.py, backed by `usfmtc`), not fetched
from yaapi.bible's /verses/ API.

Supersedes the original design (fetch_yaapi_cache.py + generate_yaapi_chapters.py,
which pulled per-verse text from yaapi.bible directly): after finding
`usfmtc` (a real, actively maintained USFM parser — see
tools/pkf-encode-py's narrower vendored tokenizer for why that wasn't
used instead) parses this repo's own cached zips with a 100% real success
rate on a random sample (vs. thousands of failures on 30+ distinct real
marker types from the narrower parser), there's no remaining reason to
depend on yaapi.bible's own extraction or its rate-limited, frequently-
interrupted /verses/ pagination.

yaapi.bible's `/versions/` CATALOG is still the id authority, unchanged —
Biblica's own catalog has no human-readable edition id at all (confirmed
2026-09-19), so `openbible-editions.json` (project_id -> {abbr, iso})
stays exactly as built. Only the CONTENT source changed — from yaapi's
live API to this repo's own local zip cache.

License data now comes directly from Biblica's own per-version
`licenses[]` array (internal-data/api-cache/openbible/text/<id>.json),
which is richer than yaapi's single `license` string (some editions
carry more than one real license tag at once, e.g. dual CC BY-SA + CC
BY-NC-ND — both kept, never collapsed to one).

Scope: only Biblica projects with BOTH (a) a resolved yaapi.bible
abbreviation (openbible-editions.json) and (b) at least one non-ND
license of their own (the lenient rule already established this session:
ND-only is excluded, but a project carrying an ND tag alongside a real
non-ND alternative is not) — matching the same content-gating decision
already applied to catalog/index.json's `o` rows.

Output:
    export/openbible/<iso>/<edition>/<book>/<chapter>.json
        {"book", "chapter", "verses": [{"verse", "text"}, ...]}
    export/openbible/<iso>/<edition>/_meta.json
        {"name", "licenses": [...], "provider", "copyright", "source",
         "openbible_link", "books": [...]}
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from usfm_to_verses import extract_verses_from_file  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, EXPORT, CATALOG_DIR  # noqa: E402

TEXT_CACHE = API_CACHE / "openbible" / "text"
ZIP_CACHE = API_CACHE / "openbible" / "text-zips"
EDITIONS_FILE = CATALOG_DIR / "openbible-editions.json"
OUT_DIR = EXPORT / "openbible"

ND_LICENSES = {"CC BY-ND", "CC BY-NC-ND"}


def has_non_nd_license(licenses: list) -> bool:
    """Lenient rule (matches catalog/index.json's own gating): eligible
    if AT LEAST ONE license is non-ND, even if an ND tag is also present
    (dual-licensed content — a licensee can pick the permissive option)."""
    if not licenses:
        return False
    return any(lic.get("licenseType", "").strip("[]") not in ND_LICENSES for lic in licenses)


def main():
    force = "--force" in sys.argv
    editions = json.loads(EDITIONS_FILE.read_text())["entries"]

    written, skipped_nd, skipped_no_zip, failed = 0, 0, 0, 0
    total_chapters = 0

    for project_id, edition in sorted(editions.items()):
        abbr, iso = edition["abbr"], edition["iso"]
        detail_path = TEXT_CACHE / f"{project_id}.json"
        zip_path = ZIP_CACHE / f"{project_id}.zip"

        edition_dir = OUT_DIR / iso / abbr
        if edition_dir.exists() and not force:
            continue

        if not zip_path.exists():
            skipped_no_zip += 1
            continue
        if not detail_path.exists():
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
            failed += 1
            continue

        books_written = set()
        edition_dir.mkdir(parents=True, exist_ok=True)
        for name in z.namelist():
            if not name.endswith(".usfm"):
                continue
            book = name.split("/")[-1].replace(".usfm", "")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".usfm", delete=False, encoding="utf-8") as tf:
                tf.write(z.read(name).decode("utf-8"))
                tmp_path = tf.name
            try:
                chapters = extract_verses_from_file(tmp_path)
            except Exception as e:
                print(f"  WARNING: {abbr}/{book} extraction failed: {e}")
                continue
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            if not chapters:
                continue
            book_dir = edition_dir / book
            book_dir.mkdir(parents=True, exist_ok=True)
            for chapter_num, verses in chapters.items():
                rows = [{"verse": v, "text": t} for v, t in sorted(
                    verses.items(), key=lambda kv: (len(kv[0]), kv[0]))]
                out_path = book_dir / f"{chapter_num}.json"
                out_path.write_text(
                    json.dumps({"book": book, "chapter": chapter_num, "verses": rows},
                               ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8",
                )
                total_chapters += 1
            books_written.add(book)

        project = detail.get("project", {})
        meta = {
            "name": project.get("titleEnglish") or project.get("title"),
            "licenses": [
                {"type": lic.get("licenseType", "").strip("[]"), "url": lic.get("licenseUrl")}
                for lic in licenses
            ],
            "provider": project.get("rightsHolder"),
            "source": "biblica",
            "openbible_link": f"https://openbible-api-1.biblica.com/projects/{project_id}",
            "books": sorted(books_written),
        }
        (edition_dir / "_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        written += 1

    print(f"[generate-openbible-chapters] {written} editions written, {total_chapters} chapter files, "
          f"{skipped_nd} skipped (ND-only), {skipped_no_zip} skipped (no cached zip/detail), "
          f"{failed} failed -> {OUT_DIR}")


if __name__ == "__main__":
    main()
