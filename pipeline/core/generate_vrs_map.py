#!/usr/bin/env python3
"""Publish a reconciled cross-scheme verse mapping (<scheme>-to-eng.json).

Takes a TVTMS-derived `source_ref -> standard_ref [-> action]` mapping (standard =
KJV/`eng`), applies our book-code crosswalk (data/vrs/crosswalk.toml) so the map
keys on OUR scheme codes, records deliberate exceptions, and emits the publishable
artifact for cdn.bibel.wiki/_vrs/map/ with TVTMS provenance.

We OWN: the crosswalk, the exceptions, the reconciliation. TVTMS is the cited
authority for the mapping content (attributed + rev-pinned), not us. See
internal-docs/vrs-cross-scheme-mappings.md §2a.

Usage:
  python3 generate_vrs_map.py \\
      --mapping example/plan-docs/vrs-reconciliation/tvtms_lxx_to_eng.tsv \\
      --source-scheme lxx --tvtms-rev <STEPBible-Data commit> \\
      --emit-tsv export/_vrs/map/lxx-to-eng.crosswalked.tsv

Then validate the crosswalked output against the canonical shapes:
  python3 example/plan-docs/vrs-reconciliation/validate_vrs_mapping.py \\
      --vrs-dir example/plan-docs/vrs-reconciliation/vrs \\
      --mapping export/_vrs/map/lxx-to-eng.crosswalked.tsv --source-scheme lxx
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import EXPORT, VRS_DIR  # noqa: E402

AUTHORITY = "TVTMS — Translators Versification Traditions, STEPBible-Data (CC BY 4.0)"
ATTRIBUTION = "https://STEPBible.org"
SOURCE_URL = "https://github.com/STEPBible/STEPBible-Data"


def split_ref(ref: str) -> tuple[str, int, str]:
    """`BOOK C:V` -> (BOOK, chapter:int, verse:str). Verse kept as str (subverses)."""
    book, cv = ref.split(" ", 1)
    c, v = cv.split(":", 1)
    return book, int(c), v


def join_ref(book: str, c: int, v: str) -> str:
    return f"{book} {c}:{v}"


def load_crosswalk(path: Path) -> dict:
    cfg = tomllib.loads(path.read_text(encoding="utf-8"))
    return {
        "book": cfg.get("book", {}),
        "drop": set(cfg.get("drop", {}).get("books", [])),
        "pending": set(cfg.get("pending", {}).get("books", [])),
        "pending_reason": cfg.get("pending", {}).get("reason", ""),
        "esg_mapping": cfg.get("esg", {}).get("mapping"),
        "documented_gaps": cfg.get("esg", {}).get("documented_gaps", []),
    }


def load_vrs(vrs_path: Path) -> dict[str, dict[int, int]]:
    """Parse a .vrs file -> {BOOK: {chapter: last_verse}}."""
    sch: dict[str, dict[int, int]] = {}
    for ln in vrs_path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        p = ln.split()
        sch[p[0]] = {int(t.split(":")[0]): int(t.split(":")[1]) for t in p[1:]}
    return sch


def load_vrs_book(vrs_path: Path, book: str) -> dict[int, int]:
    return load_vrs(vrs_path).get(book, {})


def in_shape(shape: dict[str, dict[int, int]], ref: str) -> bool:
    """Is `ref` within the scheme's shape? (title/subverse refs pass by convention.)"""
    book, c, v = split_ref(ref)
    if not v.isdigit():
        return True
    return book in shape and c in shape[book] and 1 <= int(v) <= shape[book][c]


def classify_exceptions(mapped: list[dict], lxx: dict, eng: dict) -> list[dict]:
    """Rows whose ref falls outside our own shapes — TVTMS is right, our .vrs is
    narrow. Recorded (not dropped) per §5. JER source gaps = the LXX reordering."""
    exc: list[dict] = []
    for r in mapped:
        if not in_shape(lxx, r["s"]):
            book = split_ref(r["s"])[0]
            exc.append({"s": r["s"], "t": r["t"], "side": "source",
                        "reason": "lxx-shape-narrow",
                        "kind": "reorder" if book == "JER" else "boundary-extend"})
        elif not in_shape(eng, r["t"]):
            exc.append({"s": r["s"], "t": r["t"], "side": "target",
                        "reason": "eng-shape-narrow", "kind": "recension"})
    return exc


