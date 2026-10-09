#!/usr/bin/env python3
"""Write the original USFM of every openbible book whose USJ has a table.

proskomma-core can't import USJ tables, but it can import USFM ones, so
tools/usj-to-sofria/convert_batch.mjs converts these books from USFM
(`--usfm-dir`). Output mirrors the USJ tree: <out>/<iso>/<abbr>/<BOOK>.usfm.
Source: the cached openbible text zips (openbible_zip_cache.py).

Usage:
    python3 pipeline/core/extract_openbible_table_usfm.py [<usj-dir>] [<out-dir>]
"""
import io
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from openbible_zip_cache import ZIP_CACHE_DIR  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import CATALOG_DIR, EXPORT  # noqa: E402

TABLE = re.compile(r'"type"\s*:\s*"table"')


def main() -> None:
    usj_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else EXPORT / "openbible-usj"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else EXPORT / "openbible-usfm-tables"
    editions = json.loads((CATALOG_DIR / "openbible-editions.json").read_text())["entries"]
    project_for = {(v["iso"], v["abbr"]): pid for pid, v in editions.items()}

    written, missing = 0, []
    for usj in sorted(usj_dir.rglob("*.json")):
        if not TABLE.search(usj.read_text(encoding="utf-8")):
            continue
        rel = usj.relative_to(usj_dir)
        iso, abbr, book = rel.parts[0], rel.parts[1], rel.stem
        zip_path = ZIP_CACHE_DIR / f"{project_for.get((iso, abbr), '')}.zip"
        usfm = None
        if zip_path.is_file():
            with zipfile.ZipFile(io.BytesIO(zip_path.read_bytes())) as z:
                name = next((n for n in z.namelist() if n.endswith(f"{book}.usfm")), None)
                if name:
                    usfm = z.read(name)
        if usfm is None:
            missing.append(str(rel))
            continue
        target = out_dir / rel.with_suffix(".usfm")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(usfm)
        written += 1
    print(f"[table-usfm] {written} books written to {out_dir}; no USFM source for {len(missing)}: {missing}")


if __name__ == "__main__":
    main()
