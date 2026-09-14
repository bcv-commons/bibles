#!/usr/bin/env python3
"""Generate /dbt/<iso>/media.json for each language with audio or text.

Discovers per-language, per-canon audio/timing/text availability directly
from this repo's own live caches — internal-data/sorted/BB (DBT, via
sort_cache_data.py), the helloAO/eBible catalogs, and the local contrib
timing override directory — and emits compact metadata per the CDN
contract (example/plan-docs/dbt-timecode-feedback.md §3).

Migrated 2026-09-12 off export/ALL-langs (MONO's frozen, Jul-28-dated
export-stories output), which was the root cause of new DBT editions
(e.g. ENGBER) being invisible here indefinitely. Traced and empirically
verified before the cutover (session history) that this loses nothing
real: every fileset that reaches media.json's `filesets` array already
has a real DBT-shaped abbr with no cross-source pairing dependency, and
the `sources`/`h` fields' live re-derivation was diffed against the old
ALL-langs-based computation across all (iso, canon) pairs — every
mismatch traced to the old pipeline being stale or, in two cases, an
existing detect_sources() mislabeling bug, never a case of the live
derivation missing real information.

Output: export/dbt/<iso>/media.json
"""

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import (  # noqa: E402
    API_CACHE, EXPORT, TIMING_DIR, SORTED_DIR, HELLOAO_BOOK_COMPLETENESS_FILE, ALIGN_SOURCES_FILE,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from timing_index import load_resolved, resolved_of  # noqa: E402

OUTPUT_DIR = EXPORT / "dbt"
V11N_INDEX = EXPORT / "versification" / "index.json"
EBIBLE_CSV = API_CACHE / "ebible" / "translations.csv"
CONTRIB_DIR = TIMING_DIR / "contrib"

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

def classify(has_text: bool, has_audio: bool, has_timing: bool) -> str | None:
    """Same 5-category logic as sort_cache_data.py's determine_category(),
    applied directly from a fileset's own canon_has_text/canon_has_audio/
    canon_has_timing flags rather than its precomputed aggregate_category —
    that field short-circuits to "partial" for PARTIAL-canon bibles without
    checking these at all, which would lose the real media-code signal for
    partial editions (e.g. PORALM)."""
    if has_timing:
        if has_text and has_audio:
            return "with-timecode"
        if has_audio:
            return "audio-with-timecode"
        if has_text:
            return "text-only"
        return None
    if has_text and has_audio:
        return "syncable"
    if has_text:
        return "text-only"
    if has_audio:
        return "audio-only"
    return None


def discover_dbt_filesets(v11n: dict, resolved: dict, align_sources: dict) -> tuple[dict, dict]:
    """Walk internal-data/sorted/BB (live, DBT-only) and return
    (lang_filesets, dbt_has_audio) — lang_filesets[iso][canon] is the same
    shape the old export/ALL-langs walk produced (one entry per real DBT
    bible abbr); dbt_has_audio[iso][canon] mirrors the old detect_sources()'s
    "dbt" tag semantic (audio presence only, not text — verified empirically
    against the ALL-langs-based computation before this migration)."""
    flags: dict[tuple[str, str, str], dict] = {}  # (iso, abbr, canon) -> has_text/has_audio/has_timing

    for iso_dir in sorted(p for p in SORTED_DIR.iterdir() if p.is_dir()):
        iso = iso_dir.name
        for fileset_dir in sorted(p for p in iso_dir.iterdir() if p.is_dir()):
            meta_path = fileset_dir / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text())
            except Exception:
                continue

            abbr = meta.get("bible", {}).get("abbr", "")
            if not abbr:
                continue
            canon_raw = meta.get("canon", "")
            cat = meta.get("categorization", {})
            books = meta.get("books") or []
            testaments = {b.get("testament") for b in books if b.get("testament")}
            fs_id = meta.get("fileset", {}).get("id", "")

            canons = set()
            if canon_raw == "NT":
                canons.add("nt")
            elif canon_raw == "OT":
                canons.add("ot")
            elif canon_raw == "FULL":
                canons.update({"nt", "ot"})
            else:  # PARTIAL / VARIOUS / STORY — use real testament from books[]
                if "NT" in testaments:
                    canons.add("nt")
                if "OT" in testaments:
                    canons.add("ot")

            for canon in canons:
                key = (iso, abbr, canon)
                flag = flags.setdefault(
                    key, {"has_text": False, "has_audio": False, "audio_fileset_ids": set()}
                )
                flag["has_text"] = flag["has_text"] or bool(cat.get("canon_has_text"))
                flag["has_audio"] = flag["has_audio"] or bool(cat.get("canon_has_audio"))
                if cat.get("has_audio") and fs_id:
                    flag["audio_fileset_ids"].add(fs_id)

    lang_filesets: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    dbt_has_audio: dict[str, dict[str, bool]] = defaultdict(lambda: defaultdict(bool))

    for (iso, abbr, canon), flag in sorted(flags.items()):
        # has_timing must come from timing_index.load_resolved() (real
        # timing — bibles' own owned sources plus audio-sync's real work,
        # distilled from their _runs/ manifests by pull_align_manifests.py),
        # not sort_cache_data.py's DBT-self-declared canon_has_timing
        # (audio_timestamps_filesets.json)
        # — that flag is narrower and disagrees with real confirmed timing
        # we already have for plenty of editions (verified: e.g. eng/ENGNLV
        # has real legacy-timing-data coverage DBT's own flag doesn't know
        # about). Using DBT's flag here would wrongly classify such editions
        # as untimed "syncable" (media="") even though real timing exists.
        #
        # Intersect against REAL known audio fileset ids for this abbr, not
        # a string-prefix guess — verified false negatives from prefix
        # matching (e.g. abbr "ACRNNT"'s real audio files are literally
        # named "ACRWB1N2DA_timing.json", no shared prefix at all).
        audio_fs = resolved_of(resolved, iso, flag["audio_fileset_ids"])
        category = classify(flag["has_text"], flag["has_audio"], bool(audio_fs))
        if category is None:
            continue
        media_code = CATEGORY_TO_MEDIA[category]

        entry: dict = {"id": abbr, "media": media_code}

        if audio_fs:
            entry["a"] = sorted(audio_fs)

        if flag["has_text"]:
            entry["t"] = abbr
        else:
            # Real DBT audio, no DBT-native text — audio-sync had to pull
            # text from elsewhere (usually helloAO) to align against, and
            # tells us exactly where via the manifest's text_sources map
            # (confirmed live 2026-09-14: 157+ real DBT editions hit this).
            # Surface it so a client pairs the same text audio-sync
            # actually verified, not a guess.
            pairing = align_sources.get(f"{iso}/{abbr}")
            if pairing and pairing.get("text"):
                entry["textSource"] = pairing["text"]

        scheme = v11n.get(f"{iso}/{abbr}")
        if scheme:
            entry["v11n"] = scheme

        lang_filesets[iso][canon].append(entry)
        if flag["has_audio"]:
            dbt_has_audio[iso][canon] = True

    # Editions with real, confirmed alignment that are NOT DBT editions at
    # all (e.g. eng/ENGBSBHAY — helloAO audio+text, no DBT abbr backs it)
    # — invisible to the sorted/BB walk above by construction. Without
    # this, such an edition is fully resolvable once you already know its
    # id (doc/dbt-timing.md's formula) but undiscoverable from media.json
    # itself, which defeats the point of publishing a catalog at all.
    # Confirmed live 2026-09-14: exactly 1 such edition exists today.
    known_abbrs = {(iso, abbr) for (iso, abbr, _canon) in flags}
    for key, pairing in sorted(align_sources.items()):
        iso, distinct_id = key.split("/", 1)
        if (iso, distinct_id) in known_abbrs:
            continue  # already a real DBT abbr, handled above
        if not pairing.get("audio"):
            continue  # a text_sources-only entry for a real DBT edition, not foreign audio
        books = resolved.get(iso, {}).get(distinct_id)
        if not books:
            continue  # audio-sync knows about it, but no confirmed timing yet
        for canon, book_set in (("nt", NT_BOOKS), ("ot", OT_BOOKS)):
            if not (books & book_set):
                continue
            entry = {"id": distinct_id, "media": "at", "a": [distinct_id],
                      "audioSource": pairing["audio"]}
            if pairing.get("text"):
                entry["t"] = distinct_id
                entry["textSource"] = pairing["text"]
            scheme = v11n.get(f"{iso}/{distinct_id}")
            if scheme:
                entry["v11n"] = scheme
            # Not marked into dbt_has_audio: this edition's real source is
            # whatever pairing["audio"]["source"] says (e.g. helloAO), not
            # DBT — load_helloao_sources() already covers the "sources"
            # field correctly for that case; tagging "dbt" here would
            # repeat the exact mislabeling bug found earlier this session
            # in the old ALL-langs-based detect_sources().
            lang_filesets[iso][canon].append(entry)

    return lang_filesets, dbt_has_audio


