#!/usr/bin/env python3
"""
Publish a compact per-version fileset catalog derived from sorted/BB/ to CDN.

For every (iso, distinct_id, canon) version found in sorted/BB, resolves the
best audio/text fileset against a fixed reference book (REV for NT, PSA for
OT — this project's established sample-chapter convention) using the same
get_best_fileset_for_book() resolution generate_batch_manifest.py performs
per-job. Publishing the resolved answer once here means bibles/audio-sync
never need to re-run fileset resolution or hold their own copy of
sorted/BB/api-cache — see internal-docs/content-availability-confirmation.md.

Compact encoding — one row per version:
  [iso, distinct_id, canon, <audio>, <text>]
  <audio>/<text> are optional; a row with neither is omitted entirely.
    a: / t:  -> suffix; reconstruct as distinct_id + value (verified exact
               round-trip against real data for every fileset_id that
               shares distinct_id's prefix)
    A: / T:  -> already the full fileset id (~14% of real filesets don't
               share a prefix with distinct_id — confirmed empirically),
               use verbatim, do not concatenate
    t:helloao:<id> / t:ebible:<id> -> external text source, no DBT text
               fileset for this version (same text_source convention
               already used in the batch manifest — see generate_batch_manifest.py)
  canon is "nt"/"ot" for DBT-confirmed whole-testament coverage, or
  "ntp"/"otp" (trailing "p") when the resolved fileset is Portions/partial
  — fileset_contains_book()'s own docstring says a book "may or may not"
  actually be present in these, so the row is DBT's optimistic claim, not
  a confirmed answer. A live fetch is the only way to actually confirm a
  "p"-suffixed row (see content-availability-confirmation.md) — found and
  fixed 2026-07-18 after a first build silently DROPPED all Portions-only
  versions (~14% of the catalog) rather than marking them uncertain.

Usage:
    python3 generate_catalog_export.py

Output: export/dbt/_catalog.json (publish via `make publish-dbt`, same as
every other artifact under export/dbt/).
"""
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from download_language_content import (
    get_best_fileset_for_book,
    get_distinct_id_from_metadata,
    _extract_version_id,
    _find_helloao_id,
    _get_external_text_source,
)

SORTED_DIR = Path("sorted/BB")
OUT_PATH = Path("export/dbt/_catalog.json")
REFERENCE_BOOKS = {"nt": "REV", "ot": "PSA"}


def encode_fileset(distinct_id: str, fileset_id: str) -> tuple[str, bool]:
    """Return (value, is_suffix). is_suffix=True means the caller should tag
    it with the lowercase (a:/t:) prefix and the consumer reconstructs via
    distinct_id + value; False means tag with the uppercase (A:/T:) prefix
    and use the value verbatim (fileset_id doesn't share distinct_id's
    prefix — a real, confirmed-common case, not an edge case to special-case
    away)."""
    if fileset_id.upper().startswith(distinct_id.upper()):
        return fileset_id[len(distinct_id):], True
    return fileset_id, False


# Size codes fileset_contains_book() treats as CERTAIN (whole testament)
# coverage for the given canon — everything else (NTP/OTP/NTPOTP/generic
# P/S/PARTIAL, and the "other testament" half of NTOTP/OTNTP) is Portions
# coverage, where fileset_contains_book()'s own docstring says a book "may
# or may not" actually be present. Mirrors that function's branches exactly.
CERTAIN_SIZE_CODES = {"nt": {"NT", "C", "NTOTP"}, "ot": {"OT", "C", "OTNTP"}}


def _is_uncertain_coverage(fileset_id: str, canon: str, metadata_by_fileset: dict) -> bool:
    meta = metadata_by_fileset.get(fileset_id)
    if not meta:
        return False
    size = meta.get("fileset", {}).get("size", "")
    return size not in CERTAIN_SIZE_CODES[canon]


