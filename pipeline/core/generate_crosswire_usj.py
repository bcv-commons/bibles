#!/usr/bin/env python3
"""Generate export/crosswire-usj/<iso>/<module>/<BOOK>.json — book-level USJ from CrossWire
SWORD modules — plus each edition's _meta.json (see edition_formats.py). Chapter-level
Sofria is the downstream step (tools/usj-to-sofria/convert_batch.mjs), as for openbible.

Source: CrossWire's main module repository (https://www.crosswire.org/sword/modules/). Its
module list, mods.d.tar.gz, has one .conf per module; a module's data is a zip under
packages/rawzip/. Both are cached under internal-data/downloads/crosswire/. Modules are read
with pysword (pure Python; no SWORD library needed).

A module is written only if:
- its conf's DistributionLicense is one we can republish under: Public Domain, or a Creative
  Commons licence without NC or ND (CC0, BY, BY-SA). CrossWire's "permission granted to
  CrossWire" and non-commercial licences are not republishable.
- its text is plain, without markup (no `<` in any verse). Modules with OSIS/ThML/GBF markup
  (notes, Strong's numbers, headings) need a markup-aware conversion, not written yet.
- its text is not one we already reach: its sample chapters (chapter 1 of the first Old
  Testament and first New Testament book) are compared, letters only, with every edition in
  the same language from helloAO, our openbible / audiobiblia / eBible USJ, and DBT's text.
  DUPLICATE_SCORE or more on every shared sample is the same text: skipped, and recorded in
  internal-data/api-cache/crosswire/duplicates.json.

Only the modules in MODULES are processed (a module's conf `Lang` doesn't always give the
iso we catalog it under, e.g. `el` -> ell, `mlf` for Malayalam). The text carries no
paragraph structure: each chapter is one paragraph, every verse a \\v.

Usage:
    python3 generate_crosswire_usj.py [--force] [--module NAME]
"""
import io
import json
import re
import sys
import tarfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_ebible_chapters as eb  # noqa: E402  (shared conversion and comparison helpers)
from edition_formats import write_meta  # noqa: E402
from verse_text import extract_usj  # noqa: E402  (on sys.path via generate_ebible_chapters)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, DOWNLOADS, EXPORT  # noqa: E402

REPO = "https://www.crosswire.org/ftpmirror/pub/sword"
CACHE = DOWNLOADS / "crosswire"
DUPLICATES_FILE = API_CACHE / "crosswire" / "duplicates.json"
USJ_OUT_DIR = EXPORT / "crosswire-usj"
DBT_CATALOG = API_CACHE / "dbt-catalog.json"
OWN_USJ = [EXPORT / "openbible-usj", EXPORT / "audiobiblia-usj", EXPORT / "ebible-usj"]

# module -> the iso we catalog it under
MODULES = {"GreVamvas": "ell"}

OSIS_TO_USFM = {
    "Gen": "GEN", "Exod": "EXO", "Lev": "LEV", "Num": "NUM", "Deut": "DEU", "Josh": "JOS", "Judg": "JDG",
    "Ruth": "RUT", "1Sam": "1SA", "2Sam": "2SA", "1Kgs": "1KI", "2Kgs": "2KI", "1Chr": "1CH", "2Chr": "2CH",
    "Ezra": "EZR", "Neh": "NEH", "Esth": "EST", "Job": "JOB", "Ps": "PSA", "Prov": "PRO", "Eccl": "ECC",
    "Song": "SNG", "Isa": "ISA", "Jer": "JER", "Lam": "LAM", "Ezek": "EZK", "Dan": "DAN", "Hos": "HOS",
    "Joel": "JOL", "Amos": "AMO", "Obad": "OBA", "Jonah": "JON", "Mic": "MIC", "Nah": "NAM", "Hab": "HAB",
    "Zeph": "ZEP", "Hag": "HAG", "Zech": "ZEC", "Mal": "MAL",
    "Matt": "MAT", "Mark": "MRK", "Luke": "LUK", "John": "JHN", "Acts": "ACT", "Rom": "ROM", "1Cor": "1CO",
    "2Cor": "2CO", "Gal": "GAL", "Eph": "EPH", "Phil": "PHP", "Col": "COL", "1Thess": "1TH", "2Thess": "2TH",
    "1Tim": "1TI", "2Tim": "2TI", "Titus": "TIT", "Phlm": "PHM", "Heb": "HEB", "Jas": "JAS", "1Pet": "1PE",
    "2Pet": "2PE", "1John": "1JN", "2John": "2JN", "3John": "3JN", "Jude": "JUD", "Rev": "REV",
}


