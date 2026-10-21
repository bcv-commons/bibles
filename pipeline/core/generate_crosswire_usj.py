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
- its text is plain, or OSIS using only the elements osis_to_usfm() knows (any other element
  stops the module, so nothing is silently lost or leaked into verse text).
- its text is not one we already reach: its sample chapters (chapter 1 of the first Old
  Testament and first New Testament book) are compared, letters only, with every edition in
  the same language from helloAO, our openbible / audiobiblia / eBible USJ, and DBT's text.
  DUPLICATE_SCORE or more on every shared sample is the same text: skipped, and recorded in
  internal-data/api-cache/crosswire/duplicates.json, unless the module has more books than
  the edition it matches. Then it is written, with the match in _meta.json `same_text_as`
  (Wycliffe: helloAO eng_w88 has 9 of its 76 books).

Only the modules in MODULES are processed (a module's conf `Lang` doesn't always give the
iso we catalog it under, e.g. `el` -> ell, `mlf` for Malayalam). NOT_YET lists modules
looked at and left out, with the reason.

OSIS -> USFM (osis_to_usfm), per verse as pysword returns it (clean=False):
- paragraph milestones (div type x-p / paragraph, sID) -> \\p; poetry lines (l sID, level N)
  -> \\qN; a selah line (l type=selah) -> \\qs ... \\qs*. A marker before the verse's first
  text goes before its \\v.
