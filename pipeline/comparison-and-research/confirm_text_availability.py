#!/usr/bin/env python3
"""Confirm DBT text availability for languages where the catalog claims a
text fileset exists but a real fetch has never actually confirmed it.

See examples/content-availability-confirmation.md for the design: catalog
data can only ever say what *should* be there — this script performs a real
fetch attempt per (iso, fileset_id) and records ground truth: confirmed
present, confirmed absent (with a reason), or never checked.

Candidate filesets come from MONO's published catalog export,
cdn.bibel.wiki/dbt/_catalog.json (3,360 version/canon rows, ~120KB) — a
compact, pre-resolved answer to "what DBT filesets should exist," so bibles
no longer needs its own sorted/BB or api-cache/bibles/bible_details scan
for this. Row shape: [iso, distinct_id, canon, <audio>?, <text>?] where each
optional field is a "a:"/"t:" (reconstruct as distinct_id + suffix) or
"A:"/"T:" (value is the full fileset id verbatim — ~14% of real filesets
don't share distinct_id's prefix at all) tagged string. "t:helloao:<id>" /
"t:ebible:<id>" mean no DBT text fileset exists (external source only) —
skipped here, nothing to fetch from DBT for those.

`canon` is `nt`/`ot` for whole-testament coverage, or `ntp`/`otp` (trailing
`p`) for Portions/partial filesets — DBT's own `fileset_contains_book()`
treats a book in a Portions fileset as "may or may not actually be
present," so a `p`-suffixed row is a weaker, optimistic claim than a plain
row. Plain-canon candidates are attempted first (higher confidence a
positive carries over); Portions candidates are still attempted — the
catalog's claim doesn't replace the live fetch either way — but tagged
`"portions": true` in the recorded result so a confirmed-absent Portions
result isn't read as strongly as a confirmed-absent plain-canon one.

First-pass scope: the 76 DBT/PKF-overlap languages missing a REV 15 text
sample in data/text/BB/nt/ (see CLAUDE.local.md). Not a recurring job (yet) —
run manually, review, re-run as needed.

Usage:
    python3 scripts/confirm_text_availability.py [--book REV] [--chapter 15]

Reads:  cdn.bibel.wiki/dbt/_catalog.json (cached locally at
        api-cache/dbt-catalog.json; falls back to the cached copy if the
        fetch fails)
Writes: data/text-availability.json (local record, gitignored — see below)
        export/dbt/_text-availability.json (publish-ready artifact)
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import download_language_content as dl  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, EXPORT, TEXT_AVAILABILITY_FILE  # noqa: E402

CATALOG_URL = "https://cdn.bibel.wiki/dbt/_catalog.json"
CATALOG_CACHE = API_CACHE / "dbt-catalog.json"
STATE_FILE = TEXT_AVAILABILITY_FILE
PUB_PATH = EXPORT / "dbt" / "_text-availability.json"

# 76-language gap identified 2026-07-15: DBT/PKF overlap languages missing
# a REV 15 text sample in data/text/BB/nt/. See CLAUDE.local.md.
TARGET_ISOS = {
    "aaz", "abx", "agt", "arn", "atd", "att", "bco", "big", "bkw", "blw",
    "bon", "bwd", "caf", "cav", "cbk", "chd", "chq", "cpy", "crx", "cta",
    "ctu", "cub", "cut", "cux", "dad", "dgc", "eko", "eri", "fan", "gdg",
    "gvs", "ivb", "jae", "kbc", "kgf", "kgk", "kgp", "kmk", "kqc", "kyg",
    "kyj", "lbk", "mau", "mav", "mbs", "meu", "mmx", "msb", "msk", "mti",
    "mvn", "nas", "ncl", "nhg", "otm", "ots", "pav", "qxl", "sbe", "sgz",
    "srq", "ssx", "swp", "tif", "tku", "toj", "too", "trc", "trq", "tsw",
    "tvk", "xta", "yby", "zat", "zpv", "ztp",
}


def fetch_catalog() -> dict:
    """Fetch cdn.bibel.wiki/dbt/_catalog.json, cache locally, fall back to
    the cached copy if the live fetch fails (offline dev, transient error)."""
    try:
        req = urllib.request.Request(CATALOG_URL, headers={"User-Agent": "bibles/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        catalog = json.loads(raw)
        CATALOG_CACHE.parent.mkdir(parents=True, exist_ok=True)
        CATALOG_CACHE.write_bytes(raw)
        return catalog
    except Exception as e:
        if CATALOG_CACHE.exists():
            print(f"[confirm-text] live catalog fetch failed ({e}), using cached copy "
                  f"({CATALOG_CACHE})", file=sys.stderr)
            return json.loads(CATALOG_CACHE.read_text())
        raise


def resolve_fileset(distinct_id: str, spec: str) -> Optional[str]:
    """'a:N1DA'/'t:N_ET' -> distinct_id + suffix. 'A:'/'T:' -> verbatim.
    None for external-source specs (t:helloao:.../t:ebible:...) or anything
    that doesn't parse — nothing to fetch from DBT for those."""
    if ":" not in spec:
        return None
    kind, value = spec.split(":", 1)
    if kind in ("a", "t"):
        if value.startswith(("helloao:", "ebible:")):
            return None
        return distinct_id + value
    if kind in ("A", "T"):
        return value
    return None


