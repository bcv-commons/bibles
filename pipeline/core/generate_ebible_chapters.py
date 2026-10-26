#!/usr/bin/env python3
"""Generate export/ebible-usj/<iso>/<translationId>/<book>.json — book-level USJ parsed from
eBible.org's USFM zips with `usfmtc` — plus each edition's _meta.json (name, licenses,
provider, source, books, formats; see edition_formats.py). Same conversion and layout as
generate_openbible_usj.py; chapter-level Sofria is the downstream step
(tools/usj-to-sofria/convert_batch.mjs).

Editions: eBible's catalog (`https://ebible.org/Scriptures/translations.csv`) marks them
`Redistributable` and `downloadable`, AND their copyright page
(`https://ebible.org/<translationId>/copyright.htm`) gives a licence we can republish
under: Public Domain or a Creative Commons licence without No Derivatives. The catalog
flag alone isn't enough: it is True for ND editions and for some "All rights reserved"
ones (bbr2013). A page whose licence link and text disagree (mri: a BY-NC link, "No
Derivatives" in the text) counts as ND. Pages are cached under internal-data/api-cache.

Downloads retry (3 attempts, backoff) with a (connect, read) timeout, are written to a
temporary file and checked as a zip before they are cached, so a stalled or cut-off
download is retried and never cached broken. The summary counts, separately: written,
skipped for licence (with the reason), download failed after retries, no USFM.

An edition helloAO already carries is skipped: helloAO's catalog links each of its eBible
sources as `details.php?id=<translationId>`, and SAME_AS_HELLOAO lists the ones whose link
points elsewhere (BSB -> berean.bible). Every other edition is compared by text before it is
written, never assumed distinct: its sample chapters (chapter 1 of its first Old Testament
and first New Testament book) against every edition in the same language that we can already
reach (helloAO translations, our openbible and audiobiblia USJ). A letters-only similarity of
DUPLICATE_SCORE or more on every shared sample is the same text: skipped, and recorded in
internal-data/api-cache/ebible/duplicates.json with the match and its scores.

An edition that already has USJ is skipped (--force redoes it); its _meta.json is still
written if missing.

Output:
    export/ebible-usj/<iso>/<translationId>/<book>.json  — one USJ 3.0 doc per book
    export/ebible-usj/<iso>/<translationId>/_meta.json

(Verse-json, export/ebible/<iso>/<id>/<book>/<chapter>.json, is no longer written: it
was retired 2026-10-09 in favour of Sofria.)

Usage:
    python3 generate_ebible_chapters.py [--force] [--limit N] [--translation-id ID]
"""
import collections
import csv
import difflib
import html
import io
import json
import re
import sys
import tempfile
import time
import unicodedata
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from usfm_to_verses import drop_strongs, fix_adjacent_w_spacing  # noqa: E402
from usfm_pipes import protect, restore  # noqa: E402
from edition_formats import FORMATS, META_FILE, write_meta  # noqa: E402
import usfmtc  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "verse-text" / "python"))
from helloao_to_usj import chapter_to_usj  # noqa: E402  (the client converter, tools/verse-text)
from verse_text import extract_usj  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, DOWNLOADS, EXPORT  # noqa: E402

CSV_URL = "https://ebible.org/Scriptures/translations.csv"
CSV_CACHE = DOWNLOADS / "ebible" / "translations.csv"
ZIP_CACHE = DOWNLOADS / "ebible" / "zips"
COPYRIGHT_CACHE = API_CACHE / "ebible" / "copyright"
USJ_OUT_DIR = EXPORT / "ebible-usj"
SKIP_BOOKS = {"FRT", "BAK", "INT", "GLO", "CNC", "NDX", "OTH", "XXA", "XXB", "XXC", "XXD", "XXE", "XXF", "XXG"}

HELLOAO_API = "https://bible.helloao.org/api"
HELLOAO_TRANSLATIONS = API_CACHE / "helloao" / "available_translations.json"
HELLOAO_CHAPTERS = API_CACHE / "ebible" / "helloao-samples"
DUPLICATES_FILE = API_CACHE / "ebible" / "duplicates.json"
OWN_USJ = [EXPORT / "openbible-usj", EXPORT / "audiobiblia-usj"]
# helloAO translations taken from eBible whose catalog link isn't the eBible details page.
SAME_AS_HELLOAO = {"engbsb": "BSB"}
DUPLICATE_SCORE = 0.95
OT_FIRST = ["GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA", "1KI", "2KI", "1CH", "2CH",
            "EZR", "NEH", "EST", "JOB", "PSA", "PRO", "ECC", "SNG", "ISA", "JER", "LAM", "EZK", "DAN", "HOS",
            "JOL", "AMO", "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL"]