def esg_rows(tsv: Path) -> list[dict]:
    """Read the reconciled lxx-ESG -> eng-ESG map (source_ref, standard_ref, action)."""
    rows: list[dict] = []
    for ln in tsv.read_text(encoding="utf-8").splitlines():
        if ln.startswith("#") or ln.startswith("source_ref"):
            continue
        p = ln.rstrip("\n").split("\t")
        if len(p) < 2:
            continue
        rows.append({"s": p[0], "t": p[1], **({"a": p[2]} if len(p) > 2 and p[2] else {})})
    return rows


def reconstruction_check(rows: list[dict], book: str, tgt: dict[str, dict[int, int]]) -> list[str]:
    """Shape-reconstruction: for each target chapter the mapping renumbers into, the
    max target verse must reach that chapter's length in the target shape. Catches
    off-by-N renumbering (e.g. Addition block sized wrong) that in-range checks miss.
    Only applied to chapters that HAVE renumber rows (additions-before/interleaved →
    top core verse lands at chapter end)."""
    problems: list[str] = []
    by_ch: dict[int, int] = {}
    for r in rows:
        b, c, v = split_ref(r["t"])
        if b == book and v.isdigit():
            by_ch[c] = max(by_ch.get(c, 0), int(v))
    for c, mx in sorted(by_ch.items()):
        want = tgt.get(book, {}).get(c)
        if want is not None and mx != want:
            problems.append(f"{book} {c}: renumber reaches {mx}, shape wants {want}")
    return problems


