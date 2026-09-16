#!/usr/bin/env python3
"""Generate /dbt/_app/sync-candidates.json — actionable alignment worklist
for audio-sync.

Every entry here is a real DBT edition with genuine, paired audio AND text
but no confirmed per-verse timing anywhere yet (not DBT's own declared
timing, not bibles' own owned sources, not audio-sync's real work) — i.e.
exactly the population generate_audio_metadata.py classifies "syncable"
and, by design, excludes from media.json's filesets[] (that exclusion is
itself a useful signal to other clients: "audio+text both exist, but not
ready to consume as synced playback yet"). This file is the other half —
the positive, actionable input FOR audio-sync to pick its next batches
from, using the same field names as align/_runs/<batch_id>.json's own
manifest schema (iso, canon, distinct_id, audio_fileset — snake_case,
confirmed 2026-09-14 to be their real convention) so no translation layer
is needed on their side.

Nothing needs to change here or in generate_audio_metadata.py when
audio-sync actually processes a candidate: once they publish it (a
manifest result with status "ok"), the next run of
pull_align_manifests.py folds it into the local digest, and that
edition's real audio automatically satisfies timing_index.resolved_of()
and graduates out of "syncable" into "with-timecode"/"audio-with-timecode"
— and out of this candidate list — on its own.

Output: export/dbt/_app/sync-candidates.json, shape:
    {"candidates": [
        {"iso": "eng", "canon": "nt", "distinct_id": "ENGBER",
         "audio_fileset": "ENGBERN1DA", "text_fileset": "ENGBERN_ET"},
        ...
    ]}

Usage:
    python3 pipeline/core/generate_sync_candidates.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from timing_index import load_resolved, resolved_of  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import EXPORT, SORTED_DIR  # noqa: E402

OUTPUT_DIR = EXPORT / "dbt"

# Prefer a plain-text fileset over usx/json when both exist for the same
# edition — matches get_text_content()'s own resolution preference
# elsewhere in this repo (plain text is directly usable; usx/json need
# extra parsing audio-sync would rather not redo per candidate).
TEXT_TYPE_PRIORITY = {"text_plain": 0, "text_format": 1, "text_json": 2, "text_usx": 3}


def _normalize_fileset_id(fileset_id):
    """Strip encoding-variant suffixes (e.g. "-opus16") to get the base
    fileset id — same stripping sort_cache_data.py's normalize_fileset_id()
    does (duplicated here for the same reason _prefer_standard() is: no
    standalone equivalent to import). Needed here specifically because
    resolved_of() does an exact-string match — without this, an encoding
    variant of an ALREADY-timed recording (e.g. FRNTLSN2DA-opus16, a
    different literal fileset id from the FRNTLSN2DA that's actually in
    align-index.json) would wrongly look untimed and get proposed as a
    "new" candidate for content that's really already aligned (found
    2026-09-19 investigating the fra/JHN report, once the edition-level
    skip that had been masking it was fixed)."""
    for suffix in ["-opus16", "-opus32", "-mp3", "-64", "-128", "16"]:
        if fileset_id.endswith(suffix):
            return fileset_id[: -len(suffix)]
    return fileset_id


def _prefer_standard(fileset_ids):
    """Drop a dramatized (DA) fileset id when a same-generation standard
    (SA) sibling is ALSO in the list — same real DA/SA marker (last two
    characters) sort_cache_data.py's filter_dramatized_versions() was
    fixed to use 2026-09-19 (that function's own docstring has the full
    story: the marker is the literal "DA"/"SA" suffix, NOT the recording
    generation digit at position -3, which an earlier version of that
    function mistakenly checked instead). Duplicated here (not imported)
    since that's an instance method on sort_cache_data.py's sorter class
    with no standalone equivalent — kept in sync by cross-reference, not
    a shared import, to avoid an awkward instance-method dependency."""
    base_groups = defaultdict(list)
    for fs_id in fileset_ids:
        if len(fs_id) >= 2:
            base_groups[fs_id[:-2]].append(fs_id)
    kept = []
    for base, fs_list in base_groups.items():
        standard_ids = [fs for fs in fs_list if fs.endswith("SA")]
        dramatized_ids = [fs for fs in fs_list if fs.endswith("DA")]
        if standard_ids and dramatized_ids:
            kept.extend(standard_ids)
            kept.extend(fs for fs in fs_list if fs not in dramatized_ids and fs not in standard_ids)
        else:
            kept.extend(fs_list)
    return kept


def main():
    if not SORTED_DIR.is_dir():
        print(f"[generate-sync-candidates] {SORTED_DIR} not found. Run: make sort-dbt-catalog")
        return

    resolved = load_resolved()

    # (iso, abbr, canon) -> {"audio": {fileset_id: type}, "text": {fileset_id: type}}
    grouped: dict[tuple, dict] = defaultdict(lambda: {"audio": {}, "text": {}})

    for iso_dir in sorted(p for p in SORTED_DIR.iterdir() if p.is_dir()):
        iso = iso_dir.name
        for fileset_dir in sorted(p for p in iso_dir.iterdir() if p.is_dir()):
            meta_path = fileset_dir / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text())
            except Exception:
                continue

            abbr = meta.get("bible", {}).get("abbr", "")
            if not abbr:
                continue
            canon_raw = meta.get("canon", "")
            fs = meta.get("fileset", {})
            fs_id = fs.get("id", "")
            fs_type = fs.get("type", "")
            books = meta.get("books") or []
            testaments = {b.get("testament") for b in books if b.get("testament")}

            canons = set()
            if canon_raw == "NT":
                canons.add("nt")
            elif canon_raw == "OT":
                canons.add("ot")
            elif canon_raw == "FULL":
                canons.update({"nt", "ot"})
            else:
                if "NT" in testaments:
                    canons.add("nt")
                if "OT" in testaments:
                    canons.add("ot")

            is_audio = fs_type in ("audio", "audio_drama", "audio_stream", "audio_drama_stream")
            is_text = fs_type.startswith("text")

            for canon in canons:
                key = (iso, abbr, canon)
                if is_audio and fs_id:
                    grouped[key]["audio"][fs_id] = fs_type
                if is_text and fs_id:
                    grouped[key]["text"][fs_id] = fs_type

    candidates = []
    sa_priority_fixes = []  # edition already has a real DA alignment; SA sibling still doesn't (see below)
    for (iso, abbr, canon), info in sorted(grouped.items()):
        if not info["audio"] or not info["text"]:
            continue

        # FIXED 2026-09-19 (real, confirmed bug — found investigating a
        # real client report for fra/JHN): this used to skip the entire
        # edition once ANY of its audio filesets had confirmed timing —
        # so once FRNTLSN2DA got aligned, its untimed FRNTLSN2SA sibling
        # never got proposed as a candidate at all, forever. Now checks
        # PER FILESET: an edition can have some variants already timed
        # and others still needing it (exactly the DA-timed/SA-untimed
        # case this was built to prevent going forward).
        # Dedupe encoding variants (e.g. FRNTLSN2DA / FRNTLSN2DA-opus16) to
        # one representative real id per normalized base — prefer the
        # shortest (no-suffix, canonical) form when more than one variant
        # is present.
        by_normalized: dict[str, str] = {}
        for fs_id in info["audio"]:
            norm = _normalize_fileset_id(fs_id)
            if norm not in by_normalized or len(fs_id) < len(by_normalized[norm]):
                by_normalized[norm] = fs_id

        already_timed_norm = resolved_of(resolved, iso, by_normalized.keys())
        untimed_real_ids = [real for norm, real in by_normalized.items() if norm not in already_timed_norm]
        if not untimed_real_ids:
            continue  # every audio variant already has confirmed timing

        already_timed_real = {by_normalized[n] for n in already_timed_norm if n in by_normalized}
        filtered_audio = _prefer_standard(sorted(untimed_real_ids))

        best_text = min(info["text"], key=lambda fid: TEXT_TYPE_PRIORITY.get(info["text"][fid], 99))
        for audio_fs in filtered_audio:
            candidates.append({
                "iso": iso,
                "canon": canon,
                "distinct_id": abbr,
                "audio_fileset": audio_fs,
                "text_fileset": best_text,
            })
            if audio_fs.endswith("SA") and any(fs.endswith("DA") for fs in already_timed_real):
                sa_priority_fixes.append({"iso": iso, "canon": canon, "distinct_id": abbr, "audio_fileset": audio_fs})

    if sa_priority_fixes:
        # Deliberately NOT under export/ — this is a local-only worklist
        # for coordinating with audio-sync directly (e.g. attaching to a
        # message), not part of the published sync-candidates.json schema
        # (see this file's own docstring on why that schema is kept
        # minimal and matched to their manifest format exactly).
        priority_path = SORTED_DIR.parent / "sync-candidates-sa-priority.json"
        priority_path.write_text(
            json.dumps({"candidates": sa_priority_fixes}, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[generate-sync-candidates] {len(sa_priority_fixes)} SA-priority-fix candidates "
              f"(edition already has a real DA alignment) -> {priority_path} (local only, not published)")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    app_dir = OUTPUT_DIR / "_app"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "sync-candidates.json").write_text(
        json.dumps({"candidates": candidates}, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[generate-sync-candidates] {len(candidates)} candidates "
          f"({len({(c['iso'], c['canon'], c['distinct_id']) for c in candidates})} editions) "
          f"-> {app_dir / 'sync-candidates.json'}")


if __name__ == "__main__":
    main()
