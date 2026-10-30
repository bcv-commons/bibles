#!/usr/bin/env python3
"""Script, direction, word spacing and Unicode normalization per edition (bcv-commons/bibles
issue #2, asked by bsb-add-books, now make-tanakh, and lexeme-aligner, 2026-10-26). Folded into
catalog/edition-struct.json by edition_struct.py; see doc/catalog-edition-struct.md.

Every edition with a text route (catalog/text-route.json) is read from text we already cache,
and the script is detected from its letters; the source's own metadata only refines that
(Hans/Hant for Han, Aran for Arab) or stands in where we have no text. The text decides
because the metadata is wrong too often to go first (2026-10-26): DBT labels its ESV Shavian,
a Georgian NT Cyrillic and a Kayah Li NT Latin, and swaps Latin and Cyrillic between two
Romani editions; eBible gives eight Latin editions as right to left; helloAO states no script
at all.

Text read per source (one or more chapters; script and normalization don't need more):
- d: DBT samples (internal-data/text/BB, one verse per line). Editions with none yet get one
  chapter fetched through their text route (plain, Sofria or USX) and saved there in the same
  layout.
- h: helloAO chapter JSON (internal-data/downloads/helloao/<id>/), the same files the
  versification and comparison steps fetched; an edition with none gets its first chapter.
- p: the cached PKF collection (api-cache/pkf), decoded into a temporary directory that is
  deleted straight after (PKF text is never kept; only this verdict is published).
- o, e, c, g: every book of our own USJ under export/. Its normalization is the source's: on
  every openbible edition, the USFM zip and our USJ have the same normalization (2026-10-26).

Detection: each letter (Unicode category L) is given its script by ICU (PyICU). Common and
inherited letters (ʼ, ꞌ and other modifier letters) are not counted. Hiragana or Katakana make
Jpan, Hangul makes Kore; otherwise the script with the most letters. Any other script with at
least 1% of the letters is listed in `scripts`.

Normalization is over the same text: NFC if it equals its NFC form and not its NFD form, NFD
the other way round, `mixed` if it equals neither (or files differ), and NFC if no character in
it has a decomposition at all (it is then both, and NFC is what a tool would write).

Output: internal-data/comparison-results/edition-script.json, the letter counts and
normalization per edition. Resumable: an edition already read is not read again unless
--force; one without text (null) is tried again.

Usage:
    python3 pipeline/comparison/edition_script.py [--force] [--source d|h|p|o|e|c|g] [--jobs N]
"""
import csv
import glob
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import icu
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import (API_CACHE, CATALOG_DIR, COMPARISON_RESULTS_DIR, DOWNLOADS, EXPORT,  # noqa: E402
                   OPENBIBLE_EDITIONS_FILE, REPO_ROOT, TEXT_DIR)
sys.path.insert(0, str(REPO_ROOT / "pipeline" / "core"))
import download_language_content as dl  # noqa: E402
sys.path.insert(0, str(REPO_ROOT / "tools" / "verse-text" / "python"))
from verse_text import extract_sofria, extract_usj  # noqa: E402

OUT = COMPARISON_RESULTS_DIR / "edition-script.json"
TEXT_ROUTE_FILE = CATALOG_DIR / "text-route.json"
SAMPLE_DIR = TEXT_DIR / "BB"
HELLOAO_DL = DOWNLOADS / "helloao"
HELLOAO_API = "https://bible.helloao.org/api"
PKF_CACHE = API_CACHE / "pkf"
PKF_DECODE = REPO_ROOT / "tools" / "pkf-decode" / "decode.mjs"
OWN_USJ = {"openbible": "openbible-usj", "audiobiblia": "audiobiblia-usj", "ebible": "ebible-usj",
           "crosswire": "crosswire-usj", "door43": "door43-usj"}
NT_FIRST = ["REV", "MRK", "LUK", "JHN", "MAT", "ACT", "ROM"]
NT_BOOKS = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL", "1TH", "2TH",
            "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"}

NEUTRAL = {"Zyyy", "Zinh", "Zzzz"}
MINOR_SHARE = 0.01
# Right-to-left scripts (Unicode bidi class R or AL for their letters).
RTL = {"Arab", "Aran", "Hebr", "Syrc", "Thaa", "Nkoo", "Adlm", "Samr", "Mand", "Rohg", "Yezi", "Mend",
       "Armi", "Avst", "Chrs", "Elym", "Hatr", "Khar", "Lydi", "Mani", "Narb", "Nbat", "Ougr", "Palm",
       "Phli", "Phlp", "Phnx", "Prti", "Sarb", "Sogd", "Sogo", "Hung", "Orkh"}
