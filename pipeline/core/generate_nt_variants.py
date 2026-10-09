#!/usr/bin/env python3
"""Build _vrs/map/nt-variants.json: the New Testament numbering variants TVTMS defines,
each mapped to our eng.vrs.

TVTMS describes New Testament variation as test blocks: a header naming traditions
(columns), `TEST` rows ("if REV 12:17 is the last verse, the Bible follows this
column"), then rows aligning the same text across the columns. A cell is a reference,
a range, a part of a verse (`12:17a`), or `Absent [=X]` (the text is inside verse X in
that tradition).

For every renumbering test (`<ref>=Last`) whose value differs from eng.vrs, the column
with that value is a variant, named `<BOOK><chapter>-<last verse>` (e.g. REV12-17). Its
rows map that column's verses to the column whose last verse matches eng.vrs. Identity
rows are left out. Existence tests (a verse present or absent) and verse-order tests
are not variants: they don't change a chapter's length.

`profiles` names common sets of variants, after the traditions TVTMS names for them.

Usage:
    python3 pipeline/core/generate_nt_variants.py
"""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derive_tvtms_org_eng as tv  # noqa: E402
from paths import EXPORT, REPO_ROOT  # noqa: E402

OUT = EXPORT / "_vrs" / "map" / "nt-variants.json"
ENG_VRS = REPO_ROOT / "data" / "vrs" / "eng.vrs"

# A second column with the same last verse but different rows gets its own id.
# REV 12 has 17 verses in both KJV/NIV (12:18's text starts 13:1) and ESV (it ends 12:17).
SUFFIX = {("REV", 12, "English3 (ESV etc)"): "esv"}

# Named sets of variants, after the TVTMS traditions they match. Chosen 2026-10-09 from
# the variant sets found across PKF, DBT and helloAO (1,132 editions with an `nt` entry;
# these five cover 834). Combinations with JHN7-52 (John 7:53 absent or merged) are left
# unnamed: that is a missing passage, not a numbering tradition.
PROFILES = {
    "kjv": {"variants": ["3JN1-14", "REV12-17"],
            "note": "KJV numbering: 3 John has 14 verses; Revelation 12 has 17 (12:18 starts 13:1)"},
    "niv": {"variants": ["REV12-17"],
            "note": "NIV numbering: Revelation 12 has 17 verses (12:18 starts 13:1)"},
    "esv": {"variants": ["REV12-17esv"],
            "note": "ESV numbering: Revelation 12 has 17 verses (12:18's text ends 12:17)"},
    "nrsv": {"variants": ["2CO13-13"],
             "note": "NRSV numbering: 2 Corinthians 13 has 13 verses (13:12 holds 13:12-13)"},
    "greek": {"variants": ["2CO13-13", "ACT19-40"],
              "note": "Greek (NA/UBS) numbering: also Acts 19 has 40 verses (19:40 holds 19:40-41)"},
}

_PART = re.compile(r"(\d+:\d+)[a-z]\b")


def _clean(cell: str) -> str:
    """Drop verse-part letters (12:17a -> 12:17) and bracketed notes."""
    cell = re.sub(r"\[.*?\]", "", cell).strip()
    return _PART.sub(r"\1", cell)


_CROSS = re.compile(r"^(\w+)\.(\d+):(\d+)\s*-{1,2}\s*(\d+):(\d+)$")


def _refs(cell: str, books, lengths=None) -> list[str]:
    """Verses in a cell. A range across a chapter break (Rev.12:18-13:1) runs to the end
    of the first chapter by `lengths` ({(BOOK, chapter): last verse} for this column)."""
    cell = _clean(cell)
    if not cell or cell.startswith(("Absent", "NotExist", "NoVerse")):
        return []
    m = _CROSS.match(cell)
    if m:
        first = tv.expand(f"{m.group(1)}.{m.group(2)}:{m.group(3)}", books)
        if not first:
            return []
        book, c1, v1, c2, v2 = first[0].split()[0], int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        end = (lengths or {}).get((book, c1), v1)
        return ([f"{book} {c1}:{v}" for v in range(v1, max(v1, end) + 1)]
                + [f"{book} {c}:{v}" for c in range(c1 + 1, c2) for v in range(1, (lengths or {}).get((book, c), 0) + 1)]
                + [f"{book} {c2}:{v}" for v in range(1, v2 + 1)])
    return [tv.norm(r) for r in (tv.expand(cell, books) or [])]


def _merged_into(cell: str, books) -> list[str]:
    """`Absent [=Act.19:40]` -> ['ACT 19:40']: the text is inside that verse."""
    m = re.match(r"^Absent\s*\[=(.+?)\]", cell.strip())
    return [tv.norm(r) for r in (tv.expand(_clean(m.group(1)), books) or [])] if m else []