def candidate_filesets(target_isos: set[str], book_canon: str) -> dict[str, list[tuple[str, bool]]]:
    """iso -> [(fileset_id, is_portions), ...] of real DBT text filesets, per
    the published catalog, restricted to target_isos and one testament
    (matching the sample book: REV -> nt, PSA -> ot) — covers both the plain
    canon (nt/ot) and its Portions counterpart (ntp/otp)."""
    catalog = fetch_catalog()
    candidates: dict[str, list[tuple[str, bool]]] = {}
    for row in catalog.get("versions", []):
        iso, distinct_id, canon = row[0], row[1], row[2]
        if iso not in target_isos:
            continue
        if canon == book_canon:
            is_portions = False
        elif canon == book_canon + "p":
            is_portions = True
        else:
            continue
        for field in row[3:]:
            kind = field.split(":", 1)[0]
            if kind not in ("t", "T"):  # audio (a/A) not relevant here
                continue
            fileset_id = resolve_fileset(distinct_id, field)
            if fileset_id:
                candidates.setdefault(iso, []).append((fileset_id, is_portions))
    return candidates


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    args = sys.argv[1:]
    book = "REV"
    chapter = 15
    if "--book" in args:
        book = args[args.index("--book") + 1]
    if "--chapter" in args:
        chapter = int(args[args.index("--chapter") + 1])

    catalog = fetch_catalog()
    ref_books = catalog.get("reference_books", {"nt": "REV", "ot": "PSA"})
    canon = next((c for c, b in ref_books.items() if b == book), None)
    if canon is None:
        sys.exit(f"[confirm-text] --book {book} isn't a catalog reference book "
                  f"({ref_books}); this script only knows how to filter candidates "
                  f"by canon for the established reference chapters.")

    candidates = candidate_filesets(TARGET_ISOS, canon)
    total = sum(len(v) for v in candidates.values())
    print(f"[confirm-text] {len(candidates)} language(s), {total} candidate fileset(s) "
          f"for {book} {chapter} (of {len(TARGET_ISOS)} target languages)")

    no_candidates = sorted(TARGET_ISOS - set(candidates))
    if no_candidates:
        print(f"[confirm-text] {len(no_candidates)} language(s) have no DBT text "
              f"fileset for this canon in the published catalog at all: {no_candidates}")

    state = load_state()
    confirmed, absent, checked_n = 0, 0, 0
    probe_key = f"{book}_{chapter:03d}"

    for iso in sorted(candidates):
        # Plain canon (nt/ot) first — higher-confidence claim than Portions
        # (ntp/otp), per the catalog's own confirmation-priority guidance.
        for fileset_id, is_portions in sorted(candidates[iso], key=lambda c: c[1]):
            result = dl.get_text_content(fileset_id, book, chapter)
            checked_n += 1
            now = datetime.now(timezone.utc).isoformat()
            if result:
                status = "confirmed"
                confirmed += 1
            else:
                status = dl._classify_api_failure()
                absent += 1
            entry = {"status": status, "checked_at": now}
            if is_portions:
                entry["portions"] = True
            state.setdefault(iso, {}).setdefault(fileset_id, {})[probe_key] = entry
            tag = " (portions)" if is_portions else ""
            print(f"  {iso}/{fileset_id}{tag}: {status}")
            time.sleep(0.1)  # light rate-limit courtesy to DBT's API

    save_state(state)
    print(f"[confirm-text] done: {checked_n} checked, {confirmed} confirmed, "
          f"{absent} confirmed-absent/errored. State saved to {STATE_FILE}")

    # Publish-ready artifact. `never_checked` is explicit and separate from
    # `languages` so "no catalog fileset to try" is never silently collapsed
    # into "confirmed absent" — that conflation is exactly the bug this
    # script exists to fix (see examples/content-availability-confirmation.md).
    pub = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "languages": state,
        "never_checked": {
            "reason": "no DBT text fileset for this canon in the published catalog",
            "isos": no_candidates,
        },
    }
    PUB_PATH.parent.mkdir(parents=True, exist_ok=True)
    PUB_PATH.write_text(json.dumps(pub, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[confirm-text] wrote {PUB_PATH}")


if __name__ == "__main__":
    main()
