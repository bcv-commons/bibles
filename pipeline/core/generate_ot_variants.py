#!/usr/bin/env python3
"""_vrs/map/ot-variants.json: Old Testament layouts that vary between editions of one scheme.

A scheme's map (<scheme>-to-eng.json) can hold one layout per chapter. In a few places the
editions sharing a scheme disagree, so any single choice is wrong for some of them. Found
2026-10-16 by probing all 35 orgw editions (lexeme-aligner's audit raised it): five Job
38-41 layouts, two Ecclesiastes 11-12 and two Hosea 13-14 layouts. These are published as
variants, the way nt-variants.json handles the New Testament: each is one layout of a block
of chapters, detected per edition from the chapters' last verses, with rows to eng (and
to org) for the whole block. dbt/_vrs/index.json's `ot` entry lists, per edition, the
variants it follows where it differs from its own scheme's shape.

Every layout here was read against real text at the verses where the content marks the
boundary (the lioness, eng JOB 38:39; the wild goats, 39:1; "the LORD said to Job", 40:1;
"out of the whirlwind", 40:6; Leviathan at the hook, 41:1; "no one is so fierce", 41:10;
ECC "Rejoice, young man", 11:9; "Remember your Creator", 12:1). The editions named per
variant are the ones checked.

Usage: python3 pipeline/core/generate_ot_variants.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import EXPORT  # noqa: E402

MAP_DIR = EXPORT / "_vrs" / "map"
OUT = MAP_DIR / "ot-variants.json"

# Each layout: block (book, chapters), the chapters' last verses, and the ranges that
# renumber against eng: (edition chapter, first verse, last verse, eng chapter, eng verse).
# Verses not covered by a range keep their number.
JOB = ("JOB", [38, 39, 40, 41])
ECC = ("ECC", [11, 12])
HOS = ("HOS", [13, 14])
LAYOUTS = {
    "JOB-eng": (JOB, [41, 30, 24, 34], [],
                "English layout", "ACEIBS (DBT; also DTPBSM, GORLAI, MADIBS, MINLAI, TIHBSM, ZLMTMV)"),
    "JOB-heb": (JOB, [41, 30, 32, 26], [(40, 25, 32, 41, 1), (41, 1, 26, 41, 9)],
                "Hebrew (Masoretic) layout", "org; no orgw edition (2026-10-16)"),
    "JOB-lsg": (JOB, [38, 38, 28, 25],
                [(39, 1, 3, 38, 39), (39, 4, 33, 39, 1), (39, 34, 38, 40, 1), (40, 1, 19, 40, 6),
                 (40, 20, 28, 41, 1), (41, 1, 25, 41, 10)],
                "Louis Segond layout", "fra_lsg (helloAO; also FRNTLS, swe_fol, nld_nbg, dan_det, BAMLSB, SAGBIV, ...)"),
    "JOB-ces": (JOB, [41, 35, 28, 25],
                [(39, 31, 35, 40, 1), (40, 1, 19, 40, 6), (40, 20, 28, 41, 1), (41, 1, 25, 41, 10)],
                "Kralice (Czech) layout", "ces_bkr (helloAO; also CESK13)"),
    "JOB-bel": (JOB, [41, 35, 27, 26],
                [(39, 31, 35, 40, 1), (40, 1, 19, 40, 6), (40, 20, 27, 41, 1), (41, 1, 26, 41, 9)],
                "layout of bel_jfc, RMLNEW, RMLNVC", "bel_jfc (helloAO), RMLNEW (DBT)"),
    "JOB-hun": (JOB, [38, 38, 19, 34],
                [(39, 1, 3, 38, 39), (39, 4, 33, 39, 1), (39, 34, 38, 40, 1), (40, 1, 19, 40, 6)],
                "Hungarian Karoli layout", "HUNK90 (DBT)"),
    "ECC-eng": (ECC, [10, 14], [], "English layout", "swe_fol, nld_nbg (helloAO; and most orgw editions)"),
    "ECC-lsg": (ECC, [8, 16], [(12, 1, 2, 11, 9), (12, 3, 16, 12, 1)],
                "Louis Segond layout", "fra_lsg (helloAO; also FRNTLS, BAMLSB, SAGBIV, HUNK90)"),
    "HOS-eng": (HOS, [16, 9], [], "English layout", "fra_lsg (helloAO; also FRNTLS, BAMLSB, SAGBIV, ces_bkr, CESK13)"),
    "HOS-heb": (HOS, [15, 10], [(14, 1, 1, 13, 16), (14, 2, 10, 14, 1)],
                "Hebrew (Masoretic) layout", "swe_fol, nld_nbg (helloAO; and most orgw editions)"),
}


def rows(ranges):
    out = []
    for c, v1, v2, ec, ev in ranges:
        for v in range(v1, v2 + 1):
            out.append((f"{c}:{v}", f"{ec}:{ev + v - v1}"))
    return out


def main():
    eng_to_org = {r["s"]: r["t"] for r in json.loads((MAP_DIR / "eng-to-org.json").read_text())["map"]}
    variants = {}
    for vid, ((book, chapters), lengths, ranges, tradition, checked) in LAYOUTS.items():
        pairs = [(f"{book} {s}", f"{book} {t}") for s, t in rows(ranges)]
        renumbered = {s for s, _ in pairs}
        # every verse of the block, so a client can map the edition's verse to eng and org
        all_rows = []
        for c, n in zip(chapters, lengths):
            for v in range(1, n + 1):
                s = f"{book} {c}:{v}"
                t = dict(pairs).get(s, s)
                if s in renumbered or s != t:
                    all_rows.append({"s": s, "t": [t], "o": eng_to_org.get(t, t)})
                elif eng_to_org.get(t, t) != s:
                    all_rows.append({"s": s, "t": [t], "o": eng_to_org.get(t, t)})
        variants[vid] = {
            "chapters": {f"{book} {c}": n for c, n in zip(chapters, lengths)},
            "detect": f"{book} {chapters[0]}-{chapters[-1]} have " + "/".join(map(str, lengths)) + " verses",
            "tradition": tradition,
            "text_checked": checked,
            "map": all_rows,
        }
    doc = {
        "target_scheme": "eng",
        "note": ("Tanakh layouts that vary between editions of one scheme. For an edition whose "
                 "dbt/_vrs/index.json `ot` entry lists a variant, take that block's rows from the variant "
                 "instead of from its `l` scheme's map; elsewhere use the scheme map. A row maps the edition's "
                 "verse s to eng verse(s) t and to the org (Hebrew) verse o; a verse with no row keeps its number "
                 "in both."),
        "variants": variants,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[ot-variants] {len(variants)} variants -> {OUT}")


if __name__ == "__main__":
    main()
