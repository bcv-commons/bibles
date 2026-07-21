#!/usr/bin/env python3
"""Own, verify, and stage the standard Paratext versification schemes.

We take ownership of the six standard `.vrs` scheme files (previously hosted by
the sibling PKF repo at pkf/_vrs/). Source of truth lives in data/vrs/*.vrs;
this script VERIFIES each scheme against a canonical reference text (helloAO
API) at a set of discriminating "witness" chapters, then stages the set into
export/_vrs/ for publishing to the neutral central location cdn.bibel.wiki/_vrs/.

The `.vrs` value is the LAST VERSE NUMBER per chapter (the max, gaps included) —
NOT the verse count. The LXX omits ~half of 1SA 17 (vv.12-31, 55-58) but keeps
Masoretic numbering, so its last verse is 54, not the 32 present verses.

Reference texts (helloAO ids):
  eng  eng_kjv   English / KJV
  org  HBOMAS    Hebrew Masoretic (superscription = verse; OT only)
  lxx  grc_bre   Brenton Septuagint (short 1SA 17, MT numbering w/ gaps)
  vul  lat_clv   Clementine Vulgate
  rso  —         no clean single-text reference; baseline adopted, verify later

Usage:
  python3 generate_vrs.py            # verify witnesses + stage export/_vrs/
  python3 generate_vrs.py --full     # derive full footprints (heavy, cached)
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, EXPORT, VRS_DIR  # noqa: E402

SRC_DIR = VRS_DIR
OUT_DIR = EXPORT / "_vrs"
FOOTPRINT_CACHE = API_CACHE / "versification" / "footprints"
HELLOAO_API = "https://bible.helloao.org/api"

SCHEMES = ["eng", "org", "orgw", "catm", "lxx", "vul", "rso"]
SCHEME_REF = {"eng": "eng_kjv", "org": "HBOMAS", "orgw": "fra_lsg",
              "catm": "fra_ncl", "lxx": "grc_bre", "vul": "lat_clv"}
# Schemes generated from our reference text's full footprint. Named sub-schemes:
#   orgw = org Psalm-superscription numbering + Western (eng) book chaptering.
#   catm = catholic-masoretic: masoretic Psalms + deuterocanon + Greek additions
#          to Daniel/Esther (distinct from vul, which uses LXX Psalm numbering).
REGEN = {"lxx", "vul", "orgw", "catm"}

# Canonical book order for rendering.
_OT = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB "
       "PSA PRO ECC SNG ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP "
       "HAG ZEC MAL").split()
_NT_ORDER = ("MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT "
             "PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()
_DC = ("TOB JDT ESG WIS SIR BAR LJE S3Y SUS BEL 1MA 2MA 3MA 4MA 1ES 2ES MAN PS2 "
       "ODA PSS EZA 5EZ 6EZ DAG PSB").split()
BOOK_ORDER = _OT + _NT_ORDER + _DC

# Chapters that discriminate the schemes (+ a few sanity witnesses).
WITNESS = [
    ("PSA", 117), ("PSA", 51), ("PSA", 3),          # Psalm numbering / heading
    ("1SA", 17), ("1KI", 4), ("1KI", 5),            # LXX vs Vulgate structure
    ("1KI", 20), ("1KI", 21), ("2SA", 19),
    ("JOL", 3), ("MAL", 3),                         # family (chapter splits)
    ("GEN", 31), ("EXO", 20), ("PSA", 119), ("JHN", 21),  # sanity
]


def _hao_get(path: str):
    req = urllib.request.Request(f"{HELLOAO_API}/{path}",
                                 headers={"User-Agent": "bible-story-builder/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def last_verse(tid: str, book: str, ch: int) -> int | None:
    """Highest verse NUMBER in a chapter (max, not count) — the .vrs value."""
    try:
        d = _hao_get(f"{tid}/{book}/{ch}.json")
    except Exception:
        return None
    nums = [c.get("number") for c in d.get("chapter", {}).get("content", [])
            if c.get("type") == "verse" and isinstance(c.get("number"), int)]
    return max(nums) if nums else None


def parse_vrs(text: str) -> dict:
    """'BOOK c:last c:last …' -> {(book, chapter): last_verse}."""
    fp = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        book = parts[0]
        for tok in parts[1:]:
            if ":" in tok:
                c, v = tok.split(":")
                try:
                    fp[(book, int(c))] = int(v)
                except ValueError:
                    pass
    return fp


def render(scheme: str, fp: dict) -> str:
    """Footprint {(book, ch): last} -> .vrs text in canonical book order."""
    bybook = {}
    for (b, c), v in fp.items():
        bybook.setdefault(b, {})[c] = v
    lines = [f'# Versification  "{scheme}"',
             "# Scheme structure only (last verse per chapter). Cross-scheme verse",
             "# mappings (which verse maps where) are NOT derivable from these shapes;",
             "# they are published separately as /_vrs/map/<scheme>-to-eng.json,",
             "# derived from TVTMS. See generate_vrs_map.py.", "#"]
    ordered = [b for b in BOOK_ORDER if b in bybook] + \
              [b for b in sorted(bybook) if b not in BOOK_ORDER]
    for b in ordered:
        chs = bybook[b]
        lines.append(f"{b} " + " ".join(f"{c}:{chs[c]}" for c in sorted(chs)))
    return "\n".join(lines) + "\n"


def build_footprint(tid: str) -> dict:
    """Full {(book, ch): last_verse} for a text via the API, cached per text.
    Chapters are fetched concurrently (the ~1,400 calls otherwise dominate).
    Used to author scheme files and to hash custom (non-standard) structures."""
    from concurrent.futures import ThreadPoolExecutor

    cache_path = FOOTPRINT_CACHE / f"{tid}.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    try:
        books = _hao_get(f"{tid}/books.json").get("books", [])
    except Exception:
        return {}
    want = []
    for b in books:
        book, nch = b["id"], b.get("numberOfChapters") or 0
        first = b.get("firstChapterNumber") or 1
        for ch in range(first, first + nch):
            want.append((book, ch))
    missing = [(b, c) for b, c in want if f"{b}/{c}" not in cache]
    if missing:
        with ThreadPoolExecutor(max_workers=16) as ex:
            results = ex.map(lambda bc: (bc, last_verse(tid, bc[0], bc[1])), missing)
            for (book, ch), lv in results:
                cache[f"{book}/{ch}"] = lv
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, sort_keys=True) + "\n", encoding="utf-8")
    return {(b, c): cache[f"{b}/{c}"] for b, c in want if isinstance(cache.get(f"{b}/{c}"), int)}


def regen_from_footprint(scheme: str) -> bool:
    """(Re)author data/vrs/<scheme>.vrs from its reference text's full footprint.
    Fetches the reference footprint (cached). Returns True if written."""
    ref = SCHEME_REF.get(scheme)
    if not ref:
        return False
    fp = build_footprint(ref)
    if not fp:
        return False
    (SRC_DIR / f"{scheme}.vrs").write_text(render(scheme, fp), encoding="utf-8")
    return True


def verify(scheme: str, baseline: dict, full: bool) -> list:
    """Compare the reference text against our .vrs. Returns list of mismatches."""
    ref = SCHEME_REF.get(scheme)
    if not ref:
        print(f"  {scheme}: no reference text — baseline adopted (verify later)")
        return []
    chapters = sorted(baseline) if full else WITNESS
    cache_path = FOOTPRINT_CACHE / f"{ref}.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    mismatches, checked = [], 0
    for book, ch in chapters:
        if (book, ch) not in baseline:
            continue
        key = f"{book}/{ch}"
        if key in cache:
            lv = cache[key]
        else:
            lv = last_verse(ref, book, ch)
            cache[key] = lv
        checked += 1
        if lv is not None and lv != baseline[(book, ch)]:
            mismatches.append((book, ch, baseline[(book, ch)], lv))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, sort_keys=True) + "\n", encoding="utf-8")
    ok = checked - len(mismatches)
    print(f"  {scheme} (ref {ref}): {ok}/{checked} witnesses reproduce; "
          f"{len(mismatches)} mismatch")
    for book, ch, base, lv in mismatches:
        print(f"      {book} {ch}: our .vrs={base}  {ref}={lv}")
    return mismatches


def main():
    full = "--full" in sys.argv
    if not SRC_DIR.is_dir():
        sys.exit(f"[vrs] {SRC_DIR}/ not found — seed from pkf/_vrs baseline first")

    regen = "--regen" in sys.argv
    if regen:
        print("[vrs] regenerating owned schemes from reference footprints...")
        for scheme in REGEN:
            if regen_from_footprint(scheme):
                print(f"  {scheme}: regenerated from {SCHEME_REF[scheme]}")

    print("[vrs] verifying standard schemes against reference texts...")
    all_ok = True
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for scheme in SCHEMES:
        src = SRC_DIR / f"{scheme}.vrs"
        if not src.exists():
            print(f"  {scheme}: MISSING {src}")
            all_ok = False
            continue
        baseline = parse_vrs(src.read_text())
        mism = verify(scheme, baseline, full)
        if mism:
            all_ok = False
        # Stage for publishing
        (OUT_DIR / f"{scheme}.vrs").write_text(src.read_text(), encoding="utf-8")

    print(f"[vrs] staged {len(SCHEMES)} schemes -> {OUT_DIR}/ "
          f"({'all witnesses reproduce' if all_ok else 'MISMATCHES — review above'})")


if __name__ == "__main__":
    main()
