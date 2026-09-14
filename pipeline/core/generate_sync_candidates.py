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
    for (iso, abbr, canon), info in sorted(grouped.items()):
        if not info["audio"] or not info["text"]:
            continue
        if resolved_of(resolved, iso, info["audio"]):
            continue  # already has real confirmed timing somewhere — not a candidate

        best_text = min(info["text"], key=lambda fid: TEXT_TYPE_PRIORITY.get(info["text"][fid], 99))
        for audio_fs in sorted(info["audio"]):
            candidates.append({
                "iso": iso,
                "canon": canon,
                "distinct_id": abbr,
                "audio_fileset": audio_fs,
                "text_fileset": best_text,
            })

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