def conf_of(module: str) -> dict:
    """The module's conf from mods.d.tar.gz, as {key: value} (the last value of a repeated key)."""
    tgz = CACHE / "mods.d.tar.gz"
    if not tgz.exists():
        body = eb.http_get(f"{REPO}/raw/mods.d.tar.gz")
        if body is None:
            raise SystemExit("[crosswire] could not download mods.d.tar.gz")
        CACHE.mkdir(parents=True, exist_ok=True)
        tgz.write_bytes(body)
    with tarfile.open(tgz) as t:
        member = next((m for m in t.getmembers() if m.name.lower().endswith(f"/{module.lower()}.conf")), None)
        if member is None:
            raise SystemExit(f"[crosswire] no conf for {module}")
        text = t.extractfile(member).read().decode("utf-8", "replace")
    return dict(re.findall(r"^(\w+)=(.*?)\s*$", text, re.M))


def licence(conf: dict) -> tuple[dict | None, str]:
    lic = conf.get("DistributionLicense", "")
    if lic.lower() == "public domain":
        return {"type": "Public Domain"}, "public domain"
    m = re.match(r"Creative Commons:?\s*(.*)", lic, re.I)
    if m and not re.search(r"\b(NC|ND)\b", m.group(1), re.I):
        return {"type": f"CC {m.group(1).upper()}".replace("CC CC0", "CC0")}, lic
    return None, f"licence not republishable: {lic or 'none given'}"


def fetch_module(module: str) -> Path:
    """The module unpacked under the cache (a SWORD library root with mods.d/ and modules/)."""
    root = CACHE / "lib" / module
    if not (root / "mods.d").exists():
        body = eb.http_get(f"{REPO}/packages/rawzip/{module}.zip")
        if body is None:
            raise SystemExit(f"[crosswire] could not download {module}.zip")
        zipfile.ZipFile(io.BytesIO(body)).extractall(root)
    return root


def read_books(root: Path, module: str) -> dict:
    """{BOOK: {chapter: {verse: text}}}, empty verses left out. Raises on markup."""
    from pysword.modules import SwordModules
    mods = SwordModules(str(root))
    mods.parse_modules()
    bible = mods.get_bible_from_module(module)
    books = {}
    for testament in bible.get_structure().get_books().values():
        for bk in testament:
            chapters = {}
            for c in range(1, bk.num_chapters + 1):
                verses = {}
                for v in range(1, bk.chapter_lengths[c - 1] + 1):
                    raw = bible.get(books=[bk.osis_name], chapters=[c], verses=[v], clean=False)
                    if "<" in raw:
                        raise SystemExit(f"[crosswire] {module} has markup ({bk.osis_name} {c}:{v}); not supported yet")
                    if raw.strip():
                        verses[v] = " ".join(raw.split())
                if verses:
                    chapters[c] = verses
            if chapters:
                books[OSIS_TO_USFM[bk.osis_name]] = chapters
    return books


def to_usfm(book: str, chapters: dict) -> str:
    lines = [f"\\id {book}"]
    for c, verses in chapters.items():
        lines += [f"\\c {c}", "\\p"] + [f"\\v {v} {t}" for v, t in verses.items()]
    return "\n".join(lines) + "\n"


def dbt_chapter(fileset: str, book: str, chapter: str) -> list | None:
    import download_language_content as dl
    r = dl.get_text_content(fileset, book, int(chapter))
    if not r or r.get("type") != "verses":
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "verse-text" / "python"))
    from plain_text import extract_plain
    return extract_plain(r["data"])