def apply_crosswalk(book: str, c: int, v: str, cw: dict) -> tuple[str, str, int, str]:
    """Return (status, book, chapter, verse). status in {ok, dropped, pending}."""
    if book in cw["drop"]:
        return "dropped", book, c, v
    if book in cw["pending"]:
        return "pending", book, c, v
    rule = cw["book"].get(book)
    if not rule:
        return "ok", book, c, v                      # uppercase code already matches ours
    if "only_chapter" in rule:                        # e.g. 2CH ch37 -> MAN ch1
        if c != rule["only_chapter"]:
            return "ok", book, c, v
        return "ok", rule["to"], rule.get("to_chapter", c), v
    new_c = c + rule.get("chapter_offset", 0)
    return "ok", rule["to"], new_c, v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapping", type=Path,
                    default=VRS_DIR / "tvtms-lxx-to-eng.baseline.tsv",
                    help="TSV: source_ref<TAB>standard_ref[<TAB>action] (default: "
                         "the pinned vendored TVTMS-derived baseline)")
    ap.add_argument("--crosswalk", type=Path, default=VRS_DIR / "crosswalk-lxx.toml")
    ap.add_argument("--source-scheme", default="lxx")
    ap.add_argument("--target-scheme", default="eng")
    ap.add_argument("--tvtms-rev", default="UNPINNED",
                    help="STEPBible-Data commit the mapping was derived from")
    ap.add_argument("--out", type=Path, default=None,
                    help="output json (default export/_vrs/map/<src>-to-<tgt>.json)")
    ap.add_argument("--emit-tsv", type=Path, default=None,
                    help="also write crosswalked source_ref<TAB>standard_ref for the validator")
    ap.add_argument("--vrs-dir", type=Path, default=VRS_DIR,
                    help="canonical .vrs shapes (for the ESG source-verse check)")
    args = ap.parse_args()

    cw = load_crosswalk(args.crosswalk)
    out = args.out or (EXPORT / "_vrs" / "map" / f"{args.source_scheme}-to-{args.target_scheme}.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    rows_in = 0
    mapped: list[dict] = []
    dropped: list[list[str]] = []
    pending: dict[str, int] = {}
    for ln in args.mapping.read_text(encoding="utf-8").splitlines():
        if ln.startswith("#") or ln.startswith("source_ref"):
            continue
        p = ln.rstrip("\n").split("\t")
        if len(p) < 2:
            continue
        rows_in += 1
        book, c, v = split_ref(p[0])
        action = p[2] if len(p) > 2 else ""
        status, nb, nc, nv = apply_crosswalk(book, c, v, cw)
        if status == "dropped":
            dropped.append([p[0], p[1]])
            continue
        if status == "pending":
            pending[book] = pending.get(book, 0) + 1
            continue
        mapped.append({"s": join_ref(nb, nc, nv), "t": p[1], **({"a": action} if action else {})})

    src_shape = load_vrs(args.vrs_dir / f"{args.source_scheme}.vrs")
    tgt_shape = load_vrs(args.vrs_dir / f"{args.target_scheme}.vrs")

    esg_added = 0
    esg_recon: list[str] = []
    if cw["esg_mapping"] and args.source_scheme == "lxx":
        supp = esg_rows(Path(cw["esg_mapping"]))
        mapped.extend(supp)
        esg_added = len(supp)
        esg_recon = reconstruction_check(supp, "ESG", tgt_shape)

    mapped.sort(key=lambda r: r["s"])
    exceptions = classify_exceptions(mapped, src_shape, tgt_shape)
    exc_books = sorted({split_ref(e["s"])[0] if e["side"] == "source"
                        else split_ref(e["t"])[0] for e in exceptions})

    artifact = {
        "source_scheme": args.source_scheme,
        "target_scheme": args.target_scheme,
        "authority": AUTHORITY,
        "attribution": ATTRIBUTION,
        "source": SOURCE_URL,
        "tvtms_rev": args.tvtms_rev,
        "note": "Single-verse diffs only; identity elsewhere. Derived from TVTMS, "
                "reconciled to our scheme codes — TVTMS is the mapping authority.",
        "crosswalk": {k: v for k, v in cw["book"].items()},
        "pending_crosswalk": {"books": sorted(pending), "counts": pending,
                              "reason": cw["pending_reason"]},
        "documented_gaps": cw["documented_gaps"],
        "exceptions": exceptions,
        "exceptions_note": "Rows kept in `map` but outside our own .vrs shapes — "
                           "TVTMS is authoritative; our shapes are narrower. "
                           f"Books needing shape reconciliation: {exc_books}. "
                           "JER = the LXX chapter reordering (needs true LXX Jeremiah).",
        "map": mapped,
    }
    out.write_text(json.dumps(artifact, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.emit_tsv:
        args.emit_tsv.parent.mkdir(parents=True, exist_ok=True)
        with args.emit_tsv.open("w", encoding="utf-8") as fh:
            fh.write("source_ref\tstandard_ref\n")
            for r in artifact["map"]:
                fh.write(f"{r['s']}\t{r['t']}\n")

    print(f"[vrs-map] {args.source_scheme}->{args.target_scheme}: in={rows_in} "
          f"mapped={len(mapped)} (incl esg={esg_added}) dropped={len(dropped)} "
          f"pending={sum(pending.values())} {dict(pending)}")
    if esg_added:
        status = "OK" if not esg_recon else f"FAIL {esg_recon}"
        print(f"[vrs-map] esg: {esg_added} rows | shape-reconstruction: {status}"
              f"{' | gap: ' + str(cw['documented_gaps']) if cw['documented_gaps'] else ''}")
    print(f"[vrs-map] exceptions={len(exceptions)} (rows outside our shapes, kept in map) "
          f"books={exc_books}")
    print(f"[vrs-map] tvtms_rev={args.tvtms_rev} -> {out}")
    if args.emit_tsv:
        print(f"[vrs-map] crosswalked tsv -> {args.emit_tsv}")


if __name__ == "__main__":
    main()
