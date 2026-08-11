#!/usr/bin/env python3
"""Generate /catalog/<iso[0]>/<iso>/books.json — per-language edition
metadata (vernacular book names, license/year, script direction, font
hints) merged across DBT, PKF, and helloAO. See internal-docs/ design
conversation (2026-08-11) for the full format rationale.

Source: purely local, already-cached data — no live fetch happens here
(that's fetch_pkf_book_data.py / fetch_helloao_book_data.py, run first):
  - DBT:     internal-data/api-cache/bibles/bible_details/*.json
  - PKF:     internal-data/api-cache/pkf-books/<iso>/{app-config,info}.json
             + <collection>.json (from pkf-manifest.json's catalog field)
  - helloAO: internal-data/api-cache/helloao/available_translations.json
             + internal-data/api-cache/helloao-books/<id>.json

Deliberately NOT a forced common shape across sources — DBT's free-text
`mark` field is passed through verbatim rather than parsed into a
structured license code (would be a guess, against this project's
"verified only, never inferred" principle); PKF's richer toc2/per-chapter
verse counts and helloAO's third name tier are kept even though the other
sources don't have an equivalent, rather than dropped for uniformity.

Sharded by iso[0] (first letter) so the top-level /catalog/ directory
doesn't end up with ~2000 iso subdirectories.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, PKF_BOOKS_CACHE, HELLOAO_BOOKS_CACHE, EXPORT  # noqa: E402

BOOKS_OUT_DIR = EXPORT / "catalog"

OT_CODES = {
    "GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA",
    "1KI", "2KI", "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO",
    "ECC", "SNG", "ISA", "JER", "LAM", "EZK", "DAN", "HOS", "JOL", "AMO",
    "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL",
}
NT_CODES = {
    "MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH",
    "PHP", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS",
    "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV",
}


def testament_of(code):
    if code in OT_CODES:
        return "ot"
    if code in NT_CODES:
        return "nt"
    return None  # deuterocanon / peripheral — omitted from "t", not guessed


# ---- DBT ----

def load_dbt():
    """iso -> {"d:<abbr>": {...}}"""
    out = {}
    details_dir = API_CACHE / "bibles" / "bible_details"
    if not details_dir.is_dir():
        print("[catalog-books] WARNING: no bible_details cache — DBT skipped", file=sys.stderr)
        return out

    for f in details_dir.glob("*.json"):
        try:
            d = json.loads(f.read_text())["data"]
        except Exception:
            continue
        iso = d.get("iso")
        abbr = d.get("abbr")
        if not iso or not abbr:
            continue

        # DBT's "name" field is consistently publisher/year attribution
        # text (near-duplicate of "mark"), NOT the version title — e.g.
        # AAIWBT's name is "2009 Wycliffe Bible Translators, Inc." while
        # its vname, "Tur Gewasin O Baibasit Boubun", is the real title.
        # Confirmed across multiple real records before relying on this;
        # "name" is only used as a fallback when vname is genuinely absent.
        entry = {"n": d.get("vname") or d.get("name") or abbr}
        if d.get("mark"):
            entry["license"] = {"mark": d["mark"]}
        date = d.get("date")
        if date:
            try:
                entry["year"] = int(str(date)[:4])
            except ValueError:
                pass

        alphabet = d.get("alphabet")
        if isinstance(alphabet, dict):
            if alphabet.get("direction"):
                entry["dir"] = alphabet["direction"]
            font = {}
            if "requires_font" in alphabet:
                font["requiresFont"] = bool(alphabet["requires_font"])
            if alphabet.get("primary_font"):
                font["primaryFont"] = alphabet["primary_font"]
            if font:
                entry["font"] = font

        books = []
        for b in d.get("books") or []:
            code = b.get("book_id")
            if not code:
                continue
            row = {"code": code, "n": b.get("name") or code, "ns": b.get("name_short") or b.get("name") or code}
            t = testament_of(code)
            if t:
                row["t"] = t
            chapters = b.get("chapters")
            if isinstance(chapters, list) and chapters:
                row["c"] = len(chapters)
            books.append(row)
        if books:
            entry["books"] = books

        out.setdefault(iso, {})[f"d:{abbr}"] = entry
    return out


# ---- PKF ----

def load_pkf():
    """iso -> {"p:<collectionId>": {...}}"""
    out = {}
    manifest_path = API_CACHE / "pkf-manifest.json"
    if not manifest_path.exists():
        print("[catalog-books] WARNING: no pkf-manifest.json — PKF skipped", file=sys.stderr)
        return out
    manifest = json.loads(manifest_path.read_text())["languages"]

    for iso, lang in manifest.items():
        lang_dir = PKF_BOOKS_CACHE / iso
        if not lang_dir.is_dir():
            continue

        app_config = {}
        app_config_path = lang_dir / "app-config.json"
        if app_config_path.exists():
            try:
                app_config = json.loads(app_config_path.read_text())
            except Exception:
                app_config = {}

        font_assets = []
        info_path = lang_dir / "info.json"
        if info_path.exists():
            try:
                info = json.loads(info_path.read_text())
                for asset in info.get("assets", []):
                    if asset.get("kind") == "font":
                        font_assets.append({"name": asset.get("name"), "url": asset.get("url")})
            except Exception:
                pass

        for collection in lang.get("collections", []):
            catalog_name = collection.get("catalog")
            if not catalog_name:
                continue
            catalog_path = lang_dir / catalog_name
            if not catalog_path.exists():
                continue
            try:
                catalog = json.loads(catalog_path.read_text())
            except Exception:
                continue

            collection_id = catalog.get("selectors", {}).get("abbr") or collection.get("catalog", "").split("_")[-1]
            entry = {"n": lang.get("nm") or iso}

            copyright_block = app_config.get("copyright") or {}
            lic = {}
            if copyright_block.get("license"):
                lic["license"] = copyright_block["license"]
            if copyright_block.get("holder"):
                lic["holder"] = copyright_block["holder"]
            if copyright_block.get("source"):
                lic["source"] = copyright_block["source"]
            if copyright_block.get("notice_url"):
                lic["noticeUrl"] = copyright_block["notice_url"]
            if lic:
                entry["license"] = lic
            if isinstance(copyright_block.get("year"), int):
                entry["year"] = copyright_block["year"]

            text_dir = app_config.get("collection", {}).get("textDirection")
            if text_dir:
                entry["dir"] = text_dir
            if font_assets:
                entry["font"] = font_assets

            books = []
            for doc in catalog.get("documents", []):
                code = doc.get("bookCode")
                if not code:
                    continue
                row = {"code": code, "n": doc.get("h") or code, "ns": doc.get("toc3") or doc.get("h") or code}
                if doc.get("toc2"):
                    row["toc2"] = doc["toc2"]
                t = testament_of(code)
                if t:
                    row["t"] = t
                vbc = doc.get("versesByChapters") or {}
                if vbc:
                    try:
                        chapter_nums = sorted((int(c) for c in vbc.keys()))
                        row["c"] = len(chapter_nums)
                        row["v"] = [len(vbc[str(c)]) for c in chapter_nums]
                    except (ValueError, TypeError):
                        pass
                books.append(row)
            if books:
                entry["books"] = books

            out.setdefault(iso, {})[f"p:{collection_id}"] = entry
    return out


# ---- helloAO ----

def load_helloao():
    """iso -> {"h:<translationId>": {...}}"""
    out = {}
    translations_path = API_CACHE / "helloao" / "available_translations.json"
    if not translations_path.exists():
        print("[catalog-books] WARNING: no helloAO available_translations.json — helloAO skipped", file=sys.stderr)
        return out
    translations = json.loads(translations_path.read_text())["translations"]

    for t in translations:
        tid = t.get("id")
        iso = t.get("language")
        if not tid or not iso:
            continue
        books_path = HELLOAO_BOOKS_CACHE / f"{tid}.json"
        if not books_path.exists():
            continue
        try:
            data = json.loads(books_path.read_text())
        except Exception:
            continue

        entry = {"n": t.get("englishName") or t.get("name") or tid}
        if t.get("licenseUrl"):
            entry["license"] = {"licenseUrl": t["licenseUrl"]}
        if t.get("textDirection"):
            entry["dir"] = t["textDirection"]

        books = []
        for b in data.get("books", []):
            code = b.get("id")
            if not code:
                continue
            row = {"code": code, "n": b.get("name") or code, "ns": b.get("commonName") or b.get("name") or code}
            if b.get("title") and b.get("title") not in (row["n"], row["ns"]):
                row["title"] = b["title"]
            tst = testament_of(code)
            if tst:
                row["t"] = tst
            if isinstance(b.get("numberOfChapters"), int):
                row["c"] = b["numberOfChapters"]
            if isinstance(b.get("totalNumberOfVerses"), int):
                row["verses"] = b["totalNumberOfVerses"]
            books.append(row)
        if books:
            entry["books"] = books

        out.setdefault(iso, {})[f"h:{tid}"] = entry
    return out


def merge(*sources):
    merged = {}
    for source in sources:
        for iso, entries in source.items():
            merged.setdefault(iso, {}).update(entries)
    return merged


def main():
    dbt = load_dbt()
    pkf = load_pkf()
    helloao = load_helloao()
    merged = merge(dbt, pkf, helloao)

    written = 0
    for iso, entries in sorted(merged.items()):
        if not iso:
            continue
        out_path = BOOKS_OUT_DIR / iso[0] / iso / "books.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"iso": iso, "entries": entries}
        out_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        written += 1

    print(f"[catalog-books] {len(dbt)} iso with DBT, {len(pkf)} with PKF, {len(helloao)} with helloAO "
          f"-> {written} books.json files under {BOOKS_OUT_DIR}")


if __name__ == "__main__":
    main()