NT_FIRST = ["MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL", "1TH", "2TH",
            "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"]

TIMEOUT = (10, 30)  # connect, read: a stalled response fails in 30 s, not minutes
RETRIES = 3
BACKOFF = (5, 15, 45)


def http_get(url: str) -> bytes | None:
    """GET with retries; None after the last failure (network error or non-200)."""
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.content
            if r.status_code == 404:
                return None
        except requests.RequestException:
            pass
        if attempt < RETRIES - 1:
            time.sleep(BACKOFF[attempt])
    return None


def load_catalog() -> list:
    if not CSV_CACHE.exists():
        CSV_CACHE.parent.mkdir(parents=True, exist_ok=True)
        body = http_get(CSV_URL)
        if body is None:
            raise SystemExit(f"[ebible] could not download {CSV_URL}")
        CSV_CACHE.write_bytes(body)
    return list(csv.DictReader(io.StringIO(CSV_CACHE.read_text(encoding="utf-8-sig"))))


def fetch_zip(translation_id: str) -> Path | None:
    """The cached USFM zip, downloading it if needed: streamed into a temporary file and
    only moved into the cache once it opens as a zip. None if every attempt failed."""
    ZIP_CACHE.mkdir(parents=True, exist_ok=True)
    dest = ZIP_CACHE / f"{translation_id}.zip"
    if dest.exists() and zipfile.is_zipfile(dest):
        return dest
    url = f"https://eBible.org/Scriptures/{translation_id}_usfm.zip"
    for attempt in range(RETRIES):
        tmp = dest.with_suffix(".part")
        try:
            with requests.get(url, timeout=TIMEOUT, stream=True) as r:
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in r.iter_content(1 << 16):
                        fh.write(chunk)
            if zipfile.is_zipfile(tmp):
                tmp.replace(dest)
                return dest
        except requests.RequestException:
            pass
        finally:
            tmp.unlink(missing_ok=True)
        if attempt < RETRIES - 1:
            time.sleep(BACKOFF[attempt])
    return None


CC_LINK = re.compile(r"creativecommons\.org/(licenses|publicdomain)/([a-z-]+)(?:/([0-9.]+))?", re.I)


def licence(translation_id: str) -> tuple[dict | None, str]:
    """(licence entry for _meta.json, "") if the edition can be republished, else
    (None, reason). Read from the edition's copyright page (cached)."""
    COPYRIGHT_CACHE.mkdir(parents=True, exist_ok=True)
    cache = COPYRIGHT_CACHE / f"{translation_id}.htm"
    if not cache.exists():
        body = http_get(f"https://ebible.org/{translation_id}/copyright.htm")
        if body is None:
            return None, "no copyright page"
        cache.write_bytes(body)
    raw = cache.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    links = {(m.group(1).lower(), m.group(2).lower(), m.group(3)) for m in CC_LINK.finditer(raw)}
    says_nd = bool(re.search(r"no[ -]?deriv|noderiv", text, re.I))
    if any("nd" in kind.split("-") for _, kind, _ in links) or says_nd:
        return None, "No Derivatives"
    url = f"https://ebible.org/{translation_id}/copyright.htm"
    cc = sorted(k for k in links if k[0] == "licenses")
    if len(cc) == 1:
        _, kind, version = cc[0]
        name = "CC " + kind.upper() + (f" {version}" if version else "")
        return {"type": name, "url": f"https://creativecommons.org/licenses/{kind}/{version or '4.0'}/"}, ""
    if len(cc) > 1:
        return None, "several licences on the page"
    if any(k[:2] == ("publicdomain", "zero") for k in links):
        return {"type": "CC0 1.0", "url": "https://creativecommons.org/publicdomain/zero/1.0/"}, ""
    if any(k[0] == "publicdomain" for k in links) or re.search(r"\bpublic domain\b", text, re.I):
        if re.search(r"all rights reserved|license agreement", text, re.I):
            return None, "public domain mentioned, but rights reserved"
        return {"type": "Public Domain", "url": url}, ""
    if re.search(r"all rights reserved", text, re.I):
        return None, "All rights reserved"
    return None, "no licence stated"