def resolve_version_row(iso: str, distinct_id: str, canon: str, metadata_by_fileset: dict) -> list | None:
    book = REFERENCE_BOOKS[canon]
    best = get_best_fileset_for_book(metadata_by_fileset, book)
    if not best:
        return None

    # Mark the row as Portions/uncertain-coverage (append "p" to canon) if
    # EITHER the resolved audio or text fileset's size code isn't one
    # fileset_contains_book() treats as certain whole-testament coverage —
    # i.e. the book being present is DBT's optimistic guess, not confirmed
    # by the catalog structure itself. A live fetch is the only way to
    # actually confirm these (see content-availability-confirmation.md).
    uncertain = False
    for fs in (best.get("audio_fileset"), best.get("text_fileset")):
        if fs and _is_uncertain_coverage(fs, canon, metadata_by_fileset):
            uncertain = True
            break

    row = [iso, distinct_id, f"{canon}p" if uncertain else canon]

    audio_fs = best.get("audio_fileset")
    if audio_fs:
        value, is_suffix = encode_fileset(distinct_id, audio_fs)
        row.append(f"a:{value}" if is_suffix else f"A:{value}")

    text_fs = best.get("text_fileset")
    if text_fs:
        value, is_suffix = encode_fileset(distinct_id, text_fs)
        row.append(f"t:{value}" if is_suffix else f"T:{value}")
    else:
        vid = _extract_version_id(iso, distinct_id)
        hao_id = _find_helloao_id(iso, vid)
        if hao_id:
            row.append(f"t:helloao:{hao_id}")
        else:
            source_type, source_id = _get_external_text_source(iso, distinct_id)
            if source_type:
                row.append(f"t:{source_type}:{source_id}")

    if len(row) == 3:
        return None  # neither audio nor text resolved — nothing useful to publish
    return row


def load_groups(iso_dir: Path) -> dict:
    """Group all fileset metadata under one iso dir by distinct_id ONLY —
    NOT by canon. fileset_contains_book() (called inside
    get_best_fileset_for_book()) doesn't actually use its canon argument; it
    decides per-fileset from that fileset's own `size` code (NT/OT/C/NTP/
    OTP/etc.), including Portions filesets *optimistically* for either
    testament ("may or may not contain this book — let the API decide").
    Pre-filtering groups by a single group-level canon before calling that
    resolution logic silently drops PARTIAL-only versions entirely — found
    2026-07-18 via `cpy`/`ncl`, both 100% PARTIAL-canon with real DBT text,
    both absent from an earlier build of this catalog. 316 of ~2256
    languages (~14%) have PARTIAL-only fileset coverage — a real, common
    case, not a rounding error to special-case away.
    """
    groups = defaultdict(dict)
    for fileset_dir in iso_dir.iterdir():
        if not fileset_dir.is_dir():
            continue
        meta_file = fileset_dir / "metadata.json"
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        distinct_id = get_distinct_id_from_metadata(meta)
        fileset_id = meta.get("fileset", {}).get("id", "")
        if distinct_id and fileset_id:
            groups[distinct_id][fileset_id] = meta
    return groups


def main():
    if not SORTED_DIR.is_dir():
        raise SystemExit(f"{SORTED_DIR} not found. Run: python3 sort_cache_data.py")

    versions = []
    iso_count = 0

    for iso_dir in sorted(SORTED_DIR.iterdir()):
        if not iso_dir.is_dir():
            continue
        iso_count += 1
        groups = load_groups(iso_dir)
        for distinct_id, metadata_by_fileset in groups.items():
            # Try both testaments against the FULL fileset set for this
            # version — fileset_contains_book() correctly sorts out which
            # individual filesets actually cover NT vs OT (including
            # Portions), so no canon pre-filtering is needed or correct here.
            for canon in ("nt", "ot"):
                row = resolve_version_row(iso_dir.name, distinct_id, canon, metadata_by_fileset)
                if row:
                    versions.append(row)

    output = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reference_books": REFERENCE_BOOKS,
        "versions": versions,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
    print(f"[catalog] {iso_count} languages scanned, {len(versions)} version/canon rows -> {OUT_PATH}")


if __name__ == "__main__":
    main()