def blocks(lines: list[str]):
    """Yield (header columns, test rows, data rows) for each TVTMS test block."""
    i, n = 0, len(lines)
    while i < n:
        c = [x.strip() for x in lines[i].split("\t")]
        if c[0].startswith("$") and i + 1 < n and lines[i + 1].startswith("TEST"):
            cols = [x for x in c[1:] if x]
            tests, rows, j = [], [], i + 1
            while j < n and lines[j].startswith("TEST"):
                tests.append([x.strip() for x in lines[j].split("\t")][1:1 + len(cols)])
                j += 1
            while j < n and lines[j].strip() and not lines[j].startswith(("$", "#")):
                r = [x.strip() for x in lines[j].split("\t")]
                rows.append((r[0], r[1:1 + len(cols)]))
                j += 1
            yield cols, tests, rows
            i = j
            continue
        i += 1


def main() -> None:
    lines = tv.fetch_pinned().read_text(encoding="utf-8-sig").split("\n")
    books = tv.org_books()
    eng = tv._shape(ENG_VRS)
    variants = {}
    for cols, tests, rows in blocks(lines):
        for test in tests:
            lasts = [re.match(r"^(\S+?)=Last$", t) for t in test]
            if not any(lasts):
                continue
            refs = [_refs(m.group(1), books)[0] if m and _refs(m.group(1), books) else None for m in lasts]
            known = [r for r in refs if r]
            if not known:
                continue
            book, chap = known[0].split()[0], int(known[0].split()[1].split(":")[0])
            if book not in tv.NT_BOOKS or chap not in eng.get(book, {}):
                continue
            last_of = lambda r: int(r.split(":")[1]) if r and r.split()[0] == book and int(r.split()[1].split(":")[0]) == chap else None  # noqa: E731
            eng_last = eng[book][chap]
            target = next((k for k, r in enumerate(refs) if last_of(r) == eng_last), None)
            if target is None:
                print(f"[nt-variants] {book} {chap}: no column matches eng.vrs ({eng_last}); skipped")
                continue
            seen = {}
            for k, r in enumerate(refs):
                last = last_of(r)
                if last is None or last == eng_last:
                    continue
                vid = f"{book}{chap}-{last}"
                sfx = SUFFIX.get((book, chap, cols[k]))
                if sfx:
                    vid += sfx
                elif vid in seen:
                    continue
                seen[vid] = k
                mp = collections.defaultdict(list)
                src_len = lambda col: {**{(b2, c2): n for b2, chs in eng.items() for c2, n in chs.items()},  # noqa: E731
                                       **({(book, chap): last_of(refs[col])} if last_of(refs[col]) else {})}
                kinds = set()
                for kind, cells in rows:
                    kinds.add(kind)
                    if len(cells) <= max(k, target):
                        continue
                    src, tgt = _refs(cells[k], books, src_len(k)), _refs(cells[target], books, src_len(target))
                    into = _merged_into(cells[k], books)
                    if kind == "PassageMissing" and not into and src != tgt:
                        continue  # a passage absent here: nothing is renumbered
                    if not src and into and tgt:  # text inside another verse here
                        for t in tgt:
                            if t not in mp[into[0]]:
                                mp[into[0]].append(t)
                        continue
                    if not src:
                        continue
                    if not tgt:
                        tgt = _merged_into(cells[target], books)
                    if not tgt:
                        continue
                    if len(src) == len(tgt):
                        pairs = zip(src, ([t] for t in tgt))
                    elif len(src) == 1:
                        pairs = [(src[0], tgt)]
                    else:
                        pairs = ((s, [tgt[0]]) for s in src) if len(tgt) == 1 else []
                    for s, ts in pairs:
                        for t in ts:
                            if t not in mp[s]:
                                mp[s].append(t)
                rows_out = [{"s": s, "t": ts} for s, ts in sorted(mp.items(), key=lambda x: tv.verse_key(x[0]))
                            if ts != [s]]
                variants[vid] = {"chapter": f"{book} {chap}", "detect": f"{book} {chap} has {last} verses",
                                 "tradition": cols[k],
                                 "kind": ("passage-absent" if not rows_out and kinds <= {"PassageMissing"}
                                          else "renumbering"),
                                 "map": rows_out}
    doc = {
        "target_scheme": "eng",
        "authority": "TVTMS — Translators Versification Traditions, STEPBible-Data (CC BY 4.0)",
        "attribution": "https://STEPBible.org",
        "tvtms_rev": tv.TVTMS_COMMIT,
        "note": "New Testament numbering variants, each mapped to eng.vrs. For an edition whose "
                "dbt/_vrs/index.json `nt` entry lists variants, take New Testament rows from those "
                "variants (identity elsewhere) instead of from its `l` scheme's map. A row maps the "
                "edition's verse s to one or more eng.vrs verses t.",
        "variants": dict(sorted(variants.items())),
        "profiles": PROFILES,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[nt-variants] {len(variants)} variants -> {OUT}")


if __name__ == "__main__":
    main()
