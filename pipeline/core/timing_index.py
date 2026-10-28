#!/usr/bin/env python3
"""Internal "does real timing exist, for which books" lookup for
generate_audio_metadata.py's media-code classification and its
timingBooks/timingBooksSet counts, and generate_sync_candidates.py's
dedup — the one legitimate remaining server-side use of timing existence
data (see pull_align_manifests.py's docstring for why this stopped being
a published, client-facing artifact on 2026-09-14).

The three sources a client can fetch timing from (doc/dbt-timing.md), nothing else:
  - internal-data/pkf-audio-index.json — PKF's timing, from pkf/<iso>/info.json
    (fetch_pkf_audio_index.py). Per book. Clients try it first. For DBT audio under the DBT
    fileset; for PKF's own audio under the language's PKF edition, <ISO>PKF (pkf_edition_id).
  - internal-data/align-index.json — audio-sync's real work, distilled
    from their _runs/ manifests (pull_align_manifests.py). Per book.
  - internal-data/dbt-timing-index.json — DBT's own timing, one probe per
    testament (fetch_dbt_timing_index.py). A testament that passes counts
    as timed for all its books: DBT gives no per-book answer short of
    probing every book.

bibles' own old timing (internal-data/timing/BB, contrib, legacy-timing-data)
is no longer read (2026-10-28): BB is replaced by dbt-timing-index.json, and
contrib/legacy are timing no client can fetch once timing-raw is retired.
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import ALIGN_INDEX_FILE, INTERNAL_DATA  # noqa: E402

DBT_TIMING_INDEX_FILE = INTERNAL_DATA / "dbt-timing-index.json"
PKF_AUDIO_INDEX_FILE = INTERNAL_DATA / "pkf-audio-index.json"
# DBT's index has no iso: its filesets sit under this key, matched by fileset id alone.
ANY_ISO = "*"

OT_BOOKS = {"GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA", "1KI", "2KI",
            "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO", "ECC", "SNG", "ISA", "JER",
            "LAM", "EZK", "DAN", "HOS", "JOL", "AMO", "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL"}
NT_BOOKS = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL",
            "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"}


def load_resolved() -> dict:
    """{iso: {audio_fileset: {books}}} — every fileset with timing a client
    can fetch, and which books it covers. DBT's filesets are under ANY_ISO."""
    resolved: dict = defaultdict(lambda: defaultdict(set))

    for iso, filesets in load_pkf().items():
        for audio_fileset, books in filesets.items():
            resolved[iso][audio_fileset].update(books)
    for iso, own in load_pkf_own().items():
        resolved[iso][pkf_edition_id(iso)].update(own["timing"])

    if ALIGN_INDEX_FILE.exists():
        index = json.loads(ALIGN_INDEX_FILE.read_text())
        for iso, canons in index.items():
            for filesets in canons.values():
                for audio_fileset, books in filesets.items():
                    resolved[iso][audio_fileset].update(books)

    if DBT_TIMING_INDEX_FILE.exists():
        dbt = json.loads(DBT_TIMING_INDEX_FILE.read_text()).get("filesets", {})
        for audio_fileset, canons in dbt.items():
            for canon, books in (("nt", NT_BOOKS), ("ot", OT_BOOKS)):
                if canons.get(canon) is True:
                    resolved[ANY_ISO][audio_fileset].update(books)

    return resolved


def _pkf_index() -> dict:
    return json.loads(PKF_AUDIO_INDEX_FILE.read_text()) if PKF_AUDIO_INDEX_FILE.exists() else {}


def load_pkf() -> dict:
    """{iso: {audio_fileset: [books]}}: the DBT audio filesets PKF timed."""
    return _pkf_index().get("filesets", {})


def load_pkf_own() -> dict:
    """{iso: {"src", "audio": {book: [chapters]}, "timing": {book: [chapters]}}}: the audio PKF
    gets from elsewhere than DBT (scriptureearth.org mostly), playable without a key."""
    return _pkf_index().get("own", {})


def pkf_edition_id(iso: str) -> str:
    """The id of a language's PKF edition, as in catalog/text-route.json (p:<ISO>PKF)."""
    return f"{iso.upper()}PKF"


def resolved_of(resolved: dict, iso: str, known_fileset_ids) -> set:
    """Intersect a caller-supplied set of REAL audio fileset ids (read
    directly from sorted/BB's own bible.abbr-scoped metadata — the only
    reliable abbr<->fileset-id mapping) against what's actually resolved.
    Do not guess this by string-prefix on the abbr (verified false
    negatives: e.g. abbr "ACRNNT"'s real audio files are literally named
    "ACRWB1N2DA_timing.json", no shared prefix at all)."""
    return set(known_fileset_ids) & (set(resolved.get(iso, {})) | set(resolved.get(ANY_ISO, {})))