- title type=psalm -> \\d; type=acrostic -> \\qa; other titles -> \\s1. A testament heading
  (type=main, e.g. SloStritar's "Nova zaveza") belongs to no book and is dropped.
- note -> \\f + \\ft ... \\f*; type=crossReference -> \\x - \\xt ... \\x*. Markup inside a note
  is flattened to its text.
- transChange type=added -> \\add ... \\add*; q who=Jesus -> \\wj ... \\wj*; hi bold / italic
  -> \\bd / \\it.
- milestone type=x-versemarker (a further verse inside a slot, in the edition's own
  numbering: vlsJoNT John 1:52) -> its own \\v.
- Dropped: colophons (div type=colophon; no USFM paragraph keeps them out of verse text),
  hi type=super (CSlElizabeth's LXX sub-verse numbers, "1 ... 2 ..."), and structural
  milestones (book, chapter, section ends, preverse wrappers, lg).
A module without markup gets one paragraph per chapter.

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
from edition_formats import FORMATS, USJ_ONLY, write_meta  # noqa: E402
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
MODULES = {
    "GreVamvas": "ell",
    # 2026-10-21: languages we had no text for
    "ArmEastern": "hye", "ArmWestern": "hyw", "LvGluck8": "lvs", "SloStritar": "slv", "KswSKMB": "ksw",
    "Peshitta": "syc", "CSlElizabeth": "chu", "Wycliffe": "enm", "ScotsGaelic": "gla", "ManxGaelic": "glv",
    "PotLykins": "pot", "Calo": "rmq", "vlsJoNT": "vls", "KLV": "tlh",
    # Middle English (c.1395), filed under eng with helloAO's eng_w88 (same text, 9 books),
    # so clients find it with the English editions (decided 2026-10-21)
    "Wycliffe": "eng",
}
LANGUAGE_NOTE = {"Wycliffe": "Middle English (ISO 639-3 enm), catalogued under eng"}
# Published as USJ only (no Sofria): proskomma, which builds the Sofria, cuts a "word" at 255
# bytes, and these scripts write phrases without spaces. Found by route parity, 2026-10-21.
USJ_ONLY_MODULES = {
    "KswSKMB": "S'gaw Karen phrases have no spaces: 491 chapters lost letters in Sofria "
               "(1CH 1:43: two vowel and tone marks before the full stop)",
}
NOT_YET = {
    "Wulfila": "several manuscript readings per verse (seg type=rdg) and editorial <...> brackets "
               "written into the text: no single text without choosing a manuscript",
}

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
    "Tob": "TOB", "Jdt": "JDT", "Wis": "WIS", "Sir": "SIR", "Bar": "BAR", "EpJer": "LJE", "1Macc": "1MA",
    "2Macc": "2MA", "1Esd": "1ES", "PrMan": "MAN", "EpLao": "LAO",
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
    """{BOOK: {chapter: {verse: raw OSIS fragment}}}, empty verses left out."""
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
                    if raw.strip():
                        verses[v] = raw
                if verses:
                    chapters[c] = verses
            if chapters:
                books[OSIS_TO_USFM[bk.osis_name]] = chapters
    return books


TOKEN = re.compile(r"<(/?)(\w+)((?:\s+[\w:]+=\"[^\"]*\")*)\s*(/?)>|([^<]+)")
PARA_DIVS = {"x-p", "paragraph"}
CHAR = {("transChange", "added"): "add", ("hi", "bold"): "bd", ("hi", "italic"): "it"}
IGNORED_MILESTONES = {"div", "chapter", "lg", "verse"}


class Unsupported(Exception):
    pass


def osis_to_usfm(chapters: dict, where: str) -> str:
    """One book's chapters ({chapter: {verse: OSIS fragment}}) as USFM (after \\id)."""
    import html
    lines = []
    for c, verses in chapters.items():
        lines.append(f"\\c {c}")
        para = None        # the open paragraph marker
        need_para = False  # a heading closed it: resume it before the next verse text
        for v, raw in verses.items():
            pieces, has_v = [], False

            def body(piece):
                """Verse content: \\v goes in front of the first piece of it."""
                nonlocal has_v
                if para is None or need_para:
                    set_para(para or "\\p")
                if not has_v:
                    pieces.append(f"\n\\v {v} ")
                    has_v = True
                pieces.append(piece)

            def set_para(m):
                nonlocal para, need_para
                para, need_para = m, False
                pieces.append(f"\n{m}\n")

            stack = []  # open elements: (name, closing USFM, text kept, is a heading)
            for close, name, attrs, selfclose, text in TOKEN.findall(raw):
                if text:
                    t = html.unescape(text)
                    if not all(keep for _, _, keep, _ in stack):
                        continue
                    if any(h for *_, h in stack):
                        pieces.append(t)  # heading text
                    elif t.strip() or has_v:
                        body(t)
                    continue
                at = dict(re.findall(r'([\w:]+)="([^"]*)"', attrs))
                typ = at.get("type", "")
                if close:
                    if not stack or stack[-1][0] != name:
                        raise Unsupported(f"{where} {c}:{v}: unbalanced </{name}>")
                    _, end, keep, heading = stack.pop()
                    if heading and keep:
                        pieces.append("\n")
                        need_para = True
                    elif end:
                        pieces.append(end)
                    continue
                if selfclose or "sID" in at or "eID" in at:
                    if "eID" in at:
                        if name == "l" and typ == "selah":
                            pieces.append("\\qs*")
                        elif name == "div" and typ == "colophon":
                            stack = [x for x in stack if x[0] != "colophon"]
                    elif name == "div" and typ in PARA_DIVS:
                        set_para("\\p")
                    elif name == "l" and typ == "selah":
                        body("\\qs ")
                    elif name == "l":
                        set_para(f"\\q{at.get('level', '1')}")
                    elif name == "div" and typ == "colophon":
                        stack.append(("colophon", None, False, False))
                    elif name == "milestone" and typ == "x-versemarker":
                        if int(at.get("cnum", c)) == c:
                            body(f"\n\\v {at['vnum']} ")
                    elif name not in IGNORED_MILESTONES and name != "milestone":
                        raise Unsupported(f"{where} {c}:{v}: <{name} {typ}/>")
                    continue
                if any(x[0] == "note" for x in stack):
                    stack.append((name, None, True, False))  # flattened inside a note
                elif name == "title":
                    keep = typ != "main"
                    if keep:
                        pieces.append("\n" + {"psalm": "\\d", "acrostic": "\\qa"}.get(typ, "\\s1") + " ")
                    stack.append(("title", None, keep, True))
                elif name == "note":
                    x = typ == "crossReference"
                    body("\\x - \\xt " if x else "\\f + \\ft ")
                    stack.append(("note", "\\x*" if x else "\\f*", True, False))
                elif (name, typ) in CHAR:
                    u = CHAR[(name, typ)]
                    body(f"\\{u} ")
                    stack.append((name, f"\\{u}*", True, False))
                elif name == "q" and at.get("who") == "Jesus":
                    body("\\wj ")
                    stack.append((name, "\\wj*", True, False))
                elif name == "hi" and typ == "super":
                    stack.append((name, None, False, False))
                elif name in ("foreign", "transChange", "q", "reference"):
                    stack.append((name, None, True, False))
                else:
                    raise Unsupported(f"{where} {c}:{v}: <{name} {typ}>")
            if stack:
                raise Unsupported(f"{where} {c}:{v}: unclosed {[x[0] for x in stack]}")
            lines.append("".join(pieces))
    body_text = "\n".join(lines)
    body_text = re.sub(r"[ \t]*\n[ \t]*", "\n", body_text)
    body_text = re.sub(r"\n(\\(?:p|q\d))\n(?=\\(?:p|q\d|d|s1|qa)\b)", "\n", body_text)  # a marker with nothing in it
    return re.sub(r"\n{2,}", "\n", body_text).strip() + "\n"


def to_usfm(book: str, chapters: dict) -> str:
    return f"\\id {book}\n" + osis_to_usfm(chapters, book)


def dbt_chapter(fileset: str, book: str, chapter: str) -> list | None:
    import download_language_content as dl
    r = dl.get_text_content(fileset, book, int(chapter))
    if not r or r.get("type") != "verses":
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "verse-text" / "python"))
    from plain_text import extract_plain
    return extract_plain(r["data"])


