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


def derive_orgw(pairs: set[tuple[str, str]]) -> list[tuple[str, str]]:
    """orgw = org's Hebrew-column pairs restricted to refs valid in orgw.vrs and eng.vrs.

    Verified against the strongs-aligner orgw baseline: 1,794 shared non-identity rows;
    the remaining differences are the 62 Daniel rows (the intended fix), PSA 13:6, and
    the excluded JOL rows above.
    """
    ow, eng = _shape(ORGW_VRS), _shape(ENG_VRS)
    rows = {(a, b) for a, b in pairs
            if _valid(a, ow) and _valid_target(b, eng) and a not in ORGW_EXCLUDE_SOURCES}
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
    print(f"[tvtms] derived {len(rows)} non-identity org->eng rows -> {OUT_TSV.relative_to(REPO_ROOT)}")
    print(f"[tvtms] skipped: {dict(skipped)}")


if __name__ == "__main__":
    main()