def load_helloao_sources() -> tuple[dict, dict]:
    """Per-canon helloAO TEXT presence, from the live-refreshed completeness
    cache (internal-data/comparison-results/helloao-book-completeness.json,
    see refresh_helloao_completeness.py). Returns (lang_sources, lang_helloao)
    keyed the same way the old ALL-langs-derived dicts were."""
    lang_sources: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    lang_helloao: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    if not HELLOAO_BOOK_COMPLETENESS_FILE.exists():
        return lang_sources, lang_helloao

    hao = json.loads(HELLOAO_BOOK_COMPLETENESS_FILE.read_text())
    for tid, r in hao.items():
        iso = r.get("iso", "")
        if not iso:
            continue
        if r.get("has_any_nt"):
            lang_sources[iso]["nt"].add("helloao")
            lang_helloao[iso]["nt"].add(tid)
        if r.get("has_any_ot"):
            lang_sources[iso]["ot"].add("helloao")
            lang_helloao[iso]["ot"].add(tid)
    return lang_sources, lang_helloao


def load_ebible_sources() -> dict:
    """Per-canon eBible TEXT presence, straight from the CSV's own NT/OT
    chapter counts (already live, self-fetched by fetch_ebible_cache.py)."""
    lang_sources: dict[str, set] = defaultdict(set)
    if not EBIBLE_CSV.exists():
        return lang_sources

    with open(EBIBLE_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            iso = row.get("languageCode", "")
            if not iso:
                continue
            if int(row.get("NTchapters") or 0) > 0:
                lang_sources[iso].add("nt")
            if int(row.get("OTchapters") or 0) > 0:
                lang_sources[iso].add("ot")
    return lang_sources


def load_contrib_sources() -> dict:
    """Per-canon contrib presence — local, git-tracked override directory,
    inherently live (no fetch step)."""
    lang_sources: dict[str, set] = defaultdict(set)
    if not CONTRIB_DIR.is_dir():
        return lang_sources
    for canon_dir in CONTRIB_DIR.iterdir():
        if not canon_dir.is_dir() or canon_dir.name not in ("nt", "ot"):
            continue
        for iso_dir in canon_dir.iterdir():
            if iso_dir.is_dir():
                lang_sources[iso_dir.name].add(canon_dir.name)
    return lang_sources


def count_timing_books(resolved: dict) -> dict[tuple[str, str, str], set[str]]:
    """Count books with real timing per (canon, iso, fileset), from
    timing_index.load_resolved() — bibles' own owned sources plus
    audio-sync's real work distilled from their manifests."""
    books_by_fileset: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for iso, filesets in resolved.items():
        for audio_fileset, books in filesets.items():
            for book in books:
                canon = "nt" if book in NT_BOOKS else "ot" if book in OT_BOOKS else None
                if canon:
                    books_by_fileset[(canon, iso, audio_fileset)].add(book)
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


def main():
    if not SORTED_DIR.is_dir():
        print(f"[ERROR] {SORTED_DIR} not found. Run: make sort-dbt-catalog")
        return

    print("[INFO] Loading resolved timing (owned sources + audio-sync manifest digest)...")
    resolved = load_resolved()
    align_sources = json.loads(ALIGN_SOURCES_FILE.read_text()) if ALIGN_SOURCES_FILE.exists() else {}

    print("[INFO] Counting timing books across all sources...")
    timing_books_map = count_timing_books(resolved)

    print("[INFO] Counting audio books from sorted metadata...")
    audio_books_set_map = count_audio_books()

    # Versification scheme per DBT fileset (iso/fileset -> scheme code)
    v11n = {}
    if V11N_INDEX.exists():
        v11n = json.loads(V11N_INDEX.read_text())

    print("[INFO] Discovering DBT filesets from internal-data/sorted/BB...")
    lang_filesets, dbt_has_audio = discover_dbt_filesets(v11n, resolved, align_sources)

    print("[INFO] Loading helloAO/eBible/contrib source presence...")
    lang_sources, lang_helloao = load_helloao_sources()
    ebible_sources = load_ebible_sources()
    contrib_sources = load_contrib_sources()

    for iso, canons in dbt_has_audio.items():
        for canon, present in canons.items():
            if present:
                lang_sources[iso][canon].add("dbt")
    for iso, canons in ebible_sources.items():
        for canon in canons:
            lang_sources[iso][canon].add("ebible")
    for iso, canons in contrib_sources.items():
        for canon in canons:
            lang_sources[iso][canon].add("contrib")

    # Union, not just lang_filesets: a language with only helloAO/eBible/
    # contrib presence and zero DBT filesets has no entry in sorted/BB at
    # all (DBT-only by construction), so discover_dbt_filesets() never
    # sees it — but it still needs a media.json (sources/h at minimum),
    # same as the old ALL-langs-based pipeline wrote for its ~985 pure-
    # helloAO/eBible synthetic entries.
    all_isos = set(lang_filesets) | set(lang_sources)

    # Write media.json per language (including text-only)
    files_written = 0
    for iso in sorted(all_isos):
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

    # Load language names: helloAO catalog -> DBS cache -> ALL-langs-compact
    # (last resort only). Reordered 2026-09-03: ALL-langs-compact.json used
    # to be checked FIRST, but it's a frozen, external, unmaintained
    # snapshot (bible-story-builder went private; see doc/catalog-langs.md)
    # — helloAO+DBS combined actually cover MORE languages than it does
    # (2996 vs 2165, verified), so preferring them first is a pure
    # improvement, not a tradeoff. The compact file is now optional and
    # only fills in the ~116 languages neither live source has; nothing
    # here breaks if it's absent.
    names = {}

    # helloAO catalog
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

    # DBS bible details cache — also carries a top-level `script` field
    # (e.g. "Arab", "Beng"), sibling to the nested `language` block; not
    # read before 2026-09-03, confirmed real and populated on inspection.
    # Two separate concerns here, deliberately not combined into one
    # "first source wins" pass: name resolution (fill only if no name yet)
    # vs script-code enrichment (fill for ANY entry missing `sc`,
    # regardless of which source supplied its name — a name found via
    # helloAO shouldn't forfeit a real script code DBS has for that iso).
    dbs_scripts = {}
    dbs_dir = API_CACHE / "dbs" / "bibles"
    if dbs_dir.is_dir():
        for p in sorted(dbs_dir.glob("*.json")):
            if p.name == "index.json":
                continue
            try:
                with open(p) as f:
                    d = json.load(f)
                iso = d.get("iso", "")
                script = d.get("script", "")
                if iso and script and iso not in dbs_scripts:
                    dbs_scripts[iso] = script
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

    for iso, script in dbs_scripts.items():
        if iso in names and "sc" not in names[iso]:
            names[iso]["sc"] = script

    # Last resort: frozen ALL-langs-compact.json, only for names neither
    # live source above has. Optional — this file may not exist at all.
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

    # Build media-index.json roll-up (compact: omit "m" when "", omit canon when empty)
    index = {}
    for iso in sorted(all_isos):
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
