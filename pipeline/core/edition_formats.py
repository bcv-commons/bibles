"""Each self-published edition's `_meta.json` (openbible, audiobiblia), and the formats
it lists. Written into the edition's USJ folder (export/<source>-usj/<iso>/<edition>/)
by the USJ generators, and published next to the Sofria and USJ files.

`formats` paths are relative to the edition's folder on the CDN
(cdn.bibel.wiki/<source>/<iso>/<edition>/). The verse-json chapters
(<BOOK>/<chapter>.json) were removed from the CDN on 2026-10-09; Sofria replaces them.
"""
import json
from pathlib import Path

FORMATS = {
    "sofria": {"path": "<BOOK>/<chapter>.sofria.json", "granularity": "chapter"},
    "usj": {"path": "<BOOK>.usj.json", "granularity": "book"},
}

META_FILE = "_meta.json"


def usj_books(edition_dir: Path) -> list[str]:
    """Books in an edition's USJ folder that have at least one chapter (an empty book,
    such as BLL's Letter of Jeremiah, has no Sofria chapters and is not listed)."""
    books = []
    for f in sorted(edition_dir.glob("*.json")):
        if f.name == META_FILE:
            continue
        content = json.loads(f.read_text(encoding="utf-8")).get("content", [])
        if any(isinstance(n, dict) and n.get("type") == "chapter" for n in content):
            books.append(f.stem)
    return books


def write_meta(edition_dir: Path, meta: dict) -> None:
    """Write _meta.json: the edition's own fields, then `books` and `formats`."""
    out = {**meta, "books": usj_books(edition_dir), "formats": FORMATS}
    (edition_dir / META_FILE).write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