# Scripts written without spaces between words; the tokenizer cuts Han per character, Myanmar
# per syllable, and Thai, Lao and Khmer only where the text has a zero-width space.
NO_SPACES = {"Hani", "Hans", "Hant", "Jpan", "Thai", "Laoo", "Khmr", "Mymr", "Tibt", "Lana", "Talu",
             "Tavt", "Bali", "Java"}
# Script names in source metadata that ICU doesn't resolve (eBible translations.csv, openbible).
NAMES = {"han (traditional variant)": "Hant", "han (simplified variant)": "Hans", "cjk": "Hani",
         "roman": "Latn", "amheric": "Ethi", "hindi": "Deva", "nepali": "Deva", "burmese": "Mymr",
         "tifenagh": "Tfng", "unified canadian aboriginal syllabics": "Cans", "arabic (nastaliq variant)": "Aran", "tai tham (lanna)": "Lana",
         "code for uncoded script": None, "code for undetermined script": None,
         "code for inherited script": None}


def script_code(name: str | None) -> str | None:
    """A metadata script value (ISO 15924 code or English name) -> ISO 15924 code, or None."""
    if not name:
        return None
    if re.fullmatch(r"[A-Z][a-z]{3}", name):
        return name
    key = name.strip().lower()
    if key in NAMES:
        return NAMES[key]
    for n in (name, re.sub(r"\s*\(.*", "", name)):
        try:
            codes = icu.Script.getCode(n)
        except icu.ICUError:
            continue
        if codes:
            return icu.Script(codes[0]).getShortName()
    return None


def letters(text: str) -> Counter:
    c = Counter()
    for ch in text:
        if unicodedata.category(ch)[0] == "L":
            c[icu.Script.getScript(ch).getShortName()] += 1
    return c


def normalization(text: str) -> str:
    nfc, nfd = unicodedata.normalize("NFC", text), unicodedata.normalize("NFD", text)
    if text == nfc:
        return "none" if text == nfd else "NFC"
    return "NFD" if text == nfd else "mixed"


def usfm_text(usfm: str) -> str:
    """Rough verse text from USFM, for counting letters only: notes, attributes and markers out."""
    usfm = re.sub(r"\\(f|fe|x)\s.*?\\\1\*", " ", usfm, flags=re.S)
    usfm = re.sub(r"\|[^\\]*", "", usfm)
    usfm = re.sub(r"^\\(id|h|toc\d|mt\d?|ide|rem|s\d?|r|ms\d?|mr)\b.*$", "", usfm, flags=re.M)
    return re.sub(r"\\[a-z0-9-]+\*?", " ", usfm)


def helloao_strings(o, out: list) -> None:
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, list):
        for x in o:
            helloao_strings(x, out)
    elif isinstance(o, dict) and o.get("type") not in ("footnote", "heading", "hebrew_subtitle"):
        if "text" in o:
            helloao_strings(o["text"], out)
        if "content" in o:
            helloao_strings(o["content"], out)


# --- text per source -------------------------------------------------------------------------

def fileset_stem(fileset: str) -> str:
    """KBYWBTN_ET-json -> KBYWBT: the version part of a DBT fileset id."""
    return re.sub(r"(?:[NOP]\d?(?:_ET|DA))?(?:-json|-usx)?$", "", fileset)


def dbt_samples(iso: str, distinct_id: str, fileset: str) -> list[str]:
    """Sample files (<BOOK>_<ch>_<fileset>.txt) of this fileset only: a version's samples can come
    from a sibling fileset in another script (KBYWBT's are Arabic-script KBYWBAN_ET, its text
    route is the Latin KBYWBTN_ET-json)."""
    stem = fileset_stem(fileset)
    return sorted(f for f in glob.glob(str(SAMPLE_DIR / "*" / iso / distinct_id / "**" / "*.txt"), recursive=True)
                  if fileset_stem(Path(f).stem.split("_", 2)[2]) == stem)


def dbt_texts(iso: str, distinct_id: str, route: dict) -> list[str]:
    files = dbt_samples(iso, distinct_id, route["id"])
    if not files:
        fetch_dbt_sample(iso, distinct_id, route)
        files = dbt_samples(iso, distinct_id, route["id"])
    return [Path(f).read_text(encoding="utf-8") for f in files[:3]]


