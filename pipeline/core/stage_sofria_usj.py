#!/usr/bin/env python3
"""Stage Sofria (per chapter) and USJ (per book) for the CDN, under the same tree as
the verse-json chapters:

    <prefix>/<iso>/<abbr>/<BOOK>.usj.json
    <prefix>/<iso>/<abbr>/<BOOK>/<ch>.sofria.json

The staging tree is hard links to the build outputs, so it takes no extra disk space.
Publish it with publish-openbible.sh / publish-audiobiblia.sh (SOURCE_DIR=<stage>).

convert_batch.mjs writes a book's chapters only once the whole book has converted, so
a book is staged whole or not at all; its USJ is staged only alongside its Sofria.

Usage:
    python3 pipeline/core/stage_sofria_usj.py <usj-dir> <sofria-dir> <stage-dir>
"""
import os
import shutil
import sys
from pathlib import Path


def main() -> None:
    usj_dir, sofria_dir, stage = (Path(a) for a in sys.argv[1:4])
    if stage.exists():
        shutil.rmtree(stage)
    books = chapters = 0
    skipped = []
    for usj in sorted(usj_dir.rglob("*.json")):
        rel = usj.relative_to(usj_dir).with_suffix("")  # <iso>/<abbr>/<BOOK>
        src = sofria_dir / rel
        if not src.is_dir() or not any(src.glob("*.json")):
            skipped.append(str(rel))
            continue
        out = stage / rel
        out.mkdir(parents=True, exist_ok=True)
        os.link(usj, out.parent / f"{rel.name}.usj.json")
        for ch in src.glob("*.json"):
            os.link(ch, out / f"{ch.stem}.sofria.json")
            chapters += 1
        books += 1
    print(f"[stage] {books} books, {chapters} chapters -> {stage}; no Sofria for {len(skipped)}: {skipped[:20]}")


if __name__ == "__main__":
    main()
