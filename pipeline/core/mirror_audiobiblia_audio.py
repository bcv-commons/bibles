#!/usr/bin/env python3
"""Mirror audiobiblia.org's per-chapter BLL audio (.m4a) for republishing at
cdn.bibel.wiki/audiobiblia/spa/BLL/audio/<BOOK>_<chapter>.m4a, next to the BLL text.

audiobiblia.org: "El texto y los archivos de audio están en el dominio público sin
restricciones" (spabll.htm, checked 2026-10-27). Its files are fine to play from there, but
the site sends no CORS header, so a web client can't fetch() them (offline caching, Web
Audio), and a client would have to know its naming and which chapters exist. Hence the copy.

Source naming: https://audiobiblia.org/spabll_ab/<BOOK><chapter>.m4a, chapter zero-padded to
2 digits (3 for PSA: PSA001). The site has the 66-book canon only; our BLL text also has the
deuterocanonical books (from eBible), which have no audio. Chapters are taken from our BLL
USJ (export/audiobiblia-usj/spa/BLL/), so every audio file lines up with a text chapter; a
chapter whose audio is missing is reported, and one more chapter past the text's last is
probed so audio the text doesn't have is reported too.

Each file must come back as audio/mp4 with an MP4 `ftyp` box; anything else is an error, not
written. Files already downloaded are kept (the site sends them as immutable). A dropped
connection is retried with backoff: the site resets connections now and then (default 2 workers).

Writes:
  internal-data/downloads/audiobiblia-audio/spa/BLL/audio/<BOOK>_<chapter>.m4a
  internal-data/downloads/audiobiblia-audio/spa/BLL/audio-manifest.json
      {"source", "books": {BOOK: [chapter, ...]}, "missing": [...], "extra": [...]}
The manifest is read by generate_audiobiblia_usj.py for _meta.json's `formats.audio`; the
.m4a tree is published by `make publish-audiobiblia-audio` (not part of `make clean`'s export/).

Usage:
    python3 pipeline/core/mirror_audiobiblia_audio.py [--workers N]   # default 2
"""
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import DOWNLOADS, EXPORT  # noqa: E402

EDITIONS = {
    "BLL": {"iso": "spa", "base_url": "https://audiobiblia.org/spabll_ab/"},
}
AUDIO_DIR = DOWNLOADS / "audiobiblia-audio"
USJ_DIR = EXPORT / "audiobiblia-usj"
MANIFEST = "audio-manifest.json"
UA = {"User-Agent": "Mozilla/5.0"}
RETRIES = 6

CANON_66 = ["GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA", "1KI", "2KI",
            "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO", "ECC", "SNG", "ISA", "JER",
            "LAM", "EZK", "DAN", "HOS", "JOL", "AMO", "OBA", "JON", "MIC", "NAM", "HAB", "ZEP",
            "HAG", "ZEC", "MAL",
            "MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL",
            "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN",
            "3JN", "JUD", "REV"]


def text_chapters(usj_path: Path) -> list[int]:
    content = json.loads(usj_path.read_text(encoding="utf-8")).get("content", [])
    return [int(n["number"]) for n in content if isinstance(n, dict) and n.get("type") == "chapter"]


def source_url(base: str, book: str, chapter: int) -> str:
    return f"{base}{book}{chapter:0{3 if book == 'PSA' else 2}d}.m4a"


def fetch(url: str) -> bytes | None:
    """The file's bytes; None on 404; raises on anything that isn't MP4 audio."""
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as resp:
                ctype = resp.headers.get("Content-Type", "")
                data = resp.read()
                if len(data) != int(resp.headers.get("Content-Length", len(data))):
                    raise ConnectionError(f"short read: {len(data)} bytes")
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code < 500 or attempt == RETRIES - 1:
                raise
        except OSError:  # connection reset, timeout, short read
            if attempt == RETRIES - 1:
                raise
        time.sleep(2 ** attempt)
    if not ctype.startswith("audio/") or data[4:8] != b"ftyp":
        raise ValueError(f"{url}: not MP4 audio ({ctype}, {len(data)} bytes)")
    return data


def exists(url: str) -> bool:
    req = urllib.request.Request(url, headers=UA, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.headers.get("Content-Type", "").startswith("audio/")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def mirror_chapter(base: str, out_dir: Path, book: str, chapter: int) -> str:
    dest = out_dir / f"{book}_{chapter}.m4a"
    if dest.exists() and dest.stat().st_size > 0:
        return "kept"
    data = fetch(source_url(base, book, chapter))
    if data is None:
        return "missing"
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.rename(dest)
    return "downloaded"


def main():
    args = sys.argv[1:]
    workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 2

    for edition, cfg in EDITIONS.items():
        iso, base = cfg["iso"], cfg["base_url"]
        usj_dir = USJ_DIR / iso / edition
        if not usj_dir.exists():
            print(f"[audiobiblia-audio] {usj_dir} not found. Run: make audiobiblia (the USJ) first")
            continue
        edition_dir = AUDIO_DIR / iso / edition
        out_dir = edition_dir / "audio"
        out_dir.mkdir(parents=True, exist_ok=True)

        jobs = [(book, ch) for book in CANON_66 if (usj_dir / f"{book}.json").exists()
                for ch in text_chapters(usj_dir / f"{book}.json")]
        with ThreadPoolExecutor(workers) as pool:
            results = list(pool.map(lambda j: (j, mirror_chapter(base, out_dir, *j)), jobs))

        books: dict[str, list[int]] = {}
        missing = []
        for (book, ch), status in results:
            if status == "missing":
                missing.append(f"{book} {ch}")
            else:
                books.setdefault(book, []).append(ch)
        extra = [f"{book} {chs[-1] + 1}" for book, chs in books.items()
                 if exists(source_url(base, book, chs[-1] + 1))]

        manifest = {"source": base, "books": books, "missing": missing, "extra": extra}
        (edition_dir / MANIFEST).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        counts = {s: sum(1 for _, r in results if r == s) for s in ("downloaded", "kept", "missing")}
        print(f"[audiobiblia-audio] {edition}: {len(books)} books, {len(jobs)} chapters "
              f"({counts['downloaded']} downloaded, {counts['kept']} already here, {counts['missing']} missing)"
              f"{'; audio past the text: ' + ', '.join(extra) if extra else ''} -> {out_dir}")
        if missing:
            print(f"  missing: {', '.join(missing[:20])}{' ...' if len(missing) > 20 else ''}")


if __name__ == "__main__":
    main()
