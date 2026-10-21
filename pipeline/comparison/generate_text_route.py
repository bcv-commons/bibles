#!/usr/bin/env python3
"""catalog/text-route.json: for every edition and testament, the one canonical text a client
fetches to read verse text, and through which route. The text fingerprint (tools/verse-text)
is computed over this text only, so two clients reading the same edition get the same tokens.

    entries["<iso>:<canon>"]["<source id>"] = {"route": ..., "id" | "path": ..., "why"?: ...}

Source ids are catalog/overlap.json's (d: DBT, h: helloAO, p: PKF, o: openbible /
audiobiblia, e: eBible, c: CrossWire). Routes, in order of preference (agreed with lexeme-aligner 2026-10-17):

- sofria: the source's own Sofria. DBT: its text_json fileset (`id`, the -json fileset).
  Ours (openbible, audiobiblia, CrossWire): `path` on cdn.bibel.wiki, <BOOK>/<chapter>.sofria.json
  (the same text is also there as <BOOK>.usj.json; route parity holds).
- usj: our USJ, where that is the only form we publish (eBible): `path`, <BOOK>.usj.json.
- usx: the source's USX, read with tools/verse-text (usx_to_usj.py, usx_to_sofria.mjs). Only
  where the source has no Sofria, or its Sofria lost text (`why`: sofria_damaged, evidence
  in data/text-route-overrides.toml).
- helloao: helloAO's chapter JSON through tools/verse-text's converter (helloao_to_usj.py,
  tools/helloao-to-sofria/helloao_to_usj.mjs); helloAO has no standard structured format.
- plain: plain verse text, read with tools/verse-text's plain reader. Only where nothing
  structured exists.
  `why: not_in_fileset_listing`: DBT's fileset listing (catalog/text.json) has no text for
  the version but dbt/_catalog.json does, and the comparison read it as plain text.
- pkf: a PKF collection (`id`, the .pkf file under cdn.bibel.wiki/pkf/<iso>/). Its reading
  route is not settled yet.

Usage: python3 generate_text_route.py [--out PATH]
"""
import json
import sys
import tomllib
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, CATALOG_DIR, DATA, EXPORT, HELLOAO_BOOK_COMPLETENESS_FILE  # noqa: E402

NT = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL", "1TH", "2TH",
      "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"}
OVERRIDES = DATA / "text-route-overrides.toml"
ROUTES = {
    "sofria": "the source's own Sofria; read with extract_sofria",
    "usj": "our USJ (the only form published for the edition); read with extract_usj",
    "usx": "the source's USX; read with usx_to_usj.py / usx_to_sofria.mjs (tools/verse-text)",
    "helloao": "helloAO chapter JSON through tools/verse-text's converter, then extract_usj",
    "plain": "plain verse text; read with tools/verse-text's plain reader",
    "pkf": "a PKF collection; reading route not settled yet",
}


def fileset(distinct_id: str, code: str) -> str:
    kind, _, rest = code.partition(":")
    return rest if kind == "T" else distinct_id + rest


def dbt(entries: dict, overrides: dict) -> None:
    text = json.loads((CATALOG_DIR / "text.json").read_text())["entries"]
    for key, versions in text.items():
        iso, canon = key.split(":")
        canon = canon.rstrip("p")
        for did, variants in versions.items():
            by_fmt = {}
            for v in variants:
                for f in v["fmt"]:
                    by_fmt.setdefault(f, fileset(did, v["id"]))
            o = overrides.get(did)
            if o and o["route"] == "usx" and "u" in by_fmt:
                row = {"route": "usx", "id": by_fmt["u"], "why": o["why"]}
            elif "j" in by_fmt:
                row = {"route": "sofria", "id": by_fmt["j"]}
            elif "u" in by_fmt:
                row = {"route": "usx", "id": by_fmt["u"]}
            elif "pl" in by_fmt:
                row = {"route": "plain", "id": by_fmt["pl"]}
            else:
                continue  # only a generic downloadable format: no reading route
            entries.setdefault(f"{iso}:{canon}", {})[f"d:{did}"] = row


