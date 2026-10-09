#!/usr/bin/env python3
"""Fingerprint the versification scheme of every DBT-native fileset.

DBT metadata (api-cache/bibles/bible_details/*.json) only carries chapter
NUMBERS, not per-chapter verse counts — so unlike the sibling PKF repo we
cannot compute an exact footprint from the catalog. Instead we CLASSIFY each
fileset into one of the standard Paratext schemes using cheap signals:

  Free (from bible_details, no download):
    - canon        book set  -> protestant / catholic / orthodox / nt-only
    - bookOrder    NT order  -> standard / byzantine / antilegomena
    - ps151        PSA==151  -> LXX/Orthodox signal
    - malJoel      MAL/JOL chapter counts -> Vulgate-family split

  Cheap (verse counts at diagnostic Psalm chapters):
    - PS117  2 verses  -> Masoretic Psalm numbering
             29 verses -> LXX/Slavonic Psalm numbering (Hebrew Ps 118)
    - PS51   19 verses -> eng  (superscription unnumbered, KJV tradition)
             21 verses -> org  (superscription = vv.1-2, Hebrew/Luther tradition)

helloAO / eBible text is a KJV-mapped mirror -> always "eng"; NOT fingerprinted.

Pass 1 (this run, no downloads): scan free signals + already-downloaded PS117,
classify what it can, and write the PS51/PS117 download manifest for review.

Output:
  export/versification/scan.json         per-fileset signals + provisional scheme
  export/versification/download-ps.txt   fileset ids still needing PS51 (+PS117)
"""
import json
import sys
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, EXPORT, REPO_ROOT, TEXT_DIR  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))

DETAILS_DIR = API_CACHE / "bibles" / "bible_details"
DL_OT = TEXT_DIR / "BB" / "ot"
OUT_DIR = EXPORT / "versification"

HELLOAO_API = "https://bible.helloao.org/api"
HELLOAO_CATALOG = API_CACHE / "helloao" / "available_translations.json"
HAO_CACHE = API_CACHE / "versification" / "helloao.json"

# Reference text per scheme + its per-book verse totals (whole-text checksum).
SCHEME_REF = {"eng": "eng_kjv", "org": "HBOMAS", "orgw": "fra_lsg",
              "catm": "fra_ncl", "lxx": "grc_bre", "vul": "lat_clv"}
# A masoretic text carrying the Greek additions to Daniel (MT Daniel ~357 verses;
# with the additions ~530) is catholic-masoretic (catm), not plain eng/org/orgw.
_DAN_ADDITIONS = 400
REF_TOTALS_CACHE = API_CACHE / "versification" / "scheme-book-totals.json"
# A per-book total exceeding the scheme reference by more than this many verses
# signals a wrong scheme (scheme gaps are large: Psalms eng/org ~66, Daniel/
# Esther additions ~100s), while tolerating minor textual variants.
CHECKSUM_TOLERANCE = 20
# Books whose CHAPTER count is scheme-defining. Only Psalms qualifies cleanly:
# 151>150 means the Septuagint's extra Psalm 151 (an over-count, so not a
# partial text). Malachi/Joel 3-vs-4 are NOT usable — our 'org' label tracks
# Psalm-superscription numbering, and many org texts (French Segond, Czech
# Kralická…) legitimately use Western 4-chapter Malachi.
_CH_DISCRIMINATING = {"PSA"}

_NT = ["MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH",
       "PHP", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS",
       "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"]
_NTSET = set(_NT)
_DC = {"TOB", "JDT", "ESG", "WIS", "SIR", "BAR", "LJE", "S3Y", "SUS", "BEL",
       "1MA", "2MA", "3MA", "4MA", "1ES", "2ES", "MAN", "PS2", "ODA", "PSS"}


def ot_text_fileset(abbr: str) -> str | None:
    """Find the plain-text OT (or complete) fileset id for a DBT bible_details abbr."""
    try:
        d = json.load(open(DETAILS_DIR / f"{abbr}.json"))["data"]
    except Exception:
        return None
    for bucket in d.get("filesets", {}).values():
        for f in bucket:
            if f.get("type") == "text_plain" and f.get("size") in ("OT", "C"):
                return f["id"]
    return None