def helloao_translations() -> list:
    if not HELLOAO_TRANSLATIONS.exists():
        body = http_get(f"{HELLOAO_API}/available_translations.json")
        if body is None:
            raise SystemExit("[ebible] could not download helloAO's available_translations.json")
        HELLOAO_TRANSLATIONS.parent.mkdir(parents=True, exist_ok=True)
        HELLOAO_TRANSLATIONS.write_bytes(body)
    return json.loads(HELLOAO_TRANSLATIONS.read_text(encoding="utf-8"))["translations"]


def on_helloao(translations: list) -> dict[str, str]:
    """eBible translationId (lowercase) -> the helloAO translation taken from it."""
    out = {}
    for t in translations:
        for url in (t.get("website"), t.get("licenseUrl")):
            m = re.search(r"details\.php\?id=([^&#]+)", url or "")
            if m:
                out[m.group(1).lower()] = t["id"]
    for ebible_id, helloao_id in SAME_AS_HELLOAO.items():
        out[ebible_id] = helloao_id
    return out


def letters(verses: list) -> str:
    """A chapter's text as lowercase letters only (no accents, spaces or punctuation), so
    digitization differences don't count as different text."""
    s = unicodedata.normalize("NFKD", " ".join(v["text"] for v in verses).lower())
    return "".join(c for c in s if unicodedata.category(c).startswith("L"))


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def helloao_chapter(tid: str, book: str, chapter: str) -> list | None:
    cache = HELLOAO_CHAPTERS / tid / f"{book}_{chapter}.json"
    if not cache.exists():
        body = http_get(f"{HELLOAO_API}/{tid}/{book}/{chapter}.json")
        if body is None:
            return None
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(body)
    usj = chapter_to_usj(json.loads(cache.read_text(encoding="utf-8")), book)
    return extract_usj(usj).get(chapter)


def own_chapter(edition_dir: Path, book: str, chapter: str) -> list | None:
    f = edition_dir / f"{book}.json"
    if not f.exists():
        return None
    return extract_usj(json.loads(f.read_text(encoding="utf-8"))).get(chapter)


def find_duplicate(iso: str, samples: dict, translations: list) -> dict | None:
    """The first reachable edition in `iso` whose text matches every shared sample, with its
    scores, or None. samples: {(book, chapter): letters}."""
    others = [("helloao", t["id"]) for t in translations if t.get("language") == iso]
    for root in OWN_USJ:
        others += [(root.name.replace("-usj", ""), str(d)) for d in sorted((root / iso).glob("*")) if d.is_dir()]
    for source, ref in others:
        scores = {}
        for (book, chapter), text in samples.items():
            theirs = helloao_chapter(ref, book, chapter) if source == "helloao" else own_chapter(Path(ref), book, chapter)
            if theirs:
                scores[f"{book} {chapter}"] = round(similarity(text, letters(theirs)), 3)
        if scores and min(scores.values()) >= DUPLICATE_SCORE:
            return {"source": source, "edition": ref if source == "helloao" else Path(ref).name, "scores": scores}
    return None


def sample_chapters(z: zipfile.ZipFile) -> dict:
    """{(book, "1"): letters} for the first Old Testament and first New Testament book in the zip."""
    books = {}
    for name in z.namelist():
        if name.endswith(".usfm"):
            raw = z.read(name).decode("utf-8", "replace")
            m = re.search(r"^\\id\s+(\S+)", raw, re.M)
            if m:
                books[m.group(1).upper()] = raw
    out = {}
    for order in (OT_FIRST, NT_FIRST):
        book = next((b for b in order if b in books), None)
        if book:
            verses = extract_usj(convert_book(books[book])).get("1")
            if verses:
                out[(book, "1")] = letters(verses)
    return out


def edition_meta(row: dict, lic: dict) -> dict:
    tid = row["translationId"]
    meta = {
        "name": row.get("title") or row.get("languageNameInEnglish"),
        "licenses": [lic],
        "provider": "eBible.org",
        "source": f"https://ebible.org/Scriptures/details.php?id={tid}",
    }
    copyright_text = (row.get("Copyright") or "").strip()
    if copyright_text and copyright_text.lower() != "public domain":
        meta["copyright"] = copyright_text
    return meta


