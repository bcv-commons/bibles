#!/usr/bin/env python3
"""Generate a merged, per-language "what's available, once you've picked
this language" rollup — joining catalog files this repo already publishes
separately, so a client doesn't have to cross-reference several of them
just to answer that one question.

Deliberately a JOIN, not new data: every field here already exists in
export/catalog/index.json (existence per iso/canon/source),
export/catalog/overlap.json (verified cross-source dedup clusters — only
present for (iso, canon) pairs that were actually fetched and compared;
see doc/catalog-overlap.md), export/dbt/<iso>/media.json (media flag,
audioBooks/timingBooks counts+sets), and export/catalog/obs-index.json
(OBS existence). Nothing here is inferred or guessed — an (iso, canon)
pair with real sources but no overlap.json entry gets a bare `sources`
list, never a fabricated single-edition guess (same "verified only, never
inferred" discipline catalog-overlap.json itself already enforces).

`obs` is a sibling key to `bible`, not nested under it — same reasoning
doc/catalog-obs.md already gives for keeping obs-index.json separate from
catalog-index.json: OBS has no nt/ot/canon concept, so nesting it under
`bible` would misrepresent it.

Output: export/dbt/<iso>/availability.json, one per iso with any bible
or OBS presence.
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import EXPORT  # noqa: E402

CATALOG_INDEX = EXPORT / "catalog" / "index.json"
CATALOG_OVERLAP = EXPORT / "catalog" / "overlap.json"
OBS_INDEX = EXPORT / "catalog" / "obs-index.json"
MEDIA_DIR = EXPORT / "dbt"

CLUSTER_FIELDS = ("ids", "likely", "closest", "score")


def main():
    with open(CATALOG_INDEX) as f:
        index_rows = json.load(f)["entries"]
    with open(CATALOG_OVERLAP) as f:
        overlap_entries = json.load(f)["entries"]
    with open(OBS_INDEX) as f:
        obs_rows = json.load(f)["entries"]

    # iso -> canon -> {source letters}
    iso_canons: dict = defaultdict(lambda: defaultdict(set))
    for row in index_rows:
        iso, canon, src = row[0], row[1], row[2]
        iso_canons[iso][canon].add(src)

    obs_media = {row[0]: row[3] for row in obs_rows}  # iso -> "t"/"at"

    isos = sorted(set(iso_canons) | set(obs_media))

    written = 0
    for iso in isos:
        bible = {}
        for canon in sorted(iso_canons.get(iso, {})):
            sources = sorted(iso_canons[iso][canon])
            canon_out = {"sources": sources}

            key = f"{iso}:{canon}"
            clusters = overlap_entries.get(key)
            if clusters:
                canon_out["editions"] = [
                    {k: c[k] for k in CLUSTER_FIELDS if k in c} for c in clusters
                ]
            bible[canon] = canon_out

        # Fold in media.json's own media flag + real book-level detail —
        # media.json only ever tracks the base "nt"/"ot" testament, never
        # a separate Portions bucket, so this only ever lands on those two
        # canon keys, not "ntp"/"otp" (see module docstring).
        media_path = MEDIA_DIR / iso / "media.json"
        if media_path.exists():
            with open(media_path) as f:
                m = json.load(f)
            for base_canon, cdata in m.get("canons", {}).items():
                if base_canon not in bible:
                    continue
                if cdata.get("media"):
                    bible[base_canon]["media"] = cdata["media"]
                for field in ("audioBooks", "audioBooksSet", "timingBooks", "timingBooksSet"):
                    if cdata.get(field):
                        bible[base_canon][field] = cdata[field]

        output: dict = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "iso": iso,
        }
        if bible:
            output["bible"] = bible
        if iso in obs_media:
            output["obs"] = {"media": obs_media[iso]}

        out_dir = MEDIA_DIR / iso
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "availability.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
        written += 1

    print(f"[generate-language-availability] {written} languages -> {MEDIA_DIR}/<iso>/availability.json")


if __name__ == "__main__":
    main()