def edition_books(source: str, edition: str, iso: str) -> set:
    """The books an edition we compared with has (helloAO books.json, our _meta.json)."""
    if source == "helloao":
        f = DOWNLOADS / "helloao" / edition / "books.json"
        if not f.exists():
            body = eb.http_get(f"{eb.HELLOAO_API}/{edition}/books.json")
            if body is None:
                return set()
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(body)
        return {b["id"] for b in json.loads(f.read_text())["books"]}
    meta = EXPORT / f"{source}-usj" / iso / edition / "_meta.json"
    return set(json.loads(meta.read_text()).get("books", [])) if meta.exists() else set()


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
    try:
        usfm = {b: to_usfm(b, chs) for b, chs in books.items()}
    except Unsupported as e:
        print(f"[crosswire] {module}: skipped, markup not supported yet: {e}")
        return
    usj = {b: eb.convert_book(u) for b, u in usfm.items()}
    samples = {}
    for order in (eb.OT_FIRST, eb.NT_FIRST):
        b = next((x for x in order if x in usj), None)
        if b:
            samples[(b, "1")] = eb.letters(extract_usj(usj[b])["1"])
    dup, compared = find_duplicate(iso, samples)
    print(f"[crosswire] {module}: compared with {len(compared)} editions: " +
          ", ".join(f"{c['source']}:{c['edition']} {min(c['scores'].values()) if c['scores'] else '-'}" for c in compared))
    if dup and dup["source"] != "dbt":
        theirs = edition_books(dup["source"], dup["edition"], iso)
        if len(theirs) < len(usj):
            dup["books"] = len(theirs)
            print(f"[crosswire] {module}: same text as {dup['source']}:{dup['edition']}, which has only "
                  f"{len(theirs)} of its {len(usj)} books: written")
            same_text_as, dup = dup, None
    else:
        same_text_as = None
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
    if module in LANGUAGE_NOTE:
        meta["language_note"] = LANGUAGE_NOTE[module]
    if same_text_as:
        meta["same_text_as"] = {"edition": f"{same_text_as['source']}:{same_text_as['edition']}",
                                "books": same_text_as["books"], "scores": same_text_as["scores"]}
    write_meta(out, meta, USJ_ONLY if module in USJ_ONLY_MODULES else FORMATS)
    nv = sum(len(vs) for chs in books.values() for vs in chs.values())
    print(f"[crosswire] {module}: wrote {len(usj)} books, {nv} verses -> {out}")


def main():
    args = sys.argv[1:]
    only = args[args.index("--module") + 1] if "--module" in args else None
    for module, why in NOT_YET.items():
        if only in (None, module):
            print(f"[crosswire] {module}: not processed: {why}")
    for module, iso in MODULES.items():
        if only in (None, module):
            process(module, iso, "--force" in args)


if __name__ == "__main__":
    main()