def convert_book(raw: str, strongs: bool = True) -> dict:
    """USFM -> USJ (usfmtc). strongs=False drops Strong's tags (usfm_to_verses.drop_strongs): eBible
    editions; CrossWire and Door43 share this converter and have none."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".usfm", delete=False, encoding="utf-8") as tf:
        tf.write(protect(raw))  # `|` used as text survives usfmtc
        tmp_path = tf.name
    try:
        usj = restore(usfmtc.readFile(tmp_path).outUsj())
        fix_adjacent_w_spacing(usj)
        if strongs is False:
            drop_strongs(usj)
        return usj
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def process_translation(row: dict, force: bool, outcome: collections.Counter, reasons: collections.Counter,
                        failed: list, helloao: dict, translations: list, duplicates: dict) -> int:
    """Books written for one edition (0 if skipped); the counters and records are updated."""
    tid, iso = row["translationId"], row["languageCode"]
    edition_dir = USJ_OUT_DIR / iso / tid
    if tid.lower() in helloao:
        outcome["on helloAO"] += 1
        return 0
    lic, reason = licence(tid)
    if lic is None:
        outcome["skipped (licence)"] += 1
        reasons[reason] += 1
        return 0
    if edition_dir.exists() and not force:
        if not (edition_dir / META_FILE).exists():
            write_meta(edition_dir, edition_meta(row, lic), FORMATS)
        outcome["already present"] += 1
        return 0

    zip_path = fetch_zip(tid)
    if zip_path is None:
        outcome["download failed"] += 1
        failed.append(tid)
        return 0

    books = 0
    with zipfile.ZipFile(zip_path) as z:
        samples = sample_chapters(z)
        dup = find_duplicate(iso, samples, translations) if samples else None
        duplicates[tid] = {"duplicate_of": dup, "samples": [f"{b} {c}" for b, c in samples]}
        if dup:
            outcome["duplicate (same text)"] += 1
            return 0
        for name in z.namelist():
            if not name.endswith(".usfm"):
                continue
            try:
                raw = z.read(name).decode("utf-8")
            except UnicodeDecodeError:
                print(f"  WARNING: {tid}/{name} is not UTF-8, skipped")
                continue
            m = re.search(r"^\\id\s+(\S+)", raw, re.M)
            if not m or m.group(1).upper() in SKIP_BOOKS:
                continue
            book = m.group(1).upper()
            try:
                usj = convert_book(raw, strongs=False)
            except Exception as e:
                print(f"  WARNING: {tid}/{book} USJ extraction failed: {e}")
                outcome["book extraction failures"] += 1
                continue
            edition_dir.mkdir(parents=True, exist_ok=True)
            (edition_dir / f"{book}.json").write_text(
                json.dumps(usj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            books += 1
    if books:
        write_meta(edition_dir, edition_meta(row, lic), FORMATS)
        outcome["written"] += 1
    else:
        outcome["no USFM"] += 1
    return books


def main():
    force = "--force" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    only_id = sys.argv[sys.argv.index("--translation-id") + 1] if "--translation-id" in sys.argv else None

    catalog = load_catalog()
    candidates = [r for r in catalog if r["Redistributable"] == "True" and r["downloadable"] == "True"]
    if only_id:
        candidates = [r for r in candidates if r["translationId"] == only_id]
    if limit:
        candidates = candidates[:limit]
    print(f"[ebible] {len(candidates)} redistributable+downloadable candidates "
          f"(of {len(catalog)} eBible translations)")

    translations = helloao_translations()
    helloao = on_helloao(translations)
    duplicates = json.loads(DUPLICATES_FILE.read_text(encoding="utf-8")) if DUPLICATES_FILE.exists() else {}
    outcome, reasons, failed = collections.Counter(), collections.Counter(), []
    total_books = 0
    for i, row in enumerate(candidates, 1):
        total_books += process_translation(row, force, outcome, reasons, failed, helloao, translations, duplicates)
        DUPLICATES_FILE.parent.mkdir(parents=True, exist_ok=True)
        DUPLICATES_FILE.write_text(json.dumps(duplicates, ensure_ascii=False, indent=1), encoding="utf-8")
        if i % 50 == 0 or i == len(candidates):
            print(f"[ebible] [{i}/{len(candidates)}] {dict(outcome)}", flush=True)

    print(f"[ebible] done: {dict(outcome)}; {total_books} USJ book files -> {USJ_OUT_DIR}")
    if reasons:
        print(f"[ebible] skipped for licence: {dict(reasons)}")
    dups = {k: v["duplicate_of"] for k, v in duplicates.items() if v["duplicate_of"]}
    if dups:
        print(f"[ebible] same text as an edition we already reach: "
              + ", ".join(f"{k} = {v['source']}:{v['edition']}" for k, v in dups.items()))
    if failed:
        print(f"[ebible] download failed after {RETRIES} attempts (rerun to retry): {' '.join(failed)}")


if __name__ == "__main__":
    main()