def dbt_catalog_only(entries: dict) -> None:
    """Versions with text in dbt/_catalog.json but none in DBT's fileset listing: the
    comparison fetched them as plain text (fetch_sources.dbt_text), so that route works."""
    rows = json.loads((API_CACHE / "dbt-catalog.json").read_text())["versions"]
    for iso, did, canon, *fields in rows:
        for f in fields:
            kind, _, rest = f.partition(":")
            if kind not in ("t", "T") or rest.startswith(("helloao:", "ebible:")):
                continue
            row = {"route": "plain", "id": fileset(did, f), "why": "not_in_fileset_listing"}
            entries.setdefault(f"{iso}:{canon.rstrip('p')}", {}).setdefault(f"d:{did}", row)


def from_overlap(entries: dict) -> None:
    """catalog/overlap.json can file an edition under another (iso, canon) than its own
    files suggest (an iso it was matched under, or a testament helloAO's completeness file
    doesn't flag): give those rows the same route, so every reachable id there has one."""
    ours = {i: r for v in entries.values() for i, r in v.items() if i[0] in "oec"}
    overlap = json.loads((CATALOG_DIR / "overlap.json").read_text())["entries"]
    for key, clusters in overlap.items():
        for c in clusters:
            for i in c["ids"]:
                row = {"route": "helloao"} if i.startswith("h:") else ours.get(i)
                if row and c.get("r") is not False:
                    entries.setdefault(key, {}).setdefault(i, row)


def helloao(entries: dict) -> None:
    books = json.loads(HELLOAO_BOOK_COMPLETENESS_FILE.read_text())
    for tid, b in books.items():
        for canon, has in (("nt", b.get("has_any_nt")), ("ot", b.get("has_any_ot"))):
            if has:
                entries.setdefault(f"{b['iso']}:{canon}", {})[f"h:{tid}"] = {"route": "helloao"}


def own(entries: dict, source: str, prefix: str, route: str) -> None:
    for meta in sorted((EXPORT / f"{source}-usj").glob("*/*/_meta.json")):
        iso, ed = meta.parent.parent.name, meta.parent.name
        m = json.loads(meta.read_text())
        books = set(m.get("books", []))
        r = route if route != "sofria" or "sofria" in m.get("formats", {"sofria": 1}) else "usj"
        for canon, has in (("nt", books & NT), ("ot", books - NT)):
            if has:
                entries.setdefault(f"{iso}:{canon}", {})[f"{prefix}:{ed}"] = {"route": r, "path": f"{source}/{iso}/{ed}/"}


def pkf(entries: dict) -> None:
    manifest = json.loads((API_CACHE / "pkf-manifest.json").read_text())["languages"]
    for iso, e in manifest.items():
        for c in e.get("collections", []):
            cov = c.get("coverage") or {}
            canons = [k for k, has in (("nt", cov.get("n", True)), ("ot", cov.get("o"))) if has]
            for canon in canons:
                entries.setdefault(f"{iso}:{canon}", {}).setdefault(f"p:{iso.upper()}PKF", {"route": "pkf", "id": c["pkf"]})


def main():
    args = sys.argv[1:]
    out = Path(args[args.index("--out") + 1]) if "--out" in args else CATALOG_DIR / "text-route.json"
    overrides = tomllib.loads(OVERRIDES.read_text()).get("dbt", {}) if OVERRIDES.exists() else {}
    entries: dict = {}
    dbt(entries, overrides)
    dbt_catalog_only(entries)
    helloao(entries)
    own(entries, "openbible", "o", "sofria")
    own(entries, "audiobiblia", "o", "sofria")
    own(entries, "ebible", "e", "usj")
    own(entries, "crosswire", "c", "sofria")
    pkf(entries)
    from_overlap(entries)
    doc = {"schema_version": 1, "generated_at": date.today().isoformat(), "base": "https://cdn.bibel.wiki/", "routes": ROUTES,
           "entries": {k: dict(sorted(v.items())) for k, v in sorted(entries.items())}}
    out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    from collections import Counter
    c = Counter(r["route"] for v in entries.values() for r in v.values())
    print(f"[text-route] {sum(c.values())} edition-testaments in {len(entries)} (iso, canon): {dict(c)} -> {out}")


if __name__ == "__main__":
    main()
