#!/usr/bin/env python3
"""Generate /dbt/<iso>/media.json for each language with audio or text.

Scans export/ALL-langs/ to discover per-language, per-canon audio/timing/text
availability across all filesets, and emits compact metadata per the
CDN contract (example/plan-docs/dbt-timecode-feedback.md §3).

Output: export/dbt/<iso>/media.json
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, EXPORT, TIMING_DIR, LEGACY_TIMING_DIR, ALIGN_CACHE_DIR, SORTED_DIR  # noqa: E402

EXPORT_DIR = EXPORT / "ALL-langs"
OUTPUT_DIR = EXPORT / "dbt"
V11N_INDEX = EXPORT / "versification" / "index.json"

# Canonical 66-book set, same list generate_catalog_index.py uses, to decide
# whether a canon's timingBooks/audioBooks count represents FULL coverage
# (no need for the book codes themselves) or partial (list them explicitly).
OT_BOOKS = {"GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA", "1KI", "2KI",
            "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO", "ECC", "SNG", "ISA", "JER",
            "LAM", "EZK", "DAN", "HOS", "JOL", "AMO", "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL"}
NT_BOOKS = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL",
            "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"}
FULL_CANON_SIZE = {"nt": len(NT_BOOKS), "ot": len(OT_BOOKS)}

CATEGORY_TO_MEDIA = {
    "with-timecode": "at",
    "audio-with-timecode": "at",
    "audio-only": "a",
    "text-only": "",
    "syncable": "",
}

SOURCE_ORDER = ["cdn", "helloao", "ebible", "contrib", "dbt"]

# Compact source codec for media-index.json: single char per source, fixed order
SOURCE_CHAR = {"cdn": "c", "helloao": "h", "contrib": "r", "dbt": "d", "ebible": "e"}
SOURCE_CHAR_ORDER = ["c", "h", "e", "r", "d"]

TIMING_SOURCES = [
    TIMING_DIR / "BB",
    TIMING_DIR / "contrib",
    TIMING_DIR / "helloao" / "aligned",
    LEGACY_TIMING_DIR,
    ALIGN_CACHE_DIR,
]


def detect_sources(data: dict) -> set[str]:
    a = data.get("a", "")
    t = data.get("t", "")
    t_alt = data.get("t_alt", "")
    sources = set()
    if a.startswith("contrib:"):
        sources.add("contrib")
    elif a:
        sources.add("dbt")
    if "helloao:" in t or "helloao:" in t_alt:
        sources.add("helloao")
    if "ebible:" in t:
        sources.add("ebible")
    return sources


def count_timing_books() -> dict[tuple[str, str, str], set[str]]:
    """Count books with timing data per (canon, iso, fileset) from all sources."""
    books_by_fileset: dict[tuple[str, str, str], set[str]] = defaultdict(set)

    for base in TIMING_SOURCES:
        if not base.exists():
            continue
        for tf in base.rglob("*_timing.json"):
            parts = tf.parts
            for anchor in ("BB", "contrib", "aligned", "legacy-timing-data", "align-cache"):
                if anchor in parts:
                    idx = parts.index(anchor)
                    if idx + 4 < len(parts):
                        canon = parts[idx + 1]
                        iso = parts[idx + 2]
                        distinct_id = parts[idx + 3]
                        book = parts[idx + 4]
                        books_by_fileset[(canon, iso, distinct_id)].add(book)
                    break

    return books_by_fileset


def count_audio_books() -> dict[tuple[str, str], set[str]]:
    """Book codes with audio per (canon, iso) from sorted metadata."""
    sorted_dir = SORTED_DIR
    if not sorted_dir.is_dir():
        return {}

    books_by_lang: dict[tuple[str, str], set[str]] = defaultdict(set)

    for iso_dir in sorted_dir.iterdir():
        if not iso_dir.is_dir():
            continue
        for fileset_dir in iso_dir.iterdir():
            if not fileset_dir.is_dir():
                continue
            meta_path = fileset_dir / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                canon_raw = meta.get("canon", "")
                canon = "nt" if "nt" in canon_raw.lower() else "ot" if "ot" in canon_raw.lower() else ""
                if not canon:
                    continue
                iso = meta.get("language", {}).get("iso", "")
                if not iso:
                    continue
                book_list = meta.get("books", [])
                for book in book_list:
                    book_id = book.get("book_id", "") if isinstance(book, dict) else str(book)
                    if book_id:
                        books_by_lang[(canon, iso)].add(book_id)
            except Exception:
                continue

    return dict(books_by_lang)


def find_audio_filesets_from_timing(canon: str, iso: str, fileset_id: str) -> set[str]:
    """Extract audio fileset IDs from timing filenames for a given fileset."""
    audio_filesets = set()
    for base in TIMING_SOURCES:
        if not base.exists():
            continue
        for anchor in ("BB", "contrib", "aligned", "legacy-timing-data", "align-cache"):
            search_dir = base
            if anchor == "aligned":
                search_dir = base
            fileset_path = None
            for candidate in [
                base / canon / iso / fileset_id,
            ]:
                if candidate.is_dir():
                    fileset_path = candidate
                    break
            if not fileset_path:
                continue
            for tf in fileset_path.rglob("*_timing.json"):
                name = tf.stem.replace("_timing", "")
                parts = name.split("_", 2)
                if len(parts) >= 3:
                    audio_filesets.add(parts[2])
    return audio_filesets


def main():
    if not EXPORT_DIR.is_dir():
        print("[ERROR] export/ALL-langs not found. Run export-stories first.")
        return

    print("[INFO] Counting timing books across all sources...")
    timing_books_map = count_timing_books()

    print("[INFO] Counting audio books from sorted metadata...")
    audio_books_set_map = count_audio_books()

    # Versification scheme per DBT fileset (iso/fileset -> scheme code)
    v11n = {}
    if V11N_INDEX.exists():
        v11n = json.loads(V11N_INDEX.read_text())

    # Collect per (iso, canon): all filesets with their details
    # Structure: lang_data[iso][canon] = list of fileset entries
    lang_filesets: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    lang_sources: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    lang_helloao: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))

    for canon_dir in sorted(EXPORT_DIR.iterdir()):
        if not canon_dir.is_dir():
            continue
        canon = canon_dir.name

        for cat_dir in sorted(canon_dir.iterdir()):
            if not cat_dir.is_dir():
                continue
            category = cat_dir.name

            if category not in CATEGORY_TO_MEDIA:
                continue

            media_code = CATEGORY_TO_MEDIA[category]

            for iso_dir in sorted(cat_dir.iterdir()):
                if not iso_dir.is_dir():
                    continue
                iso = iso_dir.name

                for fileset_dir in sorted(iso_dir.iterdir()):
                    if not fileset_dir.is_dir():
                        continue
                    data_file = fileset_dir / "data.json"
                    if not data_file.exists():
                        continue

                    fileset_id = fileset_dir.name
                    with open(data_file) as f:
                        data = json.load(f)

                    sources = detect_sources(data)
                    lang_sources[iso][canon].update(sources)

                    # Collect helloAO text IDs
                    for field in ("t", "t_alt"):
                        val = data.get(field, "")
                        if val.startswith("helloao:"):
                            lang_helloao[iso][canon].add(val[8:])

                    entry: dict = {"id": fileset_id, "media": media_code}

                    # Add audio filesets
                    audio_fs = find_audio_filesets_from_timing(canon, iso, fileset_id)
                    if audio_fs:
                        entry["a"] = sorted(audio_fs)

                    # Add text fileset if category has text
                    if category in ("with-timecode", "text-only", "syncable"):
                        entry["t"] = fileset_id

                    # Add versification scheme if fingerprinted (DBT-native)
                    scheme = v11n.get(f"{iso}/{fileset_id}")
                    if scheme:
                        entry["v11n"] = scheme

                    lang_filesets[iso][canon].append(entry)

    # Write media.json per language (including text-only)
    files_written = 0
    for iso in sorted(lang_filesets):
        canons_out = {}

        for canon in ("nt", "ot"):
            filesets = lang_filesets[iso].get(canon, [])

            if not filesets:
                canons_out[canon] = {"media": ""}
                continue

            # Top-level media = richest across filesets
            all_media = [fs.get("media", "") for fs in filesets]
            if any("at" == m for m in all_media):
                top_media = "at"
            elif any("a" == m for m in all_media):
                top_media = "a"
            else:
                top_media = ""

            canon_out: dict = {"media": top_media}

            sources = lang_sources[iso].get(canon, set())
            if sources:
                canon_out["sources"] = [s for s in SOURCE_ORDER if s in sources]

            # Only include filesets that have audio
            audio_filesets = [fs for fs in filesets if "a" in fs.get("media", "")]
            if audio_filesets:
                canon_out["filesets"] = audio_filesets

            # helloAO text IDs
            hao_ids = lang_helloao.get(iso, {}).get(canon, set())
            if hao_ids:
                canon_out["h"] = sorted(hao_ids)

            # Book counts. The count alone is ambiguous ("8 of how many?") —
            # when it's a full canon (27 NT / 39 OT), that's self-evident and
            # the set would be redundant; when it's partial, also publish the
            # actual book codes so a client can grey out unavailable books
            # without a per-book fetch.
            timing_books = set()
            for fs in filesets:
                timing_books.update(timing_books_map.get((canon, iso, fs["id"]), set()))
            if timing_books:
                canon_out["timingBooks"] = len(timing_books)
                if len(timing_books) < FULL_CANON_SIZE[canon]:
                    canon_out["timingBooksSet"] = sorted(timing_books)

            ab_set = audio_books_set_map.get((canon, iso))
            if ab_set:
                canon_out["audioBooks"] = len(ab_set)
                if len(ab_set) < FULL_CANON_SIZE[canon]:
                    canon_out["audioBooksSet"] = sorted(ab_set)

            canons_out[canon] = canon_out

        output = {"iso": iso, "canons": canons_out}

        out_dir = OUTPUT_DIR / iso
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "media.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
        files_written += 1

    print(f"[INFO] Written {files_written} media.json files to export/dbt/")

    # Load language names: ALL-langs-compact → helloAO catalog → DBS cache
    names = {}
    compact_path = EXPORT / "ALL-langs-compact.json"
    if compact_path.exists():
        with open(compact_path) as f:
            compact = json.load(f)
        for canon_data in compact.get("canons", {}).values():
            for cat_data in canon_data.values():
                for iso, entry in cat_data.items():
                    if iso not in names and "n" in entry:
                        nm = {"nm": entry["n"]}
                        if "v" in entry:
                            nm["v"] = entry["v"]
                        if "s" in entry:
                            nm["sc"] = entry["s"]
                        names[iso] = nm

    # Fallback: helloAO catalog
    helloao_path = API_CACHE / "helloao" / "available_translations.json"
    if helloao_path.exists():
        with open(helloao_path) as f:
            hao = json.load(f)
        for t in hao.get("translations", hao if isinstance(hao, list) else []):
            iso = t.get("language", "")
            if iso and iso not in names:
                eng = t.get("languageEnglishName", "")
                if eng:
                    nm = {"nm": eng}
                    vern = t.get("languageName", "")
                    if vern and vern != eng:
                        nm["v"] = vern
                    names[iso] = nm

    # Fallback: DBS bible details cache
    dbs_dir = API_CACHE / "dbs" / "bibles"
    if dbs_dir.is_dir():
        for p in sorted(dbs_dir.glob("*.json")):
            if p.name == "index.json":
                continue
            try:
                with open(p) as f:
                    d = json.load(f)
                iso = d.get("iso", "")
                if iso and iso not in names:
                    lang = d.get("language", {})
                    eng = lang.get("name", "")
                    if eng:
                        nm = {"nm": eng}
                        vern = lang.get("autonym", "")
                        if vern and vern != eng:
                            nm["v"] = vern
                        names[iso] = nm
            except (json.JSONDecodeError, IOError):
                continue

    # Build media-index.json roll-up (compact: omit "m" when "", omit canon when empty)
    index = {}
    for iso in sorted(lang_filesets):
        entry = {}
        for canon, key in (("nt", "n"), ("ot", "o")):
            filesets = lang_filesets[iso].get(canon, [])
            canon_entry: dict = {}

            if filesets:
                all_media = [fs.get("media", "") for fs in filesets]
                if any("at" == m for m in all_media):
                    canon_entry["m"] = "at"
                elif any("a" == m for m in all_media):
                    canon_entry["m"] = "a"

                sources = lang_sources[iso].get(canon, set())
                if sources:
                    s = "".join(c for c in SOURCE_CHAR_ORDER
                                if c in {SOURCE_CHAR[src] for src in sources})
                    if s:
                        canon_entry["s"] = s

            if canon_entry:
                entry[key] = canon_entry

        name_info = names.get(iso)
        if name_info:
            entry.update(name_info)

        index[iso] = entry

    names_found = sum(1 for e in index.values() if "nm" in e)

    app_dir = OUTPUT_DIR / "_app"
    app_dir.mkdir(parents=True, exist_ok=True)
    index_out = {"time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "l": index}
    with open(app_dir / "media-index.json", "w", encoding="utf-8") as f:
        json.dump(index_out, f, ensure_ascii=False, separators=(",", ":"))

    print(f"[INFO] Written media-index.json with {len(index)} languages ({names_found} with names)")


if __name__ == "__main__":
    main()
