#!/usr/bin/env python3
"""Direct <scheme>-to-org maps: a scheme's verse numbers in the Hebrew (org) numbering, for
clients whose reference text is the Hebrew Old Testament (lexeme-aligner's spine, shoresh).

Built by composing maps we already publish, so every scheme keeps the fixes its
<scheme>-to-eng map has: X -> eng (X's map), then eng -> org (org's map, inverted). Going
through eng verse by verse loses information where several verses meet in one English
verse (a two-verse Psalm title, a merged or split verse), so verses are matched in groups:

  1. Each X verse and each org verse is linked to the eng verses it maps to (single-verse
     map, multi-verse relations, or identity).
  2. Verses that share an eng verse form one group (connected components).
  3. A group with as many X verses as org verses pairs them in order (PSA 51:1-2 of a
     scheme with numbered titles -> org PSA 51:1-2). One X verse and several org verses is
     a split; several X verses and one org verse is a merge; both go to the multiverse
     file. Anything else is flagged, not published.

The 39 books of the Hebrew Bible only: org is the Hebrew Old Testament's numbering, and New
Testament numbering is in nt-variants.json. Deuterocanonical books have no rows.

Writes export/_vrs/map/<scheme>-to-org.json and <scheme>-to-org.multiverse.json for eng,
orgw, catm, rso, vul and lxx.

Usage: python3 pipeline/core/generate_vrs_to_org.py
"""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import REPO_ROOT  # noqa: E402

MAP_DIR = REPO_ROOT / "export" / "_vrs" / "map"
VRS_DIR = REPO_ROOT / "export" / "_vrs"
SCHEMES = ["eng", "orgw", "catm", "rso", "vul", "lxx"]
# The Hebrew Bible's 39 books: the scope of org as a reference text. (Paratext's org.vrs
# also lists deuterocanonical books, but those aren't Hebrew Bible numbering.)
HEBREW_OT = {"GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA", "1KI", "2KI", "1CH",
             "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO", "ECC", "SNG", "ISA", "JER", "LAM", "EZK",
             "DAN", "HOS", "JOL", "AMO", "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL"}
NT = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL", "1TH",
      "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"}
REF = re.compile(r"^(\S+) (\d+):(\d+|title)$")


def shape(scheme: str) -> dict[str, dict[int, int]]:
    out: dict[str, dict[int, int]] = {}
    for line in (VRS_DIR / f"{scheme}.vrs").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if not parts or line.startswith("#") or not re.fullmatch(r"[0-9A-Z]{3}", parts[0]):
            continue
        out[parts[0]] = {int(c): int(v) for c, v in (p.split(":") for p in parts[1:] if ":" in p and "=" not in p)}
    return out


def verses_of(shp: dict[str, dict[int, int]], crosswalk: dict | None = None) -> list[str]:
    """The scheme's verses in Hebrew Bible books, judged by the book each chapter has in eng
    (lxx DAG is Daniel, its EZR 11-23 Nehemiah; its MAN is not in the Hebrew Bible)."""
    cw = crosswalk or {}
    return [f"{b} {c}:{v}" for b, chs in shp.items() for c, n in chs.items()
            if identity(f"{b} {c}:1", cw).split()[0] in HEBREW_OT for v in range(1, n + 1)]


def key(ref: str) -> tuple:
    b, c, v = REF.match(ref).groups()
    return b, int(c), -1 if v == "title" else int(v)


def expand(r: str, shp: dict[str, dict[int, int]]) -> list[str]:
    """'PSA 13:5-6', '1SA 20:42-21:1', 'NUM 25:19-26:1' -> the single verses, with chapter
    ends from `shp`, the shape of the scheme the range is in."""
    m = re.match(r"^(\S+) (\d+):(\d+)-(?:(\d+):)?(\d+)$", r)
    if not m:
        return [r]
    b, c1, v1, c2, v2 = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4), int(m.group(5))
    c2 = int(c2) if c2 else c1
    out = []
    for c in range(c1, c2 + 1):
        lo = v1 if c == c1 else 1
        hi = v2 if c == c2 else shp.get(b, {}).get(c, v1 if c == c1 else v2)
        out += [f"{b} {c}:{v}" for v in range(lo, hi + 1)]
    return out


def identity(ref: str, crosswalk: dict) -> str:
    """X's own ref as an eng ref when X has no row for it: the inverse of the map's book
    crosswalk (lxx DAG -> DAN, EZR 11-23 -> NEH 1-13, MAN 1 -> 2CH 37), else unchanged."""
    b, c, v = REF.match(ref).groups()
    for eng_book, rule in crosswalk.items():
        if rule["to"] != b:
            continue
        if "chapter_offset" in rule:
            if int(c) > rule["chapter_offset"]:
                return f"{eng_book} {int(c) - rule['chapter_offset']}:{v}"
        elif "only_chapter" in rule:
            if int(c) == rule.get("to_chapter", 1):
                return f"{eng_book} {rule['only_chapter']}:{v}"
        else:
            return f"{eng_book} {c}:{v}"
    return ref


