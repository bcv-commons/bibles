#!/usr/bin/env python3
"""Derive the Hebrew (org) -> English (eng) single-verse map from TVTMS.

Reads STEPBible-Data's TVTMS versification file at a pinned commit, pulls
the Hebrew column against the English KJV column of every per-book block,
and writes the non-identity pairs to data/vrs/tvtms-org-to-eng.derived.tsv
with a provenance record.

The input is pinned by commit AND sha256: a mismatch aborts the run, so a
changed upstream file cannot silently change our map.

Usage:
    python3 pipeline/core/derive_tvtms_org_eng.py          # derive + write
    python3 pipeline/core/derive_tvtms_org_eng.py --check  # verify pinned input only
"""
import collections
import hashlib
import json
import re
import sys
import urllib.parse
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import DOWNLOADS, REPO_ROOT  # noqa: E402

TVTMS_COMMIT = "902681f77a4a2975b809555ff3c35ffe3c48a1d5"
TVTMS_PATH = ("Versification/TVTMS - Translators Versification Traditions with "
              "Methodology for Standardisation for Eng+Heb+Lat+Grk+Others - "
              "STEPBible.org CC BY.txt")
TVTMS_SHA256 = "63058e0f20201af4bdaa7d830da5be8f493455d947c5f147d84840b33db9ddf8"
TVTMS_URL = (f"https://raw.githubusercontent.com/STEPBible/STEPBible-Data/"
             f"{TVTMS_COMMIT}/{urllib.parse.quote(TVTMS_PATH)}")

DEBUG = "--debug" in sys.argv
CACHE = DOWNLOADS / "tvtms" / f"{TVTMS_COMMIT}.txt"
ORG_VRS = REPO_ROOT / "data" / "vrs" / "org.vrs"
OUT_TSV = REPO_ROOT / "data" / "vrs" / "tvtms-org-to-eng.derived.tsv"

# NT exception, added 2026-10-07: every scheme here is deliberately OT-only
# (lexeme-aligner's own description: "our NT remap is the identity for every
# scheme"). These four are the one narrow, fully TVTMS-cited exception,
# requested by lexeme-aligner for its Nestle 1904 spine, for the schemes
# whose shape already agrees with the spine at these exact chapters (org,
# orgw, catm, rso — vul is excluded; its NT stays out of scope, same as
# before). Each entry is read straight off TVTMS's own structured section
# for that chapter (line numbers below), not inferred.
#
# 2CO 13: TVTMS "$2Co.13:12-13" section (lines 4078-4082), Greek+NRSV column
# (the critical-text column the Nestle 1904 spine follows here) — its v12
# absorbs KJV/eng's v12+13 (lines 4080-4081), and its v13 = eng's v14,
# renumbered one-to-one (line 4082).
NT_FIX_2CO13_RENUMBER = ("2CO 13:13", "2CO 13:14")  # TVTMS line 4082
NT_FIX_2CO13_MULTIVERSE = {"s": "2CO 13:12", "t": "2CO 13:12-13",
                           "tvtms_line": "4080-4081", "tvtms_action": "SubdividedVerse"}

# ACT 19: TVTMS "$Act.19:40-41" section (lines 4044-4047), Greek column —
# its v40 absorbs KJV/eng's v40+41 entirely (eng's v41 is "Absent [=19:40]"
# in the Greek column).
NT_FIX_ACT19_MULTIVERSE = {"s": "ACT 19:40", "t": "ACT 19:40-41",
                           "tvtms_line": "4046-4047", "tvtms_action": "MergedPrevVerse"}

# REV 12/13 (rso only — org/orgw/catm already agree with eng here, so no row
# needed for them): TVTMS "$Rev.12:17-13.1a" section (lines 4102-4106),
# Greek column — its v13:1 absorbs KJV/eng's v12:18 AND v13:1 together.
NT_FIX_REV12_MULTIVERSE = {"s": "REV 13:1", "t": "REV 12:18-13:1",
                           "tvtms_line": "4105-4106", "tvtms_action": "OneToOne"}


def _merge_multiverse(path: Path, new_entries: list[dict], source_scheme: str) -> None:
    """Merges NT-fix entries into a <scheme>-to-eng.multiverse.json, creating
    it fresh if absent (same shape write_multiverse() already writes),
    without disturbing any existing map/evidence rows already there (rso's
    file in particular carries rows with no deriver of their own — see
    doc/vrs-maps.md and the 2026-10-07 session notes)."""
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
    else:
        doc = {
            "source_scheme": source_scheme, "target_scheme": "eng",
            "kind": "multi-verse relations (not in the single-verse map)",
            "authority": "TVTMS — Translators Versification Traditions, STEPBible-Data (CC BY 4.0)",
            "attribution": "https://STEPBible.org",
            "tvtms_rev": TVTMS_COMMIT, "tvtms_sha256": TVTMS_SHA256,
            "map": [], "evidence": [], "flagged_not_published": [],
        }
    existing = {(e["s"], e["t"]) for e in doc["map"]}
    for e in new_entries:
        if (e["s"], e["t"]) in existing:
            continue
        doc["map"].append({"s": e["s"], "t": e["t"]})
        doc["evidence"].append({"s": e["s"], "t": e["t"], "tvtms_line": e["tvtms_line"], "tvtms_action": e["tvtms_action"]})
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_nt_fixes() -> None:
    """The one deliberate NT exception — see NT_FIX_* above."""
    for out_path, scheme in ((OUT_TSV, "org"), (ORGW_OUT, "orgw"), (RSO_OUT, "rso")):
        if not out_path.is_file():
            continue
        text = out_path.read_text(encoding="utf-8")
        a, b = NT_FIX_2CO13_RENUMBER
        if f"{a}\t{b}\t" not in text:
            out_path.write_text(text + f"{a}\t{b}\tRenumber verse\n", encoding="utf-8")

    _merge_multiverse(MULTI_OUT, [NT_FIX_ACT19_MULTIVERSE, NT_FIX_2CO13_MULTIVERSE], "org")
    _merge_multiverse(REPO_ROOT / "export" / "_vrs" / "map" / "orgw-to-eng.multiverse.json",
                       [NT_FIX_ACT19_MULTIVERSE, NT_FIX_2CO13_MULTIVERSE], "orgw")
    # rso's multiverse file has real hand-curated content (built with
    # lexeme-aligner's input) with no deriver of its own, unlike org/orgw/
    # catm's here — so, unlike those, its real source lives under the
    # tracked data/vrs/ (not export/, which make clean wipes with nothing
    # to regenerate it). publish-vrs-maps.sh stages it into export/ before
    # publish. Fixed 2026-10-07 after the same export/-holds-real-source
    # mistake this repo already made once with export/timing-data/.
    _merge_multiverse(REPO_ROOT / "data" / "vrs" / "rso-to-eng.multiverse.json",
                       [NT_FIX_ACT19_MULTIVERSE, NT_FIX_2CO13_MULTIVERSE, NT_FIX_REV12_MULTIVERSE], "rso")
    _merge_multiverse(REPO_ROOT / "export" / "_vrs" / "map" / "catm-to-eng.multiverse.json",
                       [NT_FIX_ACT19_MULTIVERSE, NT_FIX_2CO13_MULTIVERSE], "catm")
    # catm's single-verse map is built from org's derived.tsv directly (see
    # `make vrs-map`'s catm rule, --mapping tvtms-org-to-eng.derived.tsv) —
    # the 2CO 13:13 renumber row above, written to OUT_TSV, already reaches
    # catm's published map with no separate catm-side row needed.

    print("[tvtms] NT fixes: 2CO 13 + ACT 19 applied to org/orgw/rso/catm; REV 12/13 applied to rso only")
