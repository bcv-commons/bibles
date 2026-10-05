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
    print(f"[tvtms] derived {len(rows)} non-identity org->eng rows -> {OUT_TSV.relative_to(REPO_ROOT)}")
    print(f"[tvtms] skipped: {dict(skipped)}")


if __name__ == "__main__":
    main()
