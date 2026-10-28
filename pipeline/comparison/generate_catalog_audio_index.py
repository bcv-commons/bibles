#!/usr/bin/env python3
"""Publish a thin, source-agnostic audio-existence index — the audio
counterpart to catalog-index.json (which is text-only; see its own
docstring). Answers one question: "does source X have real audio for this
(iso, canon)" — nothing about routing, bitrate, narrators, or timing detail,
which stay in each source's own richer structure (catalog-audio.json for
DBT's fileset routing, /dbt/<iso>/media.json for confirmed timing).

Built 2026-08-14, prompted by a client request to catalog a helloAO audio
edition (BSB) that had nowhere to go — catalog-audio.json is deliberately
DBT-only (every id in it round-trips against DBT's raw catalog; a non-DBT
id has no business there). See internal-docs/catalog-audio-ownership-
architecture.md §8 for the full scoping notes.

Row shape: [iso, canon_tag, source, count?] — deliberately identical
convention to catalog-index.json (canon_tag reuses nt/ntp/ot/otp, source is
d/p/h, count omitted when exactly 1) so a client already parsing that file
can reuse the same code path here with zero new logic.

Per-source population, as of this build:
  - DBT: real, broad — every (iso, canon) with >=1 version carrying an
    `a:`/`A:` audio tag in DBT's own raw catalog. No external-pointer
    concern here the way catalog-index.json's text rows have (DBT audio
    tags always reference DBT's own fileset, never another source) —
    confirmed by inspecting the tag format, no `a:helloao:...`/`a:ebible:...`
    pattern exists the way `t:helloao:...` does for text.
  - helloAO: real, but tiny and curated (data/helloao-audio.toml) — helloAO's
    catalog has no audio-existence field, so this can't be derived the way
    DBT's can; each entry was hand-verified against a live per-chapter
    response, not guessed from a translation name.
  - PKF (since 2026-10-28): PKF's own audio, the audio PKF's apps get from
    scriptureearth.org and elsewhere, not DBT's (internal-data/pkf-audio-index.json,
    fetch_pkf_audio_index.py, which checks each source answers). Book-level. The DBT
    audio PKF's apps stream is DBT's, already counted under `d`.
  - openbible (Biblica's Open Bible catalog, added 2026-09-16): real,
    book-level — fetch_openbible_cache.py's phase 2 already confirms real
    per-book audio coverage per version (`audioBooks`), not just a claimed
    `type: "audio"` — same NT/OT/Portions classification logic as DBT's own
    rows, applied to the CURRENT version's real book list.
  - audiobiblia (`o`, added 2026-10-27): editions we republish with their audio
    (BLL, mirror_audiobiblia_audio.py), from `formats.audio.books` in the edition's
    _meta.json. The edition's own _meta.json gives the path.

Usage:
    python3 pipeline/comparison/generate_catalog_audio_index.py [--out PATH]
"""
import glob
import json
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, CATALOG_DIR, EXPORT, HELLOAO_AUDIO_FILE, INTERNAL_DATA  # noqa: E402

DBT_CATALOG_URL = "https://cdn.bibel.wiki/dbt/_catalog.json"
PKF_MANIFEST_URL = "https://cdn.bibel.wiki/pkf/manifest.json"
PKF_AUDIO_INDEX = INTERNAL_DATA / "pkf-audio-index.json"
HELLOAO_CATALOG_URL = "https://bible.helloao.org/api/available_translations.json"
OPENBIBLE_PROJECTS_URL = "https://openbible-api-1.biblica.com/projects"

OT_BOOKS = {"GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA", "1KI", "2KI",
            "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO", "ECC", "SNG", "ISA", "JER",
            "LAM", "EZK", "DAN", "HOS", "JOL", "AMO", "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL"}
NT_BOOKS = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL",
            "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"}


def dbt_rows():
    catalog = json.loads((API_CACHE / "dbt-catalog.json").read_text())
    counts = defaultdict(int)
    for row in catalog["versions"]:
        iso, canon = row[0], row[2]
        audio_spec = next((f for f in row[3:] if f.split(":", 1)[0] in ("a", "A")), None)
        if not audio_spec:
            continue
        counts[(iso, canon, "d")] += 1
    return counts


def helloao_rows():
    counts = defaultdict(int)
    if not HELLOAO_AUDIO_FILE.exists():
        return counts
    data = tomllib.loads(HELLOAO_AUDIO_FILE.read_text())
    for edition in data.get("edition", []):
        iso = edition["iso"]
        for canon in edition["canons"]:
            counts[(iso, canon, "h")] += 1
    return counts


def pkf_rows():
    counts = defaultdict(int)
    if not PKF_AUDIO_INDEX.exists():
        return counts
    for iso, own in json.loads(PKF_AUDIO_INDEX.read_text()).get("own", {}).items():
        canon_counts(iso, set(own["audio"]), "p", counts)
    return counts


def openbible_rows():
    counts = defaultdict(int)
    for f in glob.glob(str(API_CACHE / "openbible" / "audio" / "*.json")):
        d = json.loads(Path(f).read_text())
        iso = d["project"].get("languageCode")
        if not iso:
            continue
        for v in d.get("versions", []):
            if not v.get("current"):
                continue
            books = set(v.get("audioBooks") or [])
            if books:
                canon_counts(iso, books, "o", counts)
    return counts


def canon_counts(iso: str, books: set, source: str, counts: dict) -> None:
    if NT_BOOKS.issubset(books):
        counts[(iso, "nt", source)] += 1
    elif books & NT_BOOKS:
        counts[(iso, "ntp", source)] += 1
    if OT_BOOKS.issubset(books):
        counts[(iso, "ot", source)] += 1
    elif books & OT_BOOKS:
        counts[(iso, "otp", source)] += 1


def audiobiblia_rows():
    counts = defaultdict(int)
    for f in glob.glob(str(EXPORT / "audiobiblia-usj" / "*" / "*" / "_meta.json")):
        audio = json.loads(Path(f).read_text(encoding="utf-8")).get("formats", {}).get("audio")
        if audio:
            canon_counts(Path(f).parent.parent.name, set(audio["books"]), "o", counts)
    return counts


def main():
    args = sys.argv[1:]
    out_path = Path(args[args.index("--out") + 1]) if "--out" in args else CATALOG_DIR / "audio-index.json"

    all_counts = defaultdict(int)
    for counts in (dbt_rows(), pkf_rows(), helloao_rows(), openbible_rows(), audiobiblia_rows()):
        for k, v in counts.items():
            all_counts[k] += v

    entries = []
    for (iso, canon, source), count in sorted(all_counts.items()):
        row = [iso, canon, source]
        if count > 1:
            row.append(count)
        entries.append(row)

    output = {
        "schema_version": 1,
        "generated_at": None,
        "sources": [{"d": DBT_CATALOG_URL}, {"p": PKF_MANIFEST_URL}, {"h": HELLOAO_CATALOG_URL},
                    {"o": OPENBIBLE_PROJECTS_URL}],
        "entries": entries,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"[generate-catalog-audio-index] {len(entries)} entries -> {out_path}")


if __name__ == "__main__":
    main()