def find_duplicate(iso: str, samples: dict) -> tuple[dict | None, list]:
    """(the first reachable edition matching every shared sample, or None; every comparison)."""
    others = [("helloao", t["id"]) for t in eb.helloao_translations() if t.get("language") == iso]
    for root in OWN_USJ:
        others += [(root.name.replace("-usj", ""), str(d)) for d in sorted((root / iso).glob("*")) if d.is_dir()]
    for row in json.loads(DBT_CATALOG.read_text())["versions"]:
        if row[0] == iso:
            for f in row[3:]:
                kind, _, rest = f.partition(":")
                if kind in ("t", "T") and not rest.startswith(("helloao:", "ebible:")):
                    others.append(("dbt", rest if kind == "T" else row[1] + rest))
    seen, compared = set(), []
    for source, ref in others:
        if (source, ref) in seen:
            continue
        seen.add((source, ref))
        scores = {}
        for (book, chapter), text in samples.items():
            if source == "helloao":
                theirs = eb.helloao_chapter(ref, book, chapter)
            elif source == "dbt":
                theirs = dbt_chapter(ref, book, chapter)
            else:
                theirs = eb.own_chapter(Path(ref), book, chapter)
            if theirs:
                scores[f"{book} {chapter}"] = round(eb.similarity(text, eb.letters(theirs)), 3)
        name = ref if source in ("helloao", "dbt") else Path(ref).name
        compared.append({"source": source, "edition": name, "scores": scores})
        if scores and min(scores.values()) >= eb.DUPLICATE_SCORE:
            return compared[-1], compared
    return None, compared


def process(module: str, iso: str, force: bool) -> None:
    out = USJ_OUT_DIR / iso / module
    if out.exists() and not force:
        print(f"[crosswire] {module}: already written (--force redoes it)")
        return
    conf = conf_of(module)
    lic, why = licence(conf)
    if lic is None:
        print(f"[crosswire] {module}: skipped, {why}")
        return
    books = read_books(fetch_module(module), module)
    usj = {b: eb.convert_book(to_usfm(b, chs)) for b, chs in books.items()}
    samples = {}
    for order in (eb.OT_FIRST, eb.NT_FIRST):
        b = next((x for x in order if x in usj), None)
        if b:
            samples[(b, "1")] = eb.letters(extract_usj(usj[b])["1"])
    dup, compared = find_duplicate(iso, samples)
    print(f"[crosswire] {module}: compared with {len(compared)} editions: " +
          ", ".join(f"{c['source']}:{c['edition']} {min(c['scores'].values()) if c['scores'] else '-'}" for c in compared))
    if dup:
        DUPLICATES_FILE.parent.mkdir(parents=True, exist_ok=True)
        known = json.loads(DUPLICATES_FILE.read_text()) if DUPLICATES_FILE.exists() else {}
        known[module] = dup
        DUPLICATES_FILE.write_text(json.dumps(known, indent=1, ensure_ascii=False))
        print(f"[crosswire] {module}: skipped, same text as {dup['source']}:{dup['edition']} {dup['scores']}")
        return
    out.mkdir(parents=True, exist_ok=True)
    for b, doc in usj.items():
        (out / f"{b}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    meta = {
        "name": conf.get("Description"),
        "licenses": [lic],
        "provider": "CrossWire Bible Society",
        "source": f"https://www.crosswire.org/sword/modules/ModInfo.jsp?modName={module}",
        "sword_module": {"name": module, "version": conf.get("Version"), "versification": conf.get("Versification", "KJV"),
                         "text_source": conf.get("TextSource")},
    }
    write_meta(out, meta)
    nv = sum(len(vs) for chs in books.values() for vs in chs.values())
    print(f"[crosswire] {module}: wrote {len(usj)} books, {nv} verses -> {out}")


def main():
    args = sys.argv[1:]
    only = args[args.index("--module") + 1] if "--module" in args else None
    for module, iso in MODULES.items():
        if only in (None, module):
            process(module, iso, "--force" in args)


if __name__ == "__main__":
    main()