def fetch_dbt_sample(iso: str, distinct_id: str, route: dict) -> None:
    """One chapter through the edition's text route, saved as a sample (one verse per line)."""
    fileset = route.get("id")
    books_file = CATALOG_DIR / iso[0] / iso / "books.json"
    entry = json.loads(books_file.read_text())["entries"].get(f"d:{distinct_id}", {}) if books_file.is_file() else {}
    # books.json is per version; keep the books of this fileset's testament (N / O in its id)
    m = re.search(r"([NO])\d?(?:_ET|DA)", fileset or "")
    testament = {"N": "nt", "O": "ot"}.get(m.group(1)) if m else None
    cov = {b["code"]: b.get("ch") or [1] for b in entry.get("books", [])
           if b.get("c") and testament in (None, b.get("t"))}
    if not cov:
        return
    book = next((b for b in NT_FIRST if b in cov), next(iter(cov)))
    chapter = cov[book][0]
    result = dl.get_text_content(fileset, book, chapter)
    time.sleep(0.1)
    if not result:
        return
    if result["type"] == "verses":
        lines = [v.get("verse_text", "") for v in result["data"]]
    else:
        r = requests.get(result["data"], timeout=60)
        if r.status_code != 200:
            return
        if route["route"] == "sofria":
            lines = [v["text"] for v in extract_sofria(r.json())]
        else:
            lines = [usfm_text(re.sub(r"<[^>]+>", " ", r.text))]
    if not any(x.strip() for x in lines):
        return
    f = SAMPLE_DIR / ("nt" if book in NT_BOOKS else "ot") / iso / distinct_id / book / f"{book}_{chapter:03d}_{fileset}.txt"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")


def helloao_texts(tid: str) -> list[str]:
    files = sorted(glob.glob(str(HELLOAO_DL / tid / "*" / "*.json")))
    if not files:
        books = json.loads((HELLOAO_DL / tid / "books.json").read_text())["books"]
        b = next((x for x in books if x["id"] in NT_FIRST), books[0])
        ch = b.get("firstChapterNumber") or 1
        r = requests.get(f"{HELLOAO_API}/{tid}/{b['id']}/{ch}.json", timeout=30)
        time.sleep(0.1)
        if r.status_code != 200:
            return []
        f = HELLOAO_DL / tid / ("nt" if b["id"] in NT_BOOKS else "ot") / f"{b['id']}_{ch:03d}.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(r.content)
        files = [str(f)]
    out = []
    for f in files:
        parts: list = []
        helloao_strings(json.loads(Path(f).read_text(encoding="utf-8"))["chapter"]["content"], parts)
        out.append("\n".join(parts))
    return out


def pkf_texts(iso: str, pkf_file: str) -> list[str]:
    src = PKF_CACHE / iso / pkf_file
    if not src.is_file():
        return []
    tmp = Path(tempfile.mkdtemp(prefix="pkf-script-"))
    try:
        subprocess.run(["node", str(PKF_DECODE), str(src), "--out", str(tmp)],
                       capture_output=True, timeout=600, check=False)
        books = sorted(tmp.glob("*.usfm"))
        return [usfm_text(b.read_text(encoding="utf-8")) for b in books[:3]]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def own_texts(path: str) -> list[str]:
    kind, iso, edition = path.strip("/").split("/")
    out = []
    for f in sorted((EXPORT / OWN_USJ[kind] / iso / edition).glob("*.json")):
        if f.name != "_meta.json":
            chapters = extract_usj(json.loads(f.read_text(encoding="utf-8")))
            out.append("\n".join(v["text"] for vs in chapters.values() for v in vs))
    return out


def texts_for(sid: str, iso: str, route: dict) -> list[str]:
    src, eid = sid.split(":", 1)
    if src == "d":
        return dbt_texts(iso, eid, route)
    if src == "h":
        return helloao_texts(eid)
    if src == "p":
        return pkf_texts(iso, route["id"])
    return own_texts(route["path"])


def measure(texts: list[str]) -> dict | None:
    c = Counter()
    for t in texts:
        c.update(letters(t))
    if not sum(v for k, v in c.items() if k not in NEUTRAL):
        return None
    norms = Counter(normalization(t) for t in texts)
    return {"letters": dict(c.most_common()), "normalization": dict(norms), "files": len(texts)}


# --- verdict -----------------------------------------------------------------------------------

def detect(counts: dict) -> tuple[str | None, list[str]]:
    """(script, [scripts with >= MINOR_SHARE of the letters, main one first])."""
    c = {k: v for k, v in counts.items() if k not in NEUTRAL}
    total = sum(c.values())
    if not total:
        return None, []
    if c.get("Hira") or c.get("Kana"):
        main = "Jpan"
        for k in ("Hira", "Kana", "Hani"):
            c.pop(k, None)
    elif c.get("Hang"):
        main = "Kore"
        for k in ("Hang", "Hani"):
            c.pop(k, None)
    else:
        main = max(c, key=c.get)
        c.pop(main)
    minor = [k for k, v in sorted(c.items(), key=lambda x: -x[1]) if v / total >= MINOR_SHARE]
    return main, ([main] + minor if minor else [])