PROVENANCE = REPO_ROOT / "data" / "vrs" / "tvtms-org-to-eng.provenance.json"

REF = re.compile(r"^([0-9A-Za-z]+)\.(\d+):(\d+)(?:-(\d+))?([a-z])?$")
TITLE = re.compile(r"^([0-9A-Za-z]+)\.(\d+):Title$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_pinned() -> Path:
    if CACHE.exists() and sha256(CACHE) == TVTMS_SHA256:
        return CACHE
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(TVTMS_URL, timeout=120)
    r.raise_for_status()
    CACHE.write_bytes(r.content)
    got = sha256(CACHE)
    if got != TVTMS_SHA256:
        CACHE.unlink()
        raise SystemExit(f"[tvtms] sha256 mismatch for {TVTMS_COMMIT}: got {got}, pinned {TVTMS_SHA256}")
    return CACHE


def _load_last_verse() -> dict[tuple[str, int], int]:
    out: dict[tuple[str, int], int] = {}
    for line in ORG_VRS.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        book, *chapters = line.split()
        for tok in chapters:
            ch, v = tok.split(":")
            out[(book.upper(), int(ch))] = int(v)
    return out


LAST_VERSE = _load_last_verse()


def org_books() -> set[str]:
    return {l.split()[0] for l in ORG_VRS.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")}


def expand(ref: str, books: set[str]) -> list[str] | None:
    t = TITLE.match(ref.strip())
    if t:
        b = t[1].upper()
        return [f"{b} {t[2]}:title"] if b in books else None
    m = REF.match(ref.strip())
    if not m:
        return None
    book, ch, v1, v2, sub = m.groups()
    b = book.upper()
    if b not in books:
        return None
    lo = int(v1)
    hi = int(v2) if v2 else lo
    return [f"{b} {ch}:{v}" + (sub or "") for v in range(lo, hi + 1)]


def derive(path: Path) -> tuple[set[tuple[str, str]], collections.Counter[str]]:
    books = org_books()
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    pairs: set[tuple[str, str]] = set()
    skipped: collections.Counter[str] = collections.Counter()
    i = 0
    while i < len(lines):
        names = [c.strip() for c in lines[i].split("\t")]
        if "Hebrew" in names and any(n.startswith("English KJV") for n in names):
            ie = next(k for k, n in enumerate(names) if n.startswith("English KJV"))
            ih = names.index("Hebrew")
            i += 1
            while i < len(lines) and not lines[i].startswith("$") \
                    and "Hebrew" not in [c.strip() for c in lines[i].split("\t")]:
                row = lines[i].split("\t")
                i += 1
                if len(row) <= max(ie, ih) or not row[0].strip() or row[0].startswith(" ") or "&" in row[ie]:
                    continue
                action, eng, heb = row[0].strip(), row[ie].strip(), row[ih].strip()
                if action.startswith(("#", "TEST")) or not eng or not heb:
                    continue
                if re.match(r"^(NoVerse|Absent|NotExist)", heb) or re.match(r"^(NoVerse|Absent)", eng):
                    continue
                e, h = expand(eng, books), expand(heb, books)
                if e is None or h is None:
                    if ";" in heb:
                        skipped["multi-verse subdivision (out of scope: baseline is single-verse)"] += 1
                        continue
                    skipped["unparsed or identity-suffix (.0/.1)"] += 1
                    if DEBUG:
                        print(f"[skip] line {i}: {action} eng={eng!r} heb={heb!r}")
                elif len(e) == 1 and e[0].endswith(":title"):
                    pairs.update((x, e[0]) for x in h)
                elif len(e) != len(h):
                    skipped["multi-verse subdivision (out of scope: baseline is single-verse)"] += 1
                    if DEBUG:
                        print(f"[skip] line {i}: {action} eng={eng!r} heb={heb!r}")
                else:
                    pairs.update(zip(h, e))
            continue
        i += 1
    return pairs, skipped


def norm(ref: str) -> str:
    return re.sub(r"\.\d+$", "", ref)


def action_for(src: str, std: str) -> str:
    return "Renumber title" if std.endswith(":title") else "Renumber verse"


MULTI_OUT = REPO_ROOT / "export" / "_vrs" / "map" / "org-to-eng.multiverse.json"


def verse_key(ref: str) -> tuple[str, int, int]:
    book, cv = ref.split(" ", 1)
    ch, v = cv.split(":")
    return book, int(ch), int(v)


def contiguous(a: str, b: str) -> bool:
    ka, kb = verse_key(a), verse_key(b)
    if ka[0] != kb[0]:
        return False
    if ka[1] == kb[1]:
        return kb[2] == ka[2] + 1
    return kb[1] == ka[1] + 1 and kb[2] == 1 and ka[2] == _last_verse(ka[0], ka[1])


def _last_verse(book: str, ch: int) -> int:
    return LAST_VERSE[(book, ch)]


def range_ref(refs: list[str]) -> str:
    first, last = refs[0], refs[-1]
    if first == last:
        return first
    fb, fc, fv = verse_key(first)
    lb, lc, lv = verse_key(last)
    if fc == lc:
        return f"{fb} {fc}:{fv}-{lv}"
    return f"{fb} {fc}:{fv}-{lc}:{lv}"


def multiverse_relations(path: Path, single: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """One-to-many and many-to-one relations, as org range -> eng range records.

    Returns (accepted, flagged). Flagged rows are not contiguous ranges and need a
    decision before they can be published.
    """
    books = org_books()
    lines = path.read_text(encoding="utf-8-sig").split("\n")
    rel_ref = re.compile(r"^([0-9A-Za-z]+)\.(\d+):(\d+)(?:-(\d+))?([a-z])?$")
    absent = re.compile(r"^Absent \[=([0-9A-Za-z]+\.\d+:\d+)\]")

    def is_header(line: str) -> bool:
        names = [c.strip() for c in line.split("\t")]
        return "Hebrew" in names and any(n.startswith("English KJV") for n in names)

    def verses(ref: str) -> list[str] | None:
        m = rel_ref.match(ref.strip())
        if not m:
            return None
        b, ch, v1, v2, _ = m.groups()
        if b.upper() not in books:
            return None
        lo, hi = int(v1), int(v2) if v2 else int(v1)
        return [f"{b.upper()} {ch}:{v}" for v in range(lo, hi + 1)]

    def heb_list(heb: str) -> list[str] | None:
        parts = [x.strip() for x in heb.split(";")]
        out = verses(parts[0])
        if out is None:
            return None
        book, _ = rel_ref.match(parts[0]).group(1, 2)
        for x in parts[1:]:
            m = re.match(r"^(\d+):(\d+)(?:-(\d+))?$", x)
            if not m:
                return None
            hi = int(m.group(3)) if m.group(3) else int(m.group(2))
            out += [f"{book.upper()} {m.group(1)}:{v}" for v in range(int(m.group(2)), hi + 1)]
        return out

    cands: list[tuple[int, str, list[str], list[str], str, str]] = []
    merges: list[tuple[int, str, str, str]] = []
    i, n = 0, len(lines)
    while i < n:
        if not is_header(lines[i]):
            i += 1
            continue
        names = [c.strip() for c in lines[i].split("\t")]
        ie = next(k for k, c in enumerate(names) if c.startswith("English KJV"))
        ih = names.index("Hebrew")
        j = i + 1
        while j < n and not lines[j].startswith("$") and not is_header(lines[j]):
            row = lines[j].split("\t")
            if len(row) > max(ie, ih):
                act, eng, heb = row[0].strip(), row[ie].strip(), row[ih].strip()
                if act and not act.startswith(("#", "TEST")) and eng and heb and "&" not in eng:
                    m = absent.match(heb)
                    if m and rel_ref.match(eng):
                        merges.append((j + 1, act, eng, m.group(1)))
                    elif not re.match(r"^(NoVerse|Absent|NotExist)", heb) and not re.match(r"^(NoVerse|Absent)", eng):
                        e, h = verses(eng), heb_list(heb)
                        if e and h and len(e) != len(h) and not (len(e) == 1 and e[0].endswith(":title")):
                            cands.append((j + 1, act, e, h, eng, heb))
            j += 1
        i = j

    accepted: list[dict] = []
    flagged: list[dict] = []
    for line, act, e, h, eng, heb in cands:
        if len(e) == 1:
            accepted.append({"s": range_ref(h), "t": e[0], "line": line, "action": act})
        else:
            flagged.append({"line": line, "reason": "one-to-many not expressed here", "eng": eng, "heb": heb})

    for line, act, eng, anchor_raw in merges:
        merged = verses(eng)
        anchor_list = verses(anchor_raw)
        anchor = anchor_list[0] if anchor_list else anchor_raw
        if not merged:
            flagged.append({"line": line, "reason": "merge row unparsed", "eng": eng, "heb": anchor})
            continue
        partner = single.get(anchor)
        if partner is None:
            flagged.append({"line": line, "reason": "no single-verse partner", "eng": eng, "heb": anchor})
            continue
        pair = sorted({partner, merged[0]}, key=verse_key)
        if len(pair) == 2 and contiguous(pair[0], pair[1]):
            accepted.append({"s": anchor, "t": range_ref(pair), "line": line, "action": act})
        else:
            flagged.append({"line": line, "reason": "merged verses not contiguous (not expressible as a range)",
                            "eng": eng, "heb": anchor, "partner": partner})
    return accepted, flagged


def write_multiverse(path: Path) -> None:
    pairs, _ = derive(path)
    single: dict[str, str] = {}
    counts: dict[str, int] = {}
    for h, e in pairs:
        counts[h] = counts.get(h, 0) + 1
        single[h] = e
    single = {h: e for h, e in single.items() if counts[h] == 1}
    accepted, flagged = multiverse_relations(path, single)
    MULTI_OUT.parent.mkdir(parents=True, exist_ok=True)
    MULTI_OUT.write_text(json.dumps({
        "source_scheme": "org",
        "target_scheme": "eng",
        "kind": "multi-verse relations (not in the single-verse map)",
        "authority": "TVTMS — Translators Versification Traditions, STEPBible-Data (CC BY 4.0)",
        "attribution": "https://STEPBible.org",
        "tvtms_rev": TVTMS_COMMIT,
        "tvtms_sha256": TVTMS_SHA256,
        "map": [{"s": r["s"], "t": r["t"]} for r in accepted],
        "evidence": [{"s": r["s"], "t": r["t"], "tvtms_line": r["line"], "tvtms_action": r["action"]} for r in accepted],
        "flagged_not_published": flagged,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[tvtms] multi-verse: {len(accepted)} relations -> {MULTI_OUT.relative_to(REPO_ROOT)}; flagged {len(flagged)}")


ORGW_VRS = REPO_ROOT / "data" / "vrs" / "orgw.vrs"
ENG_VRS = REPO_ROOT / "data" / "vrs" / "eng.vrs"
ORGW_OUT = REPO_ROOT / "data" / "vrs" / "tvtms-orgw-to-eng.derived.tsv"
# Org-chaptering artifacts: TVTMS places these Hebrew Joel verses in org chapter 3, but
# orgw keeps Joel 3:1-5 as English 3:1-5, so the org->eng pairing is not valid for orgw.
# Same five rows the strongs-aligner orgw baseline excluded (fixed 2026-09-05).
ORGW_EXCLUDE_SOURCES = {f"JOL 3:{v}" for v in range(1, 6)}


def _shape(path: Path) -> dict[str, dict[int, int]]:
    out: dict[str, dict[int, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        book, *chapters = line.split()
        out[book.upper()] = {int(c): int(v) for c, v in (t.split(":") for t in chapters)}
    return out


def _valid(ref: str, shape: dict[str, dict[int, int]]) -> bool:
    m = re.match(r"^(\S+) (\d+):(\d+)$", ref)
    if not m:
        return False
    b, c, v = m.group(1), int(m.group(2)), int(m.group(3))
    return b in shape and c in shape[b] and 1 <= v <= shape[b][c]


def _valid_target(ref: str, shape: dict[str, dict[int, int]]) -> bool:
    if ref.endswith(":title"):
        m = re.match(r"^(\S+) (\d+):title$", ref)
        return bool(m) and m.group(1) in shape and int(m.group(2)) in shape[m.group(1)]
    return _valid(ref, shape)


def _orgw_chaptering_artifact(ref: str) -> bool:
    """Hebrew-chaptering rows that orgw's English-style chapters do not use (partner, text-free
    structural check against orgw.vrs): Numbers 17:1-13 and 1 Kings 5:1-18."""
    return ref.startswith("NUM 17:") and int(ref.split(":")[1]) <= 13 \
        or ref.startswith("1KI 5:") and int(ref.split(":")[1]) <= 18


def derive_orgw(pairs: set[tuple[str, str]]) -> list[tuple[str, str]]:
    """orgw = org's Hebrew-column pairs restricted to refs valid in orgw.vrs and eng.vrs.

    Verified against the strongs-aligner orgw baseline: 1,794 shared non-identity rows;
    the remaining differences are the 62 Daniel rows (the intended fix), PSA 13:6, and
    the excluded JOL rows above.
    """
    ow, eng = _shape(ORGW_VRS), _shape(ENG_VRS)
    identity_books = {b for b in ow if b in eng and ow[b] == eng[b]}
    rows = {(a, b) for a, b in pairs
            if _valid(a, ow) and _valid_target(b, eng) and a not in ORGW_EXCLUDE_SOURCES
            and a.split()[0] not in identity_books and a.split()[0] != "DAN"
            and not _orgw_chaptering_artifact(a)}
    return sorted((a, b) for a, b in rows if a != b)


def write_orgw() -> None:
    pairs, _ = derive(fetch_pinned())
    rows = derive_orgw({(norm(a), norm(b)) for a, b in pairs})
    ORGW_OUT.write_text(
        f"# DERIVED from TVTMS at {TVTMS_COMMIT} (sha256 {TVTMS_SHA256}) by "
        f"pipeline/core/derive_tvtms_org_eng.py (orgw). TVTMS is CC BY 4.0, STEPBible.org.\n"
        "source_ref\tstandard_ref\taction\n"
        + "".join(f"{a}\t{b}\t{action_for(a, b)}\n" for a, b in rows),
        encoding="utf-8")
    print(f"[tvtms] orgw: {len(rows)} non-identity rows -> {ORGW_OUT.relative_to(REPO_ROOT)}")


RSO_VRS = REPO_ROOT / "data" / "vrs" / "rso.vrs"
RSO_OUT = REPO_ROOT / "data" / "vrs" / "tvtms-rso-to-eng.derived.tsv"
# Hebrew-only books (TVTMS Greek/Latin columns carry Greek additions for these).
RSO_EXCLUDE_BOOKS: set[str] = set()


def column_pairs(path: Path, colname: str) -> set[tuple[str, str]]:
    """Pairs from TVTMS's English KJV column against one exact-named tradition column."""
    lines = path.read_text(encoding="utf-8-sig").split("\n")
    books = org_books()
    pairs: set[tuple[str, str]] = set()
    i, n = 0, len(lines)
    while i < n:
        names = [c.strip() for c in lines[i].split("\t")]
        if "English KJV" in names and colname in names:
            ie, ic = names.index("English KJV"), names.index(colname)
            j = i + 1
            while j < n and not lines[j].startswith("$") and "English KJV" not in [c.strip() for c in lines[j].split("\t")]:
                row = lines[j].split("\t")
                if len(row) > max(ie, ic):
                    act, eng, src = row[0].strip(), row[ie].strip(), row[ic].strip()
                    if act and not act.startswith(("#", "TEST")) and eng and src and "&" not in eng \
                            and not re.match(r"^(NoVerse|Absent|NotExist)", src) \
                            and not re.match(r"^(NoVerse|Absent)", eng):
                        e, h = expand(eng, books), expand(src, books)
                        if e and h and len(e) == len(h):
                            pairs.update(zip(h, e))
                        elif e and h and len(e) == 1 and e[0].endswith(":title"):
                            pairs.update((x, e[0]) for x in h)
                j += 1
            i = j
            continue
        i += 1
    return pairs


def section_pairs(path: Path, label_ok) -> set[tuple[str, str]]:
    """Pairs from TVTMS's labelled sections, where a row reads [label, tradition ref, English ref].

    label_ok(label) selects tradition sections by their exact '+'-separated parts. The
    tradition reference is the source (Synodal numbering) and the English reference the
    target. Merged/kept rows are skipped; counts must match for a single pair.
    """
    books = org_books()
    out: set[tuple[str, str]] = set()
    for ln in path.read_text(encoding="utf-8-sig").split("\n"):
        c = ln.split("\t")
        if len(c) < 4:
            continue
        lab = c[0].strip()
        if not lab or lab.startswith(("$", "#", "TEST", "BIBLES", "English")) or not label_ok(lab):
            continue
        if c[3].strip().startswith(("Keep", "MergedPrev", "MergedFoll")):
            continue
        src, eng = expand(c[1].strip(), books), expand(c[2].strip(), books)
        if src and eng and len(src) == len(eng):
            out.update(zip(src, eng))
    return out


def _same_length_chapter(ref: str, same_length: set[tuple[str, int]]) -> bool:
    book, cv = ref.split(" ", 1)
    return (book, int(cv.split(":")[0])) in same_length


def _has_part(label: str, part: str) -> bool:
    return part in label.split("+")


def derive_rso(path: Path) -> tuple[list[tuple[str, str]], dict]:
    """rso = TVTMS's labelled Greek sections as base, with these overrides:
    - Bulgarian column rows for Job 39-41 only;
    - Slavonic section rows for Joshua and Leviticus only (source = Slavonic reference);
    - a documented text override, LEV 14:56 -> 14:57 (Synodal text, see provenance);
    - identity-shaped chapters (Synodal and English chapter the same length) get no rows;
    - Daniel and Esther excluded; Joel 3:1-5 excluded;
    - every source valid in rso.vrs, every target valid in eng.vrs.
    """
    rso, eng = _shape(RSO_VRS), _shape(ENG_VRS)
    # Psalms 10-147 are numbered one lower in Synodal (Septuagint psalter), so the
    # same-length test compares the wrong chapters there; it is applied to other books only.
    same_length = {(b, c) for b in rso if b in eng and b != "PSA" for c in rso[b]
                   if c in eng[b] and rso[b][c] == eng[b][c]}
    base = section_pairs(path, lambda lab: _has_part(lab, "Greek"))
    job_bulgarian = {(a, b) for a, b in column_pairs(path, "Bulgarian")
                     if a.startswith("JOB ") and int(a.split()[1].split(":")[0]) in (39, 40, 41)}
    slav = {(a, b) for a, b in section_pairs(path, lambda lab: _has_part(lab, "Slavonic"))
            if a.split()[0] in ("JOS", "LEV")}
    text_overrides = {("LEV 14:56", "LEV 14:57"),  # Synodal 14:56 = English 14:57 (text-checked)
                      ("PSA 12:6", "PSA 13:5"),     # Synodal 12:6 = English 13:5-6; first verse here, range in multi file
                      ("ROM 14:24", "ROM 16:25"),   # moved doxology, text-checked by partner
                      ("ROM 14:25", "ROM 16:26"),
                      ("ROM 14:26", "ROM 16:27"),
                      ("PSA 114:9", "PSA 116:9"),  # partner, Russian text
                      *[(f"PRO 13:{n}", f"PRO 13:{n-1}") for n in range(15, 27)],  # Septuagint addition at 13:14
                      *[(f"SNG 1:{n}", f"SNG 1:{n+1}") for n in range(1, 17)],     # English 1:1 unnumbered in Synodal
                      *[(f"ISA 3:{n}", f"ISA 3:{n+1}") for n in range(20, 26)]}   # 3:19 is a multi-verse relation
    hebrew_pairs, _ = derive(path)
    daniel_hebrew = {(norm(a), norm(b)) for a, b in hebrew_pairs
                     if norm(a).startswith(("DAN 3:", "DAN 4:")) and norm(a) != norm(b)}
    overridden = {a for a, _ in job_bulgarian | slav | text_overrides}
    merged = ({(a, b) for a, b in base if a not in overridden and not a.startswith("DAN ")} | job_bulgarian | slav
              | text_overrides | daniel_hebrew)
    rows = {(a, b) for a, b in merged
            if not _same_length_chapter(a, same_length)
            and a.split()[0] not in RSO_EXCLUDE_BOOKS and a not in ORGW_EXCLUDE_SOURCES
            and _valid(a, rso) and _valid_target(b, eng)}
    targets = collections.Counter(b for a, b in rows if a != b and not b.endswith(":title"))
    report = {"base_pairs": len(base), "job_bulgarian": len(job_bulgarian), "slavonic": len(slav),
              "text_overrides": len(text_overrides), "rows": len(rows),
              "identity": sum(1 for a, b in rows if a == b),
              "collisions": sum(1 for v in targets.values() if v > 1)}
    return sorted((a, b) for a, b in rows if a != b), report


def write_rso(path: Path) -> None:
    rows, report = derive_rso(path)
    if report["collisions"]:
        raise SystemExit(f"[rso] {report['collisions']} English verses hit by 2+ Synodal verses; refusing to write")
    RSO_OUT.write_text(
        f"# DERIVED from TVTMS at {TVTMS_COMMIT} (sha256 {TVTMS_SHA256}) by "
        f"pipeline/core/derive_tvtms_org_eng.py (rso: Greek base + Bulgarian overrides). "
        f"TVTMS is CC BY 4.0, STEPBible.org.\n"
        "source_ref\tstandard_ref\taction\n"
        + "".join(f"{a}\t{b}\t{action_for(a, b)}\n" for a, b in rows),
        encoding="utf-8")
    print(f"[tvtms] rso: {len(rows)} non-identity rows, report {report} -> {RSO_OUT.relative_to(REPO_ROOT)}")


VUL_VRS = REPO_ROOT / "data" / "vrs" / "vul.vrs"
VUL_OUT = REPO_ROOT / "data" / "vrs" / "tvtms-vul-to-eng.derived.tsv"
NT_BOOKS = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL",
            "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN",
            "3JN", "JUD", "REV"}


def _title_pair(a: str, b: str, src: dict, eng: dict) -> bool:
    """A psalm-title-to-psalm-title row whose psalms exist on both sides (e.g. Vulgate
    PSA 118:title -> English PSA 119:title); _valid() takes verse references only."""
    ma, mb = re.match(r"^PSA (\d+):title$", a), re.match(r"^PSA (\d+):title$", b)
    return bool(ma and mb and int(ma.group(1)) in src.get("PSA", {}) and int(mb.group(1)) in eng.get("PSA", {}))


def derive_vul(path: Path) -> tuple[list[tuple[str, str]], dict]:
    """vul = TVTMS's labelled Latin sections, Old Testament and deuterocanon only (the
    New Testament stays out of scope, decided 2026-10-05), every source valid in vul.vrs
    and every target valid in eng.vrs.

    Unlike rso, chapters of the same length on both sides are NOT skipped: the Vulgate
    reorders verses inside such chapters (EXO 39, 43 verses on both sides, has 17 real
    renumberings; also ISA 45 and SIR 6/14/18). The first, unpinned derivation applied
    the rso rule and lost those rows; checked 2026-10-09 against the strongs-aligner
    baseline it replaces: every baseline row is kept, with the same target.
    """
    vul, eng = _shape(VUL_VRS), _shape(ENG_VRS)
    pairs = section_pairs(path, lambda lab: _has_part(lab, "Latin"))
    rows = {(a, b) for a, b in pairs
            if a != b and a.split()[0] not in NT_BOOKS
            and ((_valid(a, vul) and _valid_target(b, eng)) or _title_pair(a, b, vul, eng))}
    sources = collections.Counter(a for a, _ in rows)
    targets = collections.Counter(b for _, b in rows if not b.endswith(":title"))
    report = {"latin_pairs": len(pairs), "rows": len(rows),
              "sources_mapped_twice": sum(1 for v in sources.values() if v > 1),
              "collisions": sum(1 for v in targets.values() if v > 1)}
    return sorted(rows), report


def write_vul(path: Path) -> None:
    rows, report = derive_vul(path)
    if report["collisions"] or report["sources_mapped_twice"]:
        raise SystemExit(f"[vul] not one-to-one: {report}; refusing to write")
    VUL_OUT.write_text(
        f"# DERIVED from TVTMS at {TVTMS_COMMIT} (sha256 {TVTMS_SHA256}) by "
        f"pipeline/core/derive_tvtms_org_eng.py (vul: Latin sections; Old Testament and "
        f"deuterocanon only, New Testament excluded by decision 2026-10-05). "
        f"TVTMS is CC BY 4.0, STEPBible.org.\n"
        "source_ref\tstandard_ref\taction\n"
        + "".join(f"{a}\t{b}\t{action_for(a, b)}\n" for a, b in rows),
        encoding="utf-8")
    print(f"[tvtms] vul: {len(rows)} non-identity rows, report {report} -> {VUL_OUT.relative_to(REPO_ROOT)}")


LXX_VRS = REPO_ROOT / "data" / "vrs" / "lxx.vrs"
LXX_OUT = REPO_ROOT / "data" / "vrs" / "tvtms-lxx-to-eng.derived.tsv"
# Chapters where TVTMS's second Greek edition (`Greek2` sections) fits lxx.vrs better
# than the main one (`Greek`). Chosen 2026-10-09 by applying each edition as a full
# map to every verse of lxx.vrs and counting collisions and invalid targets, book by
# book and chapter by chapter (internal-docs/versification-index-followups-2026-10-08.md).
LXX_GREEK2_CHAPTERS = {("MAL", 3), ("JER", 34), ("4MA", 7), ("4MA", 8), ("4MA", 12)}
_LXX_REF = re.compile(r"^(\S+) (\d+):(\d+)$")


def _in_lxx(ref: str) -> tuple[str, int, int] | None:
    """A TVTMS Greek source reference in lxx.vrs coordinates, using the same book rules
    as data/vrs/crosswalk-lxx.toml (applied by generate_vrs_map.py; the derived rows keep
    TVTMS's own codes): DAN -> DAG, NEH -> EZR chapter + 10, 2CH 37 -> MAN 1."""
    m = _LXX_REF.match(ref)
    if not m:
        return None
    book, c, v = m.group(1), int(m.group(2)), int(m.group(3))
    if book == "DAN":
        return "DAG", c, v
    if book == "NEH":
        return "EZR", c + 10, v
    if book == "2CH" and c == 37:
        return "MAN", 1, v
    return book, c, v


def _offset(a: str, b: str) -> tuple[int, int] | None:
    ma, mb = _LXX_REF.match(a), _LXX_REF.match(b)
    if not (ma and mb) or ma.group(1) != mb.group(1):
        return None
    return int(mb.group(2)) - int(ma.group(2)), int(mb.group(3)) - int(ma.group(3))


def derive_lxx(path: Path) -> tuple[list[tuple[str, str]], dict]:
    """lxx = TVTMS's `Greek` sections, with `Greek2` for LXX_GREEK2_CHAPTERS, Old
    Testament and deuterocanon. Rows keep TVTMS's book codes; crosswalk-lxx.toml maps
    them to lxx.vrs codes and drops non-Greek books, as it did for the baseline.

    Targets must be valid in eng.vrs. Sources must be in a chapter lxx.vrs has; a verse
    past the end of that chapter is kept (TVTMS is the authority; generate_vrs_map lists
    such rows as shape exceptions). Where TVTMS gives one verse two targets (from
    different sections), the one with the same offset as its nearest unambiguous
    neighbours wins (a verse without a row counts as identity), then the chapter's most
    common offset: EXO 40:28 -> 40:34 (40:27 -> 40:33, 40:29 -> 40:35), NEH 4:6 -> 4:12.
    Greek Esther stays in the hand-curated supplement (esg-lxx-to-eng.tsv).
    """
    lxx, eng = _shape(LXX_VRS), _shape(ENG_VRS)
    chapter = lambda ref: (ref.split()[0], int(ref.split()[1].split(":")[0]))  # noqa: E731

    def usable(a: str, b: str) -> bool:
        # verse -> verse, or verse -> psalm title (the Septuagint numbers a psalm's title
        # as its verse 1: PSA 3:1 -> PSA 3:title), or title -> title
        pos = _in_lxx(a)
        if not pos:
            return _title_pair(a, b, lxx, eng)
        return pos[0] not in NT_BOOKS and pos[1] in lxx.get(pos[0], {}) and _valid_target(b, eng)

    greek = section_pairs(path, lambda lab: _has_part(lab, "Greek"))
    greek2 = section_pairs(path, lambda lab: _has_part(lab, "Greek2"))
    pairs = ({(a, b) for a, b in greek if chapter(a) not in LXX_GREEK2_CHAPTERS}
             | {(a, b) for a, b in greek2 if chapter(a) in LXX_GREEK2_CHAPTERS})
    pairs = {(a, b) for a, b in pairs if usable(a, b)}
    targets_of = collections.defaultdict(set)
    for a, b in pairs:
        targets_of[a].add(b)
    def offset_at(book: str, c: int, v: int) -> tuple[int, int] | None:
        """Offset of an unambiguous verse: its single row, or identity if it has none."""
        ts = targets_of.get(f"{book} {c}:{v}")
        if ts is None:
            return (0, 0)
        return _offset(f"{book} {c}:{v}", next(iter(ts))) if len(ts) == 1 else None

    resolved = {}
    for a, ts in targets_of.items():
        if len(ts) == 1:
            resolved[a] = next(iter(ts))
            continue
        # the nearest unambiguous verse on each side of it, within the chapter, decides;
        # the chapter's prevailing offset breaks a tie
        book, cv = a.split(" ", 1)
        c, v = (int(x) for x in cv.split(":"))
        pos = _in_lxx(a)
        length = lxx.get(pos[0], {}).get(pos[1], 0) if pos else 0
        near = []
        for step in (-1, 1):
            w = v + step
            while 1 <= w <= max(length, v):
                o = offset_at(book, c, w)
                if o is not None:
                    near.append(o)
                    break
                w += step
        chapter_votes = collections.Counter(
            _offset(x, next(iter(xs))) for x, xs in targets_of.items()
            if chapter(x) == chapter(a) and len(xs) == 1)
        resolved[a] = max(sorted(ts), key=lambda t: (near.count(_offset(a, t)),
                                                    chapter_votes.get(_offset(a, t), 0)))
    rows = {(a, b) for a, b in resolved.items() if a != b}
    sources = collections.Counter(a for a, _ in rows)
    targets = collections.Counter(b for _, b in rows if not b.endswith(":title"))
    report = {"greek_pairs": len(greek), "greek2_pairs": len(greek2), "rows": len(rows),
              "resolved_two_targets": sum(1 for ts in targets_of.values() if len(ts) > 1),
              "outside_lxx_shape": sum(1 for a, _ in rows if (p := _in_lxx(a)) and not
                                       (1 <= p[2] <= lxx.get(p[0], {}).get(p[1], 0))),
              "sources_mapped_twice": sum(1 for v in sources.values() if v > 1),
              "collisions": sum(1 for v in targets.values() if v > 1)}
    return sorted(rows), report


def write_lxx(path: Path) -> None:
    rows, report = derive_lxx(path)
    if report["collisions"] or report["sources_mapped_twice"]:
        raise SystemExit(f"[lxx] not one-to-one: {report}; refusing to write")
    LXX_OUT.write_text(
        f"# DERIVED from TVTMS at {TVTMS_COMMIT} (sha256 {TVTMS_SHA256}) by "
        f"pipeline/core/derive_tvtms_org_eng.py (lxx: Greek sections, Greek2 for "
        f"{', '.join(f'{b} {c}' for b, c in sorted(LXX_GREEK2_CHAPTERS))}; Old Testament and "
        f"deuterocanon; TVTMS book codes, mapped by crosswalk-lxx.toml). TVTMS is CC BY 4.0, STEPBible.org.\n"
        "source_ref\tstandard_ref\taction\n"
        + "".join(f"{a}\t{b}\t{action_for(a, b)}\n" for a, b in rows),
        encoding="utf-8")
    print(f"[tvtms] lxx: {len(rows)} non-identity rows, report {report} -> {LXX_OUT.relative_to(REPO_ROOT)}")


def section_multiverse(path: Path, label_of, src_shape: dict, single_sources: set,
                       to_scheme=lambda ref: ref) -> tuple[list[dict], list[dict]]:
    """Multi-verse relations from TVTMS's labelled sections: rows where the tradition
    side and the English side have different verse counts (several verses into one,
    or one into several), which a single-verse map can't hold.

    label_of(chapter) -> the section label part to read for that source chapter
    (e.g. "Latin"; for lxx, "Greek" or "Greek2"). Rows marking part of a verse
    (`!a`, `!b`) are skipped: the matching whole-range row says the same. Published
    when one side is a single verse and the other a range within one chapter; flagged
    (not published) for range-to-range relations and for sources the single-verse map
    already maps.
    """
    books = org_books()
    eng = _shape(ENG_VRS)
    accepted, flagged = [], []
    for n, ln in enumerate(path.read_text(encoding="utf-8-sig").split("\n"), 1):
        c = ln.split("\t")
        if len(c) < 4:
            continue
        lab = c[0].strip()
        if not lab or lab.startswith(("$", "#", "TEST", "BIBLES", "English")):
            continue
        src_raw, eng_raw, act = c[1].strip(), c[2].strip(), c[3].strip()
        if "!" in src_raw or "!" in eng_raw or act.startswith(("Keep", "MergedPrev", "MergedFoll")):
            continue
        src, tgt = expand(src_raw, books), expand(eng_raw, books)
        if not src or not tgt or len(src) == len(tgt):
            continue
        src, tgt = [to_scheme(norm(x)) for x in src], [norm(x) for x in tgt]
        chapter = (src[0].split()[0], int(src[0].split()[1].split(":")[0]))
        part = label_of(chapter)
        if not part or not _has_part(lab, part) or src[0].split()[0] in NT_BOOKS:
            continue
        rec = {"tvtms_line": n, "tvtms_action": act, "source": src_raw, "english": eng_raw}
        if not all(_valid(x, src_shape) for x in src) or not all(_valid_target(t, eng) for t in tgt):
            flagged.append({**rec, "reason": "outside our shapes"})
        elif len(src) > 1 and len(tgt) > 1:
            flagged.append({**rec, "reason": "range-to-range (verse order differs; not expressed here)"})
        elif any(x in single_sources for x in src):
            flagged.append({**rec, "reason": "a source verse already has a single-verse row"})
        else:
            rng = lambda xs: xs[0] if len(xs) == 1 else f"{xs[0]}-{xs[-1].split(':')[1]}"  # noqa: E731
            accepted.append({"s": rng(src), "t": rng(tgt), **rec})
    # one relation per source range
    seen, unique = set(), []
    for r in accepted:
        if r["s"] not in seen:
            seen.add(r["s"])
            unique.append(r)
    return unique, flagged


def write_section_multiverse(path: Path, scheme: str, rows: list, label_of, src_shape: dict,
                             to_scheme=lambda ref: ref) -> None:
    single_sources = {to_scheme(a) for a, _ in rows}
    accepted, flagged = section_multiverse(path, label_of, src_shape, single_sources, to_scheme)
    out = REPO_ROOT / "export" / "_vrs" / "map" / f"{scheme}-to-eng.multiverse.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "source_scheme": scheme,
        "target_scheme": "eng",
        "kind": "multi-verse relations (not in the single-verse map)",
        "authority": "TVTMS — Translators Versification Traditions, STEPBible-Data (CC BY 4.0)",
        "attribution": "https://STEPBible.org",
        "tvtms_rev": TVTMS_COMMIT,
        "tvtms_sha256": TVTMS_SHA256,
        "map": [{"s": r["s"], "t": r["t"]} for r in accepted],
        "evidence": [{"s": r["s"], "t": r["t"], "tvtms_line": r["tvtms_line"],
                      "tvtms_action": r["tvtms_action"]} for r in accepted],
        "flagged_not_published": flagged,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[tvtms] {scheme} multi-verse: {len(accepted)} relations -> {out.relative_to(REPO_ROOT)}; flagged {len(flagged)}")


def write_vul_lxx_multiverse(path: Path) -> None:
    vul_rows, _ = derive_vul(path)
    write_section_multiverse(path, "vul", vul_rows, lambda ch: "Latin", _shape(VUL_VRS))
    lxx_rows, _ = derive_lxx(path)

    def lxx_code(ref: str) -> str:
        pos = _in_lxx(ref)
        return f"{pos[0]} {pos[1]}:{pos[2]}" if pos else ref

    def lxx_label(ch):  # ch is in lxx coordinates here; LXX_GREEK2_CHAPTERS uses TVTMS's
        return "Greek2" if ch in LXX_GREEK2_CHAPTERS else "Greek"
    write_section_multiverse(path, "lxx", lxx_rows, lxx_label, _shape(LXX_VRS), lxx_code)


def main() -> None:
    path = fetch_pinned()
    if "--check" in sys.argv:
        print(f"[tvtms] pinned input verified: {TVTMS_COMMIT} sha256={TVTMS_SHA256}")
        return
    pairs, skipped = derive(path)
    rows = sorted({(norm(a), norm(b)) for a, b in pairs if norm(a) != norm(b)},
                  key=lambda x: (x[0].split()[0], x[0]))
    header = (f"# DERIVED from TVTMS at {TVTMS_COMMIT} (sha256 {TVTMS_SHA256}) by "
              f"pipeline/core/derive_tvtms_org_eng.py. TVTMS is CC BY 4.0, STEPBible.org.\n")
    OUT_TSV.write_text(header + "source_ref\tstandard_ref\taction\n" +
                       "".join(f"{a}\t{b}\t{action_for(a, b)}\n" for a, b in rows),
                       encoding="utf-8")
    PROVENANCE.write_text(json.dumps({
        "source": "STEPBible-Data TVTMS",
        "licence": "CC BY 4.0",
        "attribution": "https://STEPBible.org",
        "commit": TVTMS_COMMIT,
        "input_path": TVTMS_PATH,
        "input_sha256": TVTMS_SHA256,
        "output": OUT_TSV.name,
        "output_sha256": sha256(OUT_TSV),
        "rows": len(rows),
        "skipped": dict(skipped),
        "deriver": "pipeline/core/derive_tvtms_org_eng.py",
    }, indent=2) + "\n", encoding="utf-8")
    write_multiverse(path)
    write_orgw()
    write_rso(path)
    write_vul(path)
    write_lxx(path)
    write_vul_lxx_multiverse(path)
    write_nt_fixes()
    print(f"[tvtms] derived {len(rows)} non-identity org->eng rows -> {OUT_TSV.relative_to(REPO_ROOT)}")
    print(f"[tvtms] skipped: {dict(skipped)}")


if __name__ == "__main__":
    main()
