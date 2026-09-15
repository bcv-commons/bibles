#!/usr/bin/env python3
"""Generate a compact "audio-only" exclusion list — the isos this repo's
catalog confirms have real audio but ZERO real text anywhere (DBT, PKF,
helloAO, or OBS).

Built for a "pick a language for reading" UI that needs to exclude
audio-only languages from a text-language selector — a bulk (not
per-language) signal. Client-requested 2026-09-15 to replace
ALL-langs-compact.json's ad hoc "audio-only" category string (a naming
convention they were inferring meaning from, not a declared field).

Deliberately the EXCLUSION set, not the inclusion set: of the full
language-names.json universe (2435 as of 2026-09-15), ~1900 have real
text somewhere (1869 via catalog/index.json + 214 via OBS) and only 624
are genuinely audio-only — publishing the smaller set is the more
compact choice, same principle as media.json's audioBooksSet/
timingBooksSet only appearing when coverage is partial. A client already
has the full universe via language-names.json; "has text" = NOT in this
list.

Deliberately a separate, standalone file, not a bare "t" value folded
into media-index.json's `m` field — that field's own derivation only
ever considers languages with real audio at all (contributing "a"/"at"),
so making it also carry every text-only language's `m: "t"` would grow
that already-published file for every consumer, not just the ones asking
for this specific filter.

Output: export/dbt/_app/audio-only.json
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import EXPORT  # noqa: E402

MEDIA_INDEX = EXPORT / "dbt" / "_app" / "media-index.json"
CATALOG_INDEX = EXPORT / "catalog" / "index.json"
OBS_INDEX = EXPORT / "catalog" / "obs-index.json"
OUTPUT = EXPORT / "dbt" / "_app" / "audio-only.json"


def main():
    with open(MEDIA_INDEX) as f:
        media_index = json.load(f)["l"]
    with open(CATALOG_INDEX) as f:
        catalog_rows = json.load(f)["entries"]
    with open(OBS_INDEX) as f:
        obs_rows = json.load(f)["entries"]

    text_isos = {row[0] for row in catalog_rows}
    text_isos |= {row[0] for row in obs_rows if row[3] in ("t", "at")}

    audio_isos = {
        iso for iso, entry in media_index.items()
        if any(isinstance(c, dict) and c.get("m") in ("a", "at") for c in entry.values())
    }

    audio_only = sorted(audio_isos - text_isos)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(audio_only),
        "audioOnly": audio_only,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    print(f"[generate-audio-only] {len(audio_isos)} with audio, {len(text_isos)} with text, "
          f"{len(audio_only)} audio-only -> {OUTPUT}")


if __name__ == "__main__":
    main()
