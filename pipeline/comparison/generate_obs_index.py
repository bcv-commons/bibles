#!/usr/bin/env python3
"""Publish export/catalog/obs-index.json — the existence signal for OBS
(Open Bible Stories) narration content, the OBS analogue of
catalog-index.json (which is Bible-edition text only).

Deliberately a SEPARATE file from catalog-index.json, not new rows mixed
into it: that file's `canon` field is a documented 4-value enum
(nt/ntp/ot/otp) that existing consumers validate against, and OBS content
has no canon at all (50 fixed stories, not book/chapter/verse). Putting
`"obs"` in that slot would be a silent breaking assumption for any client
that assumes the 4-value set is exhaustive. Publishing here instead — same
/catalog/ root, same row convention, same schema_version convention — is
the closest analogue without breaking that contract. See doc/catalog-obs.md.

Source: door43's own OBS catalog stats (fetch_obs_catalog.py — run that
first), NOT audio-sync's _obs_batches/ staging tree. This mirrors the DBT
precedent exactly: DBT audio existence is derived directly from DBT's own
raw catalog, independent of any downstream alignment pipeline — audio-sync
consumes this existence signal, it doesn't produce it.

Covers BOTH text-only and audio-bearing languages (214 total as of
2026-09-01, 92 of them also with audio) — the `media` row field says
which. Using _obs_batches/ here instead would badly understate real
coverage (narrows to "already staged," currently a handful of languages,
not "actually has OBS content," currently 214).

door43 tags 36 of these 214 languages with a 2-letter ISO 639-1 code
instead of the 3-letter ISO 639-3 every other file in this repo uses
(catalog-index.json has zero 2-letter codes) — normalized here via
normalize_obs_iso() (see pipeline/obs_iso.py and
data/obs-iso-639-1.toml) so a client can actually cross-reference an
`iso` here against catalog-index.json's. 30 of the 36 map to a plain,
unambiguous ISO 639-3 code; 6 (ar/fa/sw/zh/uz/ne) are macrolanguage-level
codes mapped to whichever specific individual-language code this repo's
own DBT catalog happens to use (arb/pes/swh/cmn/uzn/npi) — a practical
default for cross-referencing, not a verified "same variant" fact the
way the other 30 are. See data/obs-iso-639-1.toml's header for the full
reasoning, found + fixed 2026-09-02.

Usage:
    python3 pipeline/comparison/generate_obs_index.py [--out PATH]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from obs_iso import normalize_obs_iso  # noqa: E402
from paths import CATALOG_DIR, OBS_DOOR43_CATALOG_FILE  # noqa: E402

OBS_DOOR43_STATS_URL = "https://git.door43.org/api/v1/catalog/stats-ext?subject=Open%20Bible%20Stories"


def main():
    args = sys.argv[1:]
    out_path = Path(args[args.index("--out") + 1]) if "--out" in args else CATALOG_DIR / "obs-index.json"

    if not OBS_DOOR43_CATALOG_FILE.exists():
        print(f"[generate-obs-index] {OBS_DOOR43_CATALOG_FILE} not found. Run: make fetch-obs-catalog")
        return

    cached = json.loads(OBS_DOOR43_CATALOG_FILE.read_text())
    languages_all = cached.get("languages_all", {})
    audio_isos_normalized = {normalize_obs_iso(iso) for iso in cached.get("languages_audio", {})}

    entries = []
    for raw_iso, count in languages_all.items():
        iso = normalize_obs_iso(raw_iso)
        media = "at" if iso in audio_isos_normalized else "t"
        row = [iso, "obs", "o", media]
        if count > 1:
            row.append(count)
        entries.append(row)

    output = {
        "schema_version": 1,
        "generated_at": None,
        "sources": [{"o": OBS_DOOR43_STATS_URL}],
        "entries": sorted(entries),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"[generate-obs-index] {len(entries)} entries -> {out_path}")


if __name__ == "__main__":
    main()
