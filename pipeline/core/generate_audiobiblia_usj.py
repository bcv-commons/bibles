#!/usr/bin/env python3
"""Generate export/audiobiblia-usj/<iso>/<edition>/<book>.json (real book-level
USJ) and the edition's _meta.json for the audiobiblia.org Spanish editions that
carry a genuinely republishable license, confirmed live 2026-09-30.
(Formerly generate_audiobiblia_chapters.py, which also wrote per-chapter
verse-json; verse-json was retired 2026-10-09 in favour of Sofria.)

  BLL — Biblia Libre Latinoamericana (Public Domain). Sourced NOT from
    audiobiblia.org's own site (which only offers per-chapter HTML pages,
    no bulk download) but from eBible.org directly — a joint
    AudioBiblia.org/eBible.org project, confirmed via
    https://eBible.org/Scriptures/spabll_usfm.zip, real structured USFM
    (83 books: full 39-book protestant OT + deuterocanon + 27-book NT).
    eBible's own copr.htm flags this as "Este es un borrador de
    traducción. Está siendo revisado y editado." (a draft translation,
    still being reviewed/edited) — real content, not a placeholder, but
    worth carrying that caveat through to clients rather than presenting
    it as a finished edition. Public Domain, no attribution requirement.

  BES — La Biblia en Español Sencillo (CC BY 4.0, © 2018-2019
    AudioBiblia.org/Irma Flores). audiobiblia.org's own "NT.zip"/"AT.zip"
    links are audio bundles, NOT text (confirmed: contains files like
    "39_BES_MAL_01.mp3") — real text comes the same way as BLL, via
    eBible.org: https://eBible.org/Scriptures/spabes_usfm.zip (66 books,
    clean protestant canon). Real attribution requirement carried through
    in this script's _meta.json output.

Audio itself is NOT handled here — per the original request, audio-sync
fetches/aligns audio directly from audiobiblia.org; this script only
republishes the matching TEXT, which audio-sync specifically asked for to
avoid having to scrape audiobiblia.org's HTML pages or an unreliable PDF
extraction themselves.

Both real USFM zips verified to parse cleanly via `usfmtc` before this
script was written (real Matthew, 28 chapters, both editions).

Output, the same layout as openbible:
    export/audiobiblia-usj/<iso>/<edition>/<book>.json — one USJ 3.0 doc per book
    export/audiobiblia-usj/<iso>/<edition>/_meta.json
        {"name", "licenses": [...], "provider", "copyright"?, "source",
         "draft_notice"?, "books": [...], "formats": {...}}
"""
import json
import sys
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from usfm_to_verses import fix_adjacent_w_spacing  # noqa: E402
from edition_formats import META_FILE, write_meta  # noqa: E402
import usfmtc  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import DOWNLOADS, EXPORT  # noqa: E402

ZIP_CACHE = DOWNLOADS / "audiobiblia"
USJ_OUT_DIR = EXPORT / "audiobiblia-usj"

EDITIONS = {
    "BLL": {
        "iso": "spa",
        "zip_url": "https://eBible.org/Scriptures/spabll_usfm.zip",
        "name": "Biblia Libre Latinoamericana",
        "licenses": [{"type": "Public Domain", "url": "https://ebible.org/find/show.php?id=spabll"}],
        "provider": "AudioBiblia.org / eBible.org",
        "copyright": None,
        "source": "https://audiobiblia.org/spabll_ab/spabll.htm",
        "draft_notice": "eBible.org's own copr.htm flags this as a draft "
                        "translation still being reviewed/edited (confirmed "
                        "2026-09-30), not a finished edition.",
    },
    # BES (spa) and BBE (eng) were investigated and built (2026-10-02) but
    # deliberately EXCLUDED here, not just left unpublished: real content
    # verification (each edition's own provenance field, not just a name
    # match) found helloAO already serves byte-identical content sourced
    # from the exact same eBible.org id — helloAO's `spa_bes`/`eng_bbe`
    # `website`/`licenseUrl` both point directly at
    # `ebible.org/Scriptures/details.php?id=spabes`/`id=engBBE`. Decided:
    # for sources we don't control (DBT/PKF/helloAO) we report whatever
    # they have regardless of overlap elsewhere, but for our OWN
    # self-republishing (`"o"`) we choose not to duplicate content a
    # client can already get from another source — BLL stays because it
    # has no helloAO (or DBT) match at all, genuinely unique.
}


def edition_meta(meta: dict) -> dict:
    out = {"name": meta["name"], "licenses": meta["licenses"],
           "provider": meta["provider"], "source": meta["source"]}
    if meta["copyright"]:
        out["copyright"] = meta["copyright"]
    if meta["draft_notice"]:
        out["draft_notice"] = meta["draft_notice"]
    return out


def fetch_zip(edition: str, url: str) -> Path:
    ZIP_CACHE.mkdir(parents=True, exist_ok=True)
    dest = ZIP_CACHE / f"{edition}.zip"
    if dest.exists():
        return dest
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def main():
    force = "--force" in sys.argv
    written_editions, total_usj_books = 0, 0

    for edition, meta in EDITIONS.items():
        iso = meta["iso"]
        usj_edition_dir = USJ_OUT_DIR / iso / edition
        if usj_edition_dir.exists() and not force:
            if not (usj_edition_dir / META_FILE).exists():
                write_meta(usj_edition_dir, edition_meta(meta))
                print(f"[audiobiblia] {edition} already present: _meta.json written (--force to redo the USJ)")
            else:
                print(f"[audiobiblia] {edition} already present, skipping (--force to redo)")
            continue

        zip_path = fetch_zip(edition, meta["zip_url"])
        z = zipfile.ZipFile(zip_path)

        usj_edition_dir.mkdir(parents=True, exist_ok=True)

        for name in z.namelist():
            if not name.endswith(".usfm"):
                continue
            suffix = f"{iso}{edition.lower()}.usfm"  # e.g. "spabll.usfm"
            stem = name.split("-", 1)[1] if "-" in name else name
            book = stem[:-len(suffix)] if stem.endswith(suffix) else stem.replace(".usfm", "")
            book = book.upper()
            if book == "FRT":
                continue  # front matter, not a real book

            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".usfm", delete=False, encoding="utf-8") as tf:
                tf.write(z.read(name).decode("utf-8"))
                tmp_path = tf.name
            try:
                doc = usfmtc.readFile(tmp_path)
                usj = doc.outUsj()
                fix_adjacent_w_spacing(usj)
            except Exception as e:
                print(f"  WARNING: {edition}/{book} extraction failed: {e}")
                continue
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            usj_path = usj_edition_dir / f"{book}.json"
            usj_path.write_text(
                json.dumps(usj, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            total_usj_books += 1

        write_meta(usj_edition_dir, edition_meta(meta))
        written_editions += 1
        print(f"[audiobiblia] {edition}: USJ and _meta.json written")

    print(f"[audiobiblia] {written_editions} editions, {total_usj_books} USJ book files -> {USJ_OUT_DIR}")


if __name__ == "__main__":
    main()