def fetch_verse_count(abbr: str, iso: str, book: str, chapter: int) -> int | None:
    """Fetch a book/chapter from DBT, cache it (one verse per line), return the
    verse count. Counts distinct verse_start values — immune to poetic line
    breaks inside a verse (which would otherwise inflate a raw line count)."""
    import download_language_content as dl

    fsid = ot_text_fileset(abbr)
    if not fsid:
        return None
    dest = DL_OT / iso / abbr / book / f"{book}_{chapter:03d}_{fsid}.txt"
    if dest.exists():
        return len([ln for ln in dest.read_text(encoding="utf-8").split("\n") if ln.strip()])
    absent = dest.with_suffix(".absent")
    if absent.exists():
        return None
    res = dl.get_text_content(fsid, book, chapter)
    if not res:
        # A chapter DBT says isn't there (404, or 200 with no data) is recorded, so a
        # later run without --fetch still knows. A network error or 403 is not.
        reason = dl._classify_api_failure()
        if reason in ("http_404_not_found", "empty_data"):
            _mark_absent(absent, reason)
        return None
    if res.get("type") != "verses":
        return None
    # Merge fragments sharing a verse_start; flatten internal newlines to spaces.
    by_verse = {}
    for item in res["data"]:
        vs = item.get("verse_start")
        txt = " ".join(item.get("verse_text", "").split())
        if vs is None or not txt:
            continue
        by_verse[vs] = (by_verse.get(vs, "") + " " + txt).strip()
    if not by_verse:
        _mark_absent(absent, "no_verse_text")
        return None
    verses = [by_verse[k] for k in sorted(by_verse)]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(verses) + "\n", encoding="utf-8")
    return len(verses)