def eng_links(scheme: str, verses: list[str], eng: dict, own: dict) -> dict[str, list[str]]:
    """Each verse of `scheme` -> the eng verses it maps to."""
    if scheme == "eng":
        return {v: [v] for v in verses}
    doc = json.loads((MAP_DIR / f"{scheme}-to-eng.json").read_text(encoding="utf-8"))
    single = {r["s"]: r["t"] for r in doc["map"]}
    multi: dict[str, list[str]] = {}
    mv = MAP_DIR / f"{scheme}-to-eng.multiverse.json"
    if mv.is_file():
        for r in json.loads(mv.read_text(encoding="utf-8"))["map"]:
            for s in expand(r["s"], own):
                multi[s] = expand(r["t"], eng)  # a relation wins over a single row (PSA 13:6)
    cw = doc.get("crosswalk") or {}
    return {v: multi.get(v) or [single.get(v) or identity(v, cw)] for v in verses}


def components(x_links: dict, o_links: dict) -> list[tuple[list[str], list[str]]]:
    by_eng: dict[str, tuple[list, list]] = collections.defaultdict(lambda: ([], []))
    for side, links in ((0, x_links), (1, o_links)):
        for v, es in links.items():
            for e in es:
                by_eng[e][side].append(v)
    parent: dict = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e, (xs, os_) in by_eng.items():
        nodes = [("x", v) for v in xs] + [("o", v) for v in os_]
        for n in nodes:
            parent[find(n)] = find(("e", e))
    groups: dict = collections.defaultdict(lambda: ([], []))
    for side, links in (("x", x_links), ("o", o_links)):
        for v in links:
            groups[find((side, v))][0 if side == "x" else 1].append(v)
    return [(sorted(xs, key=key), sorted(os_, key=key)) for xs, os_ in groups.values()]


def contiguous(refs: list[str], shp: dict) -> bool:
    for a, b in zip(refs, refs[1:]):
        (ba, ca, va), (bb, cb, vb) = key(a), key(b)
        if ba != bb or not (ca == cb and vb == va + 1 or cb == ca + 1 and vb == 1 and va == shp[ba][ca]):
            return False
    return True


def range_ref(refs: list[str]) -> str:
    if len(refs) == 1:
        return refs[0]
    (b, c1, v1), (_, c2, v2) = key(refs[0]), key(refs[-1])
    return f"{b} {c1}:{v1}-{v2}" if c1 == c2 else f"{b} {c1}:{v1}-{c2}:{v2}"


def build(scheme: str, eng, org_shape, o_links) -> dict:
    shp = shape(scheme)
    cw = {} if scheme == "eng" else json.loads((MAP_DIR / f"{scheme}-to-eng.json").read_text(encoding="utf-8")).get("crosswalk") or {}
    x_links = eng_links(scheme, verses_of(shp, cw), eng, shp)
    single, multi, flagged, no_org = [], [], [], []
    for xs, os_ in components(x_links, o_links):
        if not xs:
            continue
        if not os_:
            no_org += xs
        elif len(xs) == len(os_):
            if len(xs) > 1 and len({tuple(x_links[x]) for x in xs} | {tuple(o_links[o]) for o in os_}) > 1:
                flagged.append({"reason": "equal-size group with differing eng links", "source": xs, "org": os_})
                continue
            single += [{"s": x, "t": o} for x, o in zip(xs, os_) if x != o]
        elif len(xs) == 1 and contiguous(os_, org_shape):
            multi.append({"s": xs[0], "t": range_ref(os_)})
        elif len(os_) == 1 and contiguous(xs, shp):
            multi.append({"s": range_ref(xs), "t": os_[0]})
        else:
            flagged.append({"reason": "not a contiguous one-to-many or many-to-one group", "source": xs, "org": os_})
    single.sort(key=lambda r: key(r["s"]))
    multi.sort(key=lambda r: key(r["s"].split("-")[0]) if "-" not in r["s"].split(":")[1] else key(r["s"].split("-")[0]))
    no_org_books = collections.Counter(v.split()[0] for v in no_org)
    return {"single": single, "multi": multi, "flagged": flagged, "no_org": no_org, "no_org_books": no_org_books}


def main():
    eng = shape("eng")
    org_shape = shape("org")
    o_links = eng_links("org", verses_of(org_shape), eng, org_shape)
    org_doc = json.loads((MAP_DIR / "org-to-eng.json").read_text(encoding="utf-8"))
    for scheme in SCHEMES:
        r = build(scheme, eng, org_shape, o_links)
        head = {
            "source_scheme": scheme,
            "target_scheme": "org",
            "authority": org_doc["authority"],
            "tvtms_rev": org_doc.get("tvtms_rev"),
            "derivation": (f"{scheme}-to-eng composed with org-to-eng inverted, matched in groups of "
                           "verses that share English verses (pipeline/core/generate_vrs_to_org.py)"),
            "scope": "the 39 books of the Hebrew Bible; New Testament numbering is in nt-variants.json",
        }
        (MAP_DIR / f"{scheme}-to-org.json").write_text(json.dumps({
            **head, "note": "Single-verse diffs only; identity elsewhere.",
            "map": r["single"],
            "no_org_counterpart": r["no_org"],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (MAP_DIR / f"{scheme}-to-org.multiverse.json").write_text(json.dumps({
            **head, "kind": "multi-verse relations: one verse in one scheme is several in the other",
            "map": r["multi"], "flagged_not_published": r["flagged"],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[to-org] {scheme}: {len(r['single'])} rows, {len(r['multi'])} multi-verse, "
              f"{len(r['flagged'])} flagged, {len(r['no_org'])} verses with no org counterpart")


if __name__ == "__main__":
    main()
