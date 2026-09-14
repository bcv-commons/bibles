#!/usr/bin/env python3
"""Generate /dbt/<iso>/coverage.json — real per-fileset book/chapter coverage.

Companion file to media.json, per explicit client request: a partial DBT
edition's real book set (e.g. PORALM: 11 books) can't be assumed from an
"NT"/"OT" canon label alone, and the client's own direct-polling workaround
for this had no refresh mechanism and had gone stale.

Source: DBT's own /bibles/{abbr} response (bible-level — checked live
against DBT's API: passing an audio/text-fileset-suffix id like ENGBERN1DA
as distinct_id 404s, only the bible abbr works), already cached and
kept fresh by fetch_api_cache.py, and propagated per-fileset (testament-
filtered for NT/OT-only filesets, so an NT-only audio fileset doesn't
inherit OT books from its bible's aggregate response) by sort_cache_data.py
into internal-data/sorted/BB/<iso>/<fileset>/metadata.json's "books" field.

Deliberately independent of export/ALL-langs (unlike
generate_audio_metadata.py's fileset discovery) — this reads sorted/BB
directly, so it stays live regardless of that separate, known-stale
dependency.

Output: export/dbt/<iso>/coverage.json, shape:
    {"<fileset_id>": {"<book_id>": [<chapters>], ...}, ...}

Usage:
    python3 pipeline/core/generate_dbt_coverage.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import EXPORT, SORTED_DIR  # noqa: E402

OUTPUT_DIR = EXPORT / "dbt"


def main():
    if not SORTED_DIR.is_dir():
        print(f"[generate-dbt-coverage] {SORTED_DIR} not found. Run: make sort-dbt-catalog")
        return

    files_written = 0
    for iso_dir in sorted(p for p in SORTED_DIR.iterdir() if p.is_dir()):
        iso = iso_dir.name
        coverage: dict[str, dict[str, list]] = {}

        for fileset_dir in sorted(p for p in iso_dir.iterdir() if p.is_dir()):
            meta_path = fileset_dir / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text())
            except Exception:
                continue

            books = meta.get("books")
            if not books:
                continue

            fileset_id = meta.get("fileset", {}).get("id", "")
            if not fileset_id:
                continue

            # A FULL-canon fileset that got expanded into separate NT/OT
            # sorted/BB directories (see sort_cache_data.py's save_metadata)
            # shares one real fileset_id across both directories — merge,
            # don't overwrite, so both halves survive.
            entry = coverage.setdefault(fileset_id, {})
            entry.update({b["book_id"]: b["chapters"] for b in books if b.get("book_id")})

        if not coverage:
            continue

        iso_out = OUTPUT_DIR / iso
        iso_out.mkdir(parents=True, exist_ok=True)
        (iso_out / "coverage.json").write_text(
            json.dumps(coverage, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
        files_written += 1

    print(f"[generate-dbt-coverage] {files_written} language(s) -> {OUTPUT_DIR}/<iso>/coverage.json")


if __name__ == "__main__":
    main()