def _mark_absent(path: Path, reason: str) -> None:
    """Negative probe result: DBT confirmed this chapter has no content. Without it a
    later run can't tell "confirmed absent" from "never fetched". (Fixed 2026-10-09:
    org labels resting on a confirmed-absent MAL 4 were lost on every rebuild without
    --fetch, e.g. BULCBV, since only positive results were cached.)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(reason + "\n", encoding="utf-8")


def load_absent(book: str, ch3: str) -> set:
    """Fileset ids whose book/chapter probe was confirmed absent (see _mark_absent)."""
    return {p.relative_to(DL_OT).parts[1] for p in DL_OT.rglob(f"{book}_{ch3}_*.absent")}


def load_probe(book: str, ch3: str) -> dict:
    """Map fileset id -> verse (line) count for a cached book/chapter probe."""
    counts = {}
    for p in DL_OT.rglob(f"{book}_{ch3}_*.txt"):
        fileset = p.relative_to(DL_OT).parts[1]  # <iso>/<fileset>/<book>/file
        text = p.read_text(encoding="utf-8", errors="replace")
        counts[fileset] = len([ln for ln in text.split("\n") if ln.strip()])
    return counts


# --- helloAO / eBible versification (preserves original scheme, not KJV) ---

def _hao_get(path: str):
    req = urllib.request.Request(f"{HELLOAO_API}/{path}",
                                 headers={"User-Agent": "bible-story-builder/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def hao_verse_count(tid: str, book: str, ch: int) -> int | None:
    """The chapter's highest real verse NUMBER — what a .vrs shape records —
    NOT the `numberOfVerses` metadata field. Real, confirmed bug (2026-09-27,
    a client cross-check): they disagree whenever a translation genuinely
    skips a verse number mid-chapter (isl_bib's real PSA 51 has 20 verse
    entries but no v.17 at all, so its own last verse is numbered 21, not
    20 — `numberOfVerses` correctly counts entries present, but for
    versification purposes the chapter boundary is defined by the highest
    NUMBER, and trusting the count field there misclassified isl_bib as eng
    instead of the real org). Falls back to `numberOfVerses` only if the
    real content array is unusable for some reason (defensive, not the
    normal path)."""
    try:
        data = _hao_get(f"{tid}/{book}/{ch}.json")
    except Exception:
        return None
    content = data.get("chapter", {}).get("content", [])
    numbers = [v["number"] for v in content
               if isinstance(v, dict) and v.get("type") == "verse" and isinstance(v.get("number"), int)]
    if numbers:
        return max(numbers)
    return data.get("numberOfVerses")


def hao_probe(tid: str) -> dict:
    """Fingerprint one helloAO/eBible translation from its API (books.json +
    PSA 117 / PSA 51 numberOfVerses). Returns the same signal shape as DBT."""
    sig = {"iso": "", "bookCount": 0, "deuterocanon": False,
           "bookOrder": "unknown", "ps151": False, "mal": None, "jol": None,
           "ps117": None, "ps51": None, "sa17": None, "ki4": None, "mal4": None,
           "hag1": None, "bv": {}, "bc": {}}
    try:
        books = _hao_get(f"{tid}/books.json").get("books", [])
    except Exception:
        books = []
    if books:
        order = [b["id"] for b in books]
        nt = [b for b in order if b in _NTSET]

        def nch(bid):
            return next((b.get("numberOfChapters") for b in books if b["id"] == bid), None)
        sig.update(bookCount=len(order), bookOrder=book_order(nt),
                   deuterocanon=bool(set(order) & _DC),
                   ps151=(nch("PSA") or 0) >= 151, mal=nch("MAL"), jol=nch("JOL"),
                   # per-book verse totals + chapter counts — whole-text checksum
                   # (both free from books.json; chapters gate over/under checking)
                   bv={b["id"]: b.get("totalNumberOfVerses") for b in books},
                   bc={b["id"]: b.get("numberOfChapters") for b in books})
    sig["ps117"] = hao_verse_count(tid, "PSA", 117)
    if sig["ps117"] is not None and sig["ps117"] < 15:
        sig["ps51"] = hao_verse_count(tid, "PSA", 51)  # Masoretic: eng vs org
        if sig["ps51"] is not None and sig["ps51"] > 20 and sig.get("mal") == 4:
            # org-family + a real-content-listed 4th Malachi chapter — confirm
            # it's actually real content (not just a catalog claim) before
            # picking org vs orgw. Real, confirmed bug (2026-09-26, fra_lsg):
            # helloAO texts never got this confirmation fetch at all, so
            # classify() always returned "?" here — and the caller's "?"
            # fallback defaulted straight to "eng", actively wrong for a text
            # whose own Psalm data had already ruled eng out.
            #
            # Second real, confirmed bug (2026-09-27, a client cross-check —
            # eng_ojb, rmc_the): a chapter can be a real 200 response with a
            # genuine chapter shell but ZERO actual verses (checked directly:
            # both these texts' real MAL/4 has `"numberOfVerses": 0` and an
            # empty content array) — structurally identical to "not real
            # content" for this purpose, but `confirmed is not None` treated
            # 0 as truthy evidence, wrongly picking orgw over org.
            confirmed = hao_verse_count(tid, "MAL", 4)
            sig["mal4"] = bool(confirmed)
    elif sig["ps117"] is not None and sig["ps117"] >= 15:
        sig["sa17"] = hao_verse_count(tid, "1SA", 17)   # LXX: lxx vs vul
        sig["ki4"] = hao_verse_count(tid, "1KI", 4)
        true_lxx = sig["sa17"] is not None and sig["sa17"] <= 40 and (
            sig["ki4"] is None or sig["ki4"] <= 25)
        if sig["sa17"] is not None and not true_lxx:
            # Not true LXX — need Haggai ch.1 to split vul vs rso (see
            # classify()'s own comment on this discriminator).
            sig["hag1"] = hao_verse_count(tid, "HAG", 1)
    return sig


def hao_book_meta(tid: str) -> tuple[dict, dict]:
    """(per-book verse totals, per-book chapter counts) from books.json alone."""
    try:
        books = _hao_get(f"{tid}/books.json").get("books", [])
    except Exception:
        return {}, {}
    bv = {b["id"]: b.get("totalNumberOfVerses") for b in books}
    bc = {b["id"]: b.get("numberOfChapters") for b in books}
    return bv, bc


def reference_book_totals(fetch: bool) -> dict:
    """Per-scheme reference: {scheme: {book: {"v": verses, "c": chapters}}}."""
    if REF_TOTALS_CACHE.exists():
        return json.loads(REF_TOTALS_CACHE.read_text())
    if not fetch:
        return {}
    totals = {}
    for scheme, ref in SCHEME_REF.items():
        bv, bc = hao_book_meta(ref)
        if bv:
            totals[scheme] = {b: {"v": bv[b], "c": bc.get(b)} for b in bv}
    REF_TOTALS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    REF_TOTALS_CACHE.write_text(json.dumps(totals, sort_keys=True) + "\n", encoding="utf-8")
    return totals


def checksum_ok(bv: dict, bc: dict, scheme: str, ref_totals: dict) -> tuple[bool, int, list]:
    """Verify a text's per-book totals against its scheme reference. Two signals:

      1. VERSE over-count: a book with MORE verses than the scheme allows (e.g.
         org's extra Psalm-superscription verses, or the Greek additions to
         Daniel/Esther) means the wrong scheme. Under-counts are NOT flagged —
         `books.json` reports the full chapter count even when verses are omitted
         within chapters, so fewer verses can't be distinguished from a partial
         translation.
      2. CHAPTER mismatch on a discriminating book (Malachi/Joel 3-vs-4, Psalms
         150-vs-151): the reference's chapter count is scheme-defining, so a
         differing count is a real mismatch regardless of verse completeness.

    Returns (ok, worst_signal, flagged_books)."""
    ref = ref_totals.get(scheme)
    if not ref or not bv:
        return True, 0, []          # no reference (rso) or no data -> can't check
    worst, flagged = 0, []
    for book, tv in bv.items():
        if book in _DC:
            continue          # deuterocanon: verse divisions vary too much to check
        r = ref.get(book)
        if not isinstance(r, dict):
            continue
        rv, rc, tc = r.get("v"), r.get("c"), bc.get(book)
        if rv is not None and tv is not None and tv - rv > CHECKSUM_TOLERANCE:
            flagged.append(f"{book} v+{tv - rv}")
            worst = max(worst, tv - rv)
        elif book in _CH_DISCRIMINATING and tc is not None and rc is not None and tc > rc:
            flagged.append(f"{book} ch+{tc - rc}")
            worst = max(worst, (tc - rc) * 100)      # chapter over-count dominates ranking
    return (not flagged), worst, flagged


def helloao_ot_ids() -> list[str]:
    """helloAO translation ids that include OT (versification-relevant)."""
    if not HELLOAO_CATALOG.exists():
        return []
    cat = json.load(open(HELLOAO_CATALOG))
    return sorted(t["id"] for t in cat.get("translations", [])
                  if t.get("numberOfBooks", 0) > 27)


# Index keys whose label rests on a default or on partial evidence -> reason. Published
# as index.json's `assumed` map, so clients can tell a label from a guess.
ASSUMED: dict = {}
ASSUMED_REASONS = {
    "no_psalm_evidence": "no Psalm probe data; defaulted to eng",
    "nt_only": "New Testament only; defaulted to eng (Old Testament numbering unknown)",
    "ebible_direct": "eBible text not mirrored in helloAO; defaulted to eng",
    "tiebreaker_unconfirmed": "family known from the Psalms, deciding chapter not "
                              "confirmed (org vs orgw: MAL 4; vul vs rso: HAG 1)",
    "book_order_only": "rso from Byzantine book order alone, no Psalm evidence",
    "near_match": "PKF custom .vrs within a few chapters of this scheme; the differing "
                  "chapters are in irregular.json",
}


def classify_helloao(fetch: bool) -> dict:
    """Classify helloAO/eBible texts, caching probe results in HAO_CACHE.
    NT-only translations default to 'eng'. Returns {helloao:<id> -> scheme}."""
    cache = json.loads(HAO_CACHE.read_text()) if HAO_CACHE.exists() else {}
    index = {}
    ot_ids = helloao_ot_ids()
    ref_totals = reference_book_totals(fetch)
    if fetch:
        def full_probe(tid):
            e = cache.get(tid)
            if e is None:
                return True
            p = e.get("ps117")
            if p is None and "PSA" in e.get("bc", {}):
                return True   # has Psalms but PS117 probe failed -> retry
            # cached before the 1SA17 discriminator existed
            if p is not None and p >= 15 and e.get("sa17") is None:
                return True
            # ps51 invalidated (2026-09-27) after fixing hao_verse_count() to
            # use the real max verse NUMBER instead of the `numberOfVerses`
            # count field — see that function's own docstring; every cached
            # ps51 at the eng/org boundary (19 or 20) needed re-checking.
            if p is not None and p < 15 and e.get("ps51") is None:
                return True
            # Real, confirmed bug (2026-09-26, a client report): cached before
            # the mal4/hag1 tiebreaker probes existed, so entries that need
            # one are stuck on a stale scheme (fra_lsg wrongly "eng" instead
            # of "orgw"; rus_syn wrongly "vul" instead of "rso") until
            # re-probed with the fixed hao_probe().
            p51 = e.get("ps51")
            if p is not None and p < 15 and p51 is not None and p51 > 20 \
                    and e.get("mal") == 4 and e.get("mal4") is None:
                return True
            sa17 = e.get("sa17")
            if p is not None and p >= 15 and sa17 is not None and e.get("hag1") is None:
                true_lxx = sa17 <= 40 and (e.get("ki4") is None or e.get("ki4") <= 25)
                if not true_lxx:
                    return True
            return False
        full = [t for t in ot_ids if full_probe(t)]
        backfill = [t for t in ot_ids
                    if not full_probe(t) and (not cache[t].get("bv") or not cache[t].get("bc"))]
        print(f"[v11n] helloAO: {len(full)} full probes, {len(backfill)} bv/bc backfills "
              f"({len(cache)} cached)...")
        for i, tid in enumerate(full, 1):
            sig = hao_probe(tid)
            cache[tid] = {**sig, "scheme": classify(sig)[0]}
            if i % 50 == 0:
                print(f"        full {i}/{len(full)}")
        for i, tid in enumerate(backfill, 1):
            bv, bc = hao_book_meta(tid)               # 1 books.json call each
            cache[tid]["bv"], cache[tid]["bc"] = bv, bc
            if i % 50 == 0:
                print(f"        backfill {i}/{len(backfill)}")
        HAO_CACHE.parent.mkdir(parents=True, exist_ok=True)
        HAO_CACHE.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    # OT translations: re-classify from cached signals, then verify the whole-text
    # per-book checksum against the scheme reference. NT-only: default eng.
    flagged, undetermined = [], []
    for tid in ot_ids:
        entry = cache.get(tid)
        if not entry:
            continue
        scheme = classify(entry)[0]
        if scheme == "?":
            # This "?" can mean two very different things, and they must NOT
            # share a fallback: (a) no Psalm probe at all (no Psalms book, or
            # PS117 still failing) — genuinely undetermined, eng is a
            # reasonable default; (b) Psalm probe data EXISTS and already
            # rules eng out, but a tiebreaker (org-vs-orgw's mal4, vul-vs-rso's
            # hag1) hasn't been confirmed yet. Real, confirmed bug (2026-09-26,
            # a client report — fra_lsg): case (b) was being silently folded
            # into case (a)'s "default eng", producing a scheme classify()
            # had already ruled out. Now: keep the org/vul family the Psalm
            # signal already established, don't fall all the way to eng/vul-
            # by-default when there's real evidence against them.
            dan = entry.get("bv", {}).get("DAN")
            p117, p51 = entry.get("ps117"), entry.get("ps51")
            key = f"helloao:{tid}"
            if entry.get("bookOrder") == "byzantine":
                scheme = "rso"
                if p117 is None:
                    ASSUMED[key] = "book_order_only"
            elif dan is not None and dan > _DAN_ADDITIONS:
                scheme = "catm"
            elif p117 is not None and p117 < 15 and p51 is not None and p51 > 20:
                scheme = "org"      # eng already ruled out; org/orgw tiebreaker only
                ASSUMED[key] = "tiebreaker_unconfirmed"
            elif p117 is not None and p117 >= 15 and entry.get("sa17") is not None:
                scheme = "vul"      # true-lxx already ruled out; vul/rso tiebreaker only
                ASSUMED[key] = "tiebreaker_unconfirmed"
            elif entry.get("bc") and p117 is None:
                scheme = "eng"   # case (a) only: no Psalm evidence at all
                ASSUMED[key] = "no_psalm_evidence"
            else:
                undetermined.append(tid)
                index[f"helloao:{tid}"] = "undetermined"
                continue
            index[f"helloao:{tid}"] = scheme
            continue
        # Masoretic text carrying the Greek additions to Daniel -> catholic-
        # masoretic (a base eng/org/orgw scheme + additions). bv is helloAO-only.
        dan = entry.get("bv", {}).get("DAN")
        if scheme in ("eng", "org", "orgw") and dan is not None and dan > _DAN_ADDITIONS:
            scheme = "catm"
        ok, dev, bad = checksum_ok(entry.get("bv", {}), entry.get("bc", {}),
                                   scheme, ref_totals)
        if not ok:
            # Examined but conforms to no standard scheme -> official 'irregular'
            # sentinel (no .vrs; client uses the text's own verse numbers as-is).
            flagged.append((tid, scheme, dev, bad))
            index[f"helloao:{tid}"] = "irregular"
            continue
        index[f"helloao:{tid}"] = scheme
    if flagged:
        diag = {f"helloao:{tid}": {"nearest": scheme, "conflicts": bad}
                for tid, scheme, dev, bad in flagged}
        (EXPORT / "dbt" / "_vrs").mkdir(parents=True, exist_ok=True)
        (EXPORT / "dbt" / "_vrs" / "irregular.json").write_text(
            json.dumps(diag, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"[v11n] {len(flagged)} text(s) marked 'irregular' (no standard scheme):")
        for tid, scheme, dev, bad in flagged[:12]:
            print(f"        {tid} labeled {scheme}: {' '.join(bad[:5])}")
    if undetermined:
        print(f"[v11n] {len(undetermined)} text(s) marked 'undetermined' "
              f"(examined, insufficient data)")
    if HELLOAO_CATALOG.exists():
        cat = json.load(open(HELLOAO_CATALOG))
        for t in cat.get("translations", []):
            if t.get("numberOfBooks", 0) <= 27:  # NT-only
                index[f"helloao:{t['id']}"] = "eng"
                ASSUMED[f"helloao:{t['id']}"] = "nt_only"
    return index


def book_order(nt_books: list) -> str:
    if "JAS" not in nt_books or "ACT" not in nt_books:
        return "unknown"
    if nt_books.index("JAS") == nt_books.index("ACT") + 1:
        return "byzantine"
    if nt_books[-4:] == ["HEB", "JAS", "JUD", "REV"]:
        return "antilegomena"
    if "HEB" in nt_books and nt_books.index("JAS") == nt_books.index("HEB") + 1:
        return "standard"
    return "other"


def classify(sig: dict) -> tuple[str, bool]:
    """Return (scheme, needs_probe). scheme='?' when undetermined.

    Probes (verse counts, poetic-line-wrap tolerant):
      PS117  <15 Masoretic Psalm numbering / >=15 LXX Psalm numbering
      PS51   (Masoretic only) 19/20 eng heading / 21+ org heading
      1SA17  (LXX-Psalm only) <=40 true Septuagint book structure (short
             David & Goliath) / >40 Vulgate/Western structure
      1KI4   tiebreaker with 1SA17 (both short -> genuine lxx)

    Deuterocanon does NOT force 'vul': a Catholic Bible with Masoretic Psalms
    still uses eng/org verse structure — vul.vrs (LXX Psalms) would mis-map it.

    Byzantine NT book order does NOT force 'rso' on its own — fixed
    2026-09-04 after a real, confirmed misclassification: BULCBV has
    Byzantine NT ordering but genuinely Masoretic-numbered Psalms (live
    DBT: PSA 117 = 2 verses, PSA 51 = 21 verses -> org), not rso. NT book
    order and OT Psalm-numbering scheme are independent axes; byz is now
    only a CONFIRMING signal alongside real lxx-numbering evidence
    (matching a client-reported bug in audio-sync's alignment pipeline,
    traced to this exact classifier bug — see doc/versification-fixes.md).
    """
    p117 = sig.get("ps117")
    p51 = sig.get("ps51")
    sa17 = sig.get("sa17")
    ki4 = sig.get("ki4")
    hag1 = sig.get("hag1")
    byz = sig["bookOrder"] == "byzantine"
    masoretic = p117 is not None and p117 < 15
    lxx_num = (p117 is not None and p117 >= 15) or sig["ps151"]

    if p117 is None:
        # No Psalm-numbering evidence at all yet — book order alone is not
        # sufficient (see docstring note above). Always probe before
        # committing to any scheme, byz included.
        return "?", True
    if lxx_num:
        if byz:
            return "rso", False           # confirmed: Byzantine order + real LXX Psalm numbering
        if sa17 is None:
            return "?", True              # need 1SA17 to split lxx vs vul/rso
        true_lxx = sa17 <= 40 and (ki4 is None or ki4 <= 25)
        if true_lxx:
            return "lxx", False
        # Not true LXX. Real, confirmed bug (found 2026-09-26 via a client
        # report — rus_syn): NT book order alone used to gate "rso" entirely
        # — a non-byzantine NT order fell through to "vul" unconditionally,
        # even when the real OT content is genuinely rso (rus_syn's own
        # Haggai is 1:15/2:23, matching rso, not vul's 1:14/2:24; its NT
        # book order just happens to be "standard"). NT book order and OT
        # verse-numbering scheme are independent axes — same principle
        # already applied to org's own byz-independence fix above, just
        # not extended to this branch. Haggai chapter 1's real verse count
        # is a clean, confirmed discriminator: 14 is unique to vul; every
        # other scheme (rso included) is 15.
        if hag1 is None:
            return "?", True              # need HAG 1 to split vul vs rso
        return ("vul" if hag1 == 14 else "rso"), False
    if masoretic:
        if p51 is None:
            return "?", True              # heading unknown -> need PS51
        if p51 <= 20:
            return "eng", False           # superscription unnumbered/folded (KJV)
        # org Psalm-superscription numbering; Western (4-chapter) Malachi marks
        # the org-western hybrid (French Segond / Czech Kralická tradition).
        # `mal==4` alone is NOT enough — it's DBT's own catalog *listing*
        # (free, unfetched), not confirmed content. Fixed 2026-09-04:
        # BULCBV's bible_details claims 4 Malachi chapters but MAL/4 is a
        # real 404 (no such content) — DBT's own metadata was simply wrong.
        # `mal4` is the CONFIRMED signal (did we actually fetch real
        # content for chapter 4); only trust it once known.
        if sig.get("mal") == 4:
            if sig.get("mal4") is None:
                return "?", True          # need to confirm chapter 4 is real, not just listed
            return ("orgw" if sig["mal4"] else "org"), False
        return "org", False               # Hebrew: superscription = vv.1-2, Mal 3
    # PS117 unavailable (audio-only fileset with no DBT text)
    return "?", True


def main():
    fetch = "--fetch" in sys.argv
    ps117 = load_probe("PSA", "117")
    ps51 = load_probe("PSA", "051")
    sa17 = load_probe("1SA", "017")
    ki4 = load_probe("1KI", "004")
    mal4 = load_probe("MAL", "004")  # confirms bible_details' free mal==4 claim against real content
    mal4_absent = load_absent("MAL", "004")  # ...or confirms the claim is wrong
    hag1 = load_probe("HAG", "001")  # vul-vs-rso discriminator (14 verses -> vul, else rso)

    # First gather all filesets + free signals
    filesets = []
    for p in sorted(DETAILS_DIR.glob("*.json")):
        try:
            d = json.load(open(p))["data"]
        except Exception:
            continue
        books = [b["book_id"] for b in d.get("books", [])]
        if "PSA" not in books:
            continue  # versification variance lives in Psalms/OT
        abbr = p.stem
        iso = d.get("iso", "")
        nt_books = [b for b in books if b in _NTSET]
        psa_ch = next(len(b["chapters"]) for b in d["books"] if b["book_id"] == "PSA")

        def ch(book, d=d):
            return next((len(b["chapters"]) for b in d["books"] if b["book_id"] == book), None)

        filesets.append({
            "abbr": abbr, "iso": iso,
            "bookCount": len(books),
            "deuterocanon": bool(set(books) & _DC),
            "bookOrder": book_order(nt_books),
            "ps151": psa_ch >= 151,
            "mal": ch("MAL"), "jol": ch("JOL"),
            "ps117": ps117.get(abbr), "ps51": ps51.get(abbr),
            "sa17": sa17.get(abbr), "ki4": ki4.get(abbr),
            "mal4": (True if abbr in mal4 else False if abbr in mal4_absent else None),
            "hag1": hag1.get(abbr),
        })

    # Optionally fetch probes for undetermined filesets that actually have DBT text
    if fetch:
        todo = [f for f in filesets
                if classify(f)[1] and ot_text_fileset(f["abbr"]) is not None]
        print(f"[v11n] fetching probes for {len(todo)} filesets with DBT text "
              f"(PS117 if missing, then PS51)...")
        for i, f in enumerate(todo, 1):
            if f["ps117"] is None:
                f["ps117"] = fetch_verse_count(f["abbr"], f["iso"], "PSA", 117)
            if f["ps117"] is not None and f["ps117"] < 15 and f["ps51"] is None:
                # Masoretic: heading probe (eng vs org)
                f["ps51"] = fetch_verse_count(f["abbr"], f["iso"], "PSA", 51)
            if (f["ps117"] is not None and f["ps117"] < 15 and f["ps51"] is not None
                    and f["ps51"] > 20 and f["mal"] == 4 and f["mal4"] is None):
                # org-family, free metadata claims a 4th Malachi chapter —
                # confirm it's real content, not just a catalog listing
                # (BULCBV: bible_details claims 4, MAL/4 is a real 404). Also
                # guard against a real-but-empty (0-verse) response — see the
                # analogous helloAO fix's comment above for why "not None"
                # alone isn't enough.
                confirmed = fetch_verse_count(f["abbr"], f["iso"], "MAL", 4)
                f["mal4"] = bool(confirmed)
            if f["ps117"] is not None and f["ps117"] >= 15 and f["sa17"] is None:
                # LXX Psalms: structure probe (true Septuagint vs Vulgate/Western)
                f["sa17"] = fetch_verse_count(f["abbr"], f["iso"], "1SA", 17)
                f["ki4"] = fetch_verse_count(f["abbr"], f["iso"], "1KI", 4)
            true_lxx = (f["sa17"] is not None and f["sa17"] <= 40
                        and (f["ki4"] is None or f["ki4"] <= 25))
            if (f["ps117"] is not None and f["ps117"] >= 15 and f["sa17"] is not None
                    and not true_lxx and f["hag1"] is None):
                # Not true LXX — confirm vul vs rso via Haggai ch.1 (14 -> vul,
                # else rso; see classify()'s own comment on this discriminator).
                f["hag1"] = fetch_verse_count(f["abbr"], f["iso"], "HAG", 1)
            if i % 50 == 0:
                print(f"        {i}/{len(todo)}")

    # Classify DBT-native
    records, index, need_download = {}, {}, []
    scheme_counts = Counter()
    for f in filesets:
        scheme, needs = classify(f)
        f["scheme"] = scheme
        records[f"{f['iso']}/{f['abbr']}"] = f
        scheme_counts[scheme] += 1
        if scheme != "?":
            index[f"{f['iso']}/{f['abbr']}"] = scheme
        if needs:
            need_download.append(f["abbr"])

    # Classify helloAO / eBible texts (preserve original scheme; cached)
    hao_index = classify_helloao(fetch)
    index.update(hao_index)
    hao_counts = Counter(hao_index.values())

    # eBible-direct texts (ebible: prefix, not mirrored in helloAO) default to
    # eng: the LXX/Vulgate eBible editions are major languages already resolved
    # via helloAO; the few direct ones are minority Protestant translations.
    ebible_index = {}
    for dj in (EXPORT / "ALL-langs").rglob("data.json"):
        try:
            d = json.loads(dj.read_text())
        except Exception:
            continue
        for field in ("t", "t_alt"):
            v = d.get(field, "")
            if v.startswith("ebible:"):
                ebible_index[f"ebible:{v.split(':', 1)[1]}"] = "eng"
                ASSUMED[f"ebible:{v.split(':', 1)[1]}"] = "ebible_direct"
    index.update(ebible_index)

    # PKF collections (pkf:<collection id>): declared scheme or custom .vrs file, plus
    # their New Testament variants (pkf_versification.py, nt-variants.json).
    import pkf_versification as pv
    import derive_tvtms_org_eng as tv
    nt_index, pkf_diag = {}, {}
    pkf_manifest = API_CACHE / "pkf-manifest.json"
    nt_variants_file = EXPORT / "_vrs" / "map" / "nt-variants.json"
    if pkf_manifest.is_file() and nt_variants_file.is_file():
        schemes = {s: tv._shape(REPO_ROOT / "data" / "vrs" / f"{s}.vrs") for s in pv.SCHEMES}
        pkf_labels, pkf_assumed, nt_index, pkf_diag = pv.classify_pkf(
            json.loads(pkf_manifest.read_text())["languages"], schemes,
            json.loads(nt_variants_file.read_text()), API_CACHE / "pkf-vrs")
        # DBT and helloAO New Testaments, from the probe cache (nt_probes.py --fetch)
        import nt_probes
        from nt_versification import NtClassifier
        probed = nt_probes.nt_entries(dict(index), NtClassifier(schemes, json.loads(nt_variants_file.read_text())))
        nt_index.update(probed)
        print(f"[v11n] DBT/helloAO: {len(probed)} with New Testament variants (from nt_probes.py's cache)")
        index.update(pkf_labels)
        ASSUMED.update(pkf_assumed)
        print(f"[v11n] PKF: {len(pkf_labels)} collections {dict(Counter(pkf_labels.values()))}; "
              f"{len(nt_index)} editions in all with New Testament variants")
    else:
        print("[v11n] PKF skipped: needs api-cache/pkf-manifest.json and _vrs/map/nt-variants.json (make vrs-map)")
    if pkf_diag:
        irr = EXPORT / "dbt" / "_vrs" / "irregular.json"
        merged = json.loads(irr.read_text()) if irr.is_file() else {}
        merged.update(pkf_diag)
        irr.parent.mkdir(parents=True, exist_ok=True)
        irr.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "scan.json").write_text(
        json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "download-ps.txt").write_text("\n".join(sorted(need_download)) + "\n",
                                             encoding="utf-8")

    # Publishable index for the CDN (/dbt/_vrs/index.json). The standard .vrs
    # scheme files are reused from the sibling PKF tree where available.
    pub_dir = EXPORT / "dbt" / "_vrs"
    pub_dir.mkdir(parents=True, exist_ok=True)
    schemes_used = sorted(set(index.values()))
    # Cross-scheme verse maps published under /_vrs/map/<src>-to-eng.json (built by
    # generate_vrs_map.py). Advertise whichever ones have been generated.
    map_dir = EXPORT / "_vrs" / "map"
    maps = sorted(p.name for p in map_dir.glob("*-to-*.json")) if map_dir.is_dir() else []
    pub = {
        "vrs_base": "https://cdn.bibel.wiki/_vrs/",
        "map_base": "https://cdn.bibel.wiki/_vrs/map/",
        "maps": maps,
        "schemes": [s for s in schemes_used if s not in ("irregular", "undetermined")],
        # Sentinels are NOT .vrs files. 'irregular': examined but matches no
        # standard scheme (conflicting/non-standard) — use the text's own verse
        # numbers as-is (diagnostics in /_vrs/irregular.json). 'undetermined':
        # examined but insufficient data to classify (e.g. no Psalms).
        "sentinels": {
            "irregular": "no standard scheme — use the text's own verse numbers",
            "undetermined": "examined, insufficient data to classify",
        },
        "l": index,
        # Keys of `l` whose label is a default or rests on partial evidence -> reason
        # (see `assumed_reasons`). Every other label is backed by probe evidence.
        "assumed": {k: ASSUMED[k] for k in sorted(ASSUMED) if k in index},
        "assumed_reasons": ASSUMED_REASONS,
        # New Testament numbering that differs from what the key's `l` scheme's map assumes:
        # {key: {variants, profile?, unexplained?}}. Take NT rows from those variants in
        # map_base + nt_variants (identity elsewhere), not from the `l` map.
        "nt_variants": "nt-variants.json",
        "nt": dict(sorted(nt_index.items())),
    }
    (pub_dir / "index.json").write_text(
        json.dumps(pub, separators=(",", ":"), sort_keys=True), encoding="utf-8")

    print(f"[v11n] DBT-native filesets with Psalms: {len(records)}")
    print("[v11n] scheme distribution:")
    for s, c in scheme_counts.most_common():
        label = {"eng": "English (KJV heading)", "org": "Hebrew/Luther heading",
                 "lxx": "Septuagint numbering", "rso": "Russian Orthodox (Byzantine)",
                 "vul": "Vulgate/Catholic", "?": "UNDETERMINED (needs PS51/PS117)"}.get(s, s)
        print(f"        {c:4d}  {s:4}  {label}")
    print(f"[v11n] DBT index: {len(index) - len(hao_index)} classified; "
          f"{len(need_download)} undetermined")
    print("[v11n] helloAO/eBible scheme distribution:")
    for s, c in hao_counts.most_common():
        print(f"        {c:4d}  {s}")
    print(f"[v11n] total index.json: {len(index)} mappings "
          f"(DBT + helloAO/eBible) -> export/dbt/_vrs/index.json")
    if not fetch and need_download:
        print("[v11n] run with --fetch to download probes and finalize")


if __name__ == "__main__":
    main()
