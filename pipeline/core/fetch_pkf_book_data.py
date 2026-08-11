#!/usr/bin/env python3
"""Fetch the three PKF per-language files generate_catalog_books.py needs
(book names/chapters, license/year, font hints) into
internal-data/api-cache/pkf-books/<iso>/ — resumable, skips files already
cached. Live rclone fetch, same mechanism as
pipeline/comparison/fetch_sources.py's pkf_text(), reused directly.

Per language, per collection:
  <catalog>.json  — collections[].catalog from pkf-manifest.json;
                     documents[].{bookCode,h,toc,toc2,toc3,versesByChapters}
  app-config.json — collection.{copyright,textDirection}
  info.json       — assets[] with kind:"font" (real font files/URLs)
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from paths import API_CACHE, PKF_BOOKS_CACHE  # noqa: E402

sys.path.insert(0, str(ROOT / "pipeline" / "comparison"))
from fetch_sources import rclone_env  # noqa: E402

MANIFEST = API_CACHE / "pkf-manifest.json"


def fetch_one(env, bucket, iso, filename, dest):
    if dest.exists():
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["rclone", "copyto", f"R2:{bucket}/pkf/{iso}/{filename}", str(dest)],
        capture_output=True, text=True, env=env,
    )
    return result.returncode == 0 and dest.exists()


def main():
    manifest = json.loads(MANIFEST.read_text())["languages"]
    env, bucket = rclone_env()

    isos = sorted(manifest.keys())
    if "--limit" in sys.argv:
        n = int(sys.argv[sys.argv.index("--limit") + 1])
        isos = isos[:n]
    ok = fail = skipped = 0
    for i, iso in enumerate(isos, 1):
        entry = manifest[iso]
        lang_dir = PKF_BOOKS_CACHE / iso
        # app-config.json / info.json are per-language (not per-collection)
        app_config_dest = lang_dir / "app-config.json"
        info_dest = lang_dir / "info.json"
        already_had = app_config_dest.exists() and info_dest.exists()

        if fetch_one(env, bucket, iso, "app-config.json", app_config_dest):
            ok += 1
        else:
            fail += 1
        if fetch_one(env, bucket, iso, "info.json", info_dest):
            ok += 1
        else:
            fail += 1

        for collection in entry.get("collections", []):
            catalog_name = collection.get("catalog")
            if not catalog_name:
                continue
            catalog_dest = lang_dir / catalog_name
            if catalog_dest.exists():
                skipped += 1
                continue
            if fetch_one(env, bucket, iso, catalog_name, catalog_dest):
                ok += 1
            else:
                fail += 1

        if already_had:
            skipped += 1
        if i % 50 == 0 or i == len(isos):
            print(f"[fetch-pkf-books] [{i}/{len(isos)}] ok={ok} skipped={skipped} fail={fail}", flush=True)

    print(f"[fetch-pkf-books] done: {ok} fetched, {skipped} already cached, {fail} failed")


if __name__ == "__main__":
    main()