def refine(detected: str, stated: str | None) -> bool:
    """True if the stated script is a more specific form of the detected one."""
    return (detected == "Hani" and stated in ("Hans", "Hant")) or (detected == "Arab" and stated == "Aran")


def merged_normalization(norms: dict) -> str:
    seen = set(norms) - {"none"}
    if not seen:
        return "NFC"
    return seen.pop() if len(seen) == 1 else "mixed"


def verdict(measured: dict | None, stated_script: str | None, stated_direction: str | None) -> dict:
    """The published fields for one edition (see doc/catalog-edition-struct.md)."""
    out: dict = {}
    detected, scripts = detect(measured["letters"]) if measured else (None, [])
    if detected:
        if stated_script == detected or refine(detected, stated_script):
            out["script"], out["basis"] = stated_script, "metadata"
        else:
            out["script"], out["basis"] = detected, "detected"
            if stated_script:
                out["stated_script"] = stated_script
        if scripts:
            out["scripts"] = scripts
    elif stated_script:
        out["script"], out["basis"] = stated_script, "metadata"
    script = out.get("script")
    if script:
        out["direction"] = "rtl" if script in RTL else "ltr"
        if stated_direction and stated_direction != out["direction"]:
            out["stated_direction"] = stated_direction
    elif stated_direction:
        out["direction"], out["basis"] = stated_direction, "metadata"
    if script in NO_SPACES:
        out["spaces"] = False
    if measured:
        out["normalization"] = merged_normalization(measured["normalization"])
    return out


# --- stated metadata ---------------------------------------------------------------------------

def stated_metadata() -> dict:
    """{edition id: (script code or None, direction or None)} from each source's own metadata."""
    out = {}
    for f in (API_CACHE / "bibles" / "bible_details").glob("*.json"):
        a = (json.loads(f.read_text()).get("data") or {}).get("alphabet") or {}
        if a:
            out[f"d:{f.stem}"] = (script_code(a.get("script")), (a.get("direction") or "").lower() or None)
    hao = json.loads((API_CACHE / "helloao" / "available_translations.json").read_text())["translations"]
    for t in hao:
        out[f"h:{t['id']}"] = (None, t.get("textDirection"))
    ob = json.loads(OPENBIBLE_EDITIONS_FILE.read_text())["entries"]
    for pid, e in ob.items():
        f = API_CACHE / "openbible" / "text" / f"{pid}.json"
        if f.is_file():
            p = json.loads(f.read_text()).get("project", {})
            out[f"o:{e['abbr']}"] = (script_code(p.get("script")), (p.get("scriptDirection") or "").lower() or None)
    with open(API_CACHE / "ebible" / "translations.csv", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            out[f"e:{row['translationId']}"] = (script_code(row["script"]), row["textDirection"] or None)
    return out


# --- main --------------------------------------------------------------------------------------

def editions() -> dict:
    """{edition id: (iso, route)} for every edition in text-route.json (first testament seen)."""
    out = {}
    for key, eds in json.loads(TEXT_ROUTE_FILE.read_text())["entries"].items():
        for sid, route in eds.items():
            out.setdefault(sid, (key.split(":")[0], route))
    return out


def main() -> None:
    args = sys.argv[1:]
    force = "--force" in args
    only = args[args.index("--source") + 1] if "--source" in args else None
    jobs = int(args[args.index("--jobs") + 1]) if "--jobs" in args else 4
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    if force:
        done = {s: v for s, v in done.items() if only is not None and not s.startswith(only + ":")}
    todo = {s: v for s, v in editions().items()
            if (only is None or s.startswith(only + ":")) and done.get(s) is None}
    print(f"[edition-script] {len(todo)} editions to read ({sum(v is not None for v in done.values())} already read)")

    def one(item):
        sid, (iso, route) = item
        try:
            return sid, measure(texts_for(sid, iso, route))
        except Exception as e:  # noqa: BLE001 - one edition's failure is recorded, not fatal
            print(f"[edition-script] {sid}: {type(e).__name__}: {e}")
            return sid, None

    n = 0
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for sid, m in pool.map(one, sorted(todo.items())):
            done[sid] = m
            n += 1
            if n % 200 == 0:
                OUT.write_text(json.dumps(done, ensure_ascii=False))
                print(f"[edition-script] {n}/{len(todo)}")
    OUT.write_text(json.dumps(dict(sorted(done.items())), ensure_ascii=False))
    print(f"[edition-script] {len(done)} editions, {sum(1 for v in done.values() if v is None)} without text -> {OUT}")


if __name__ == "__main__":
    main()
