#!/usr/bin/env python3
"""Generate a single, compact iso -> {name, vernacular} lookup covering
every language this repo's catalog knows about from any source.

Built for a client "pick a language before you know what's in it" UI
(availability list, not media detail) — publishes a small union of every
name this repo already resolves for media.json/media-index.json (helloAO
-> DBS bible_details -> frozen ALL-langs-compact, see generate_audio_metadata.py's
own name-resolution pass) PLUS the PKF catalog, which was never in that
union before this (root cause of a real client bug: PKF-only languages
like `ivv`/Ivatan have a real name in PKF's manifest but no DBT-family
fileset, so they never reached media-index.json's `l` dict at all).

Reads two already-published/cached artifacts rather than re-deriving
name resolution from scratch:
  - export/dbt/_app/media-index.json  (`l` dict — DBT-family names,
    already resolved via helloAO -> DBS -> ALL-langs-compact priority;
    run generate_audio_metadata.py first if this is missing/stale)
  - internal-data/api-cache/pkf-manifest.json  (`languages` dict — real,
    live PKF catalog; confirmed byte-identical to the live CDN manifest
    before use, 2026-09-15)

Priority on a name conflict for the same iso: whichever source above
already has one wins (media-index.json's own DBT-family priority order,
then PKF, then OBS only for isos neither named) — first found, fill only
if missing, same discipline generate_audio_metadata.py already uses
internally.

OBS-only isos (export/catalog/obs-index.json) are unioned in last, so a
language whose only real content is OBS stories is still selectable.
OBS's own per-language media.json carries no language-name field at all
(checked directly, 2026-09-15) — for the ~87 of 214 OBS isos not already
named by DBT/PKF/helloAO (mostly private-use dialect tags like
`bfz-x-baghati` or region subtags like `pt-br`/`zh-hant` that no source
here has a real name for), data/obs-unresolved-language-names.toml is
checked next (a maintained config table, same convention as
data/obs-iso-639-1.toml — verified names only, filled in over time, never
guessed here). Whatever's still unresolved after that falls back to the
bare code as a value — present in the union, honestly un-named, not
missing. Reported as a distinct count so this is visible, not silent.

Output shape (format "D" from the design discussion): value is a bare
name string when there's no vernacular (or it's identical to the name),
else a real 2-element [name, vernacular] array — 23% smaller raw than a
per-language {"nm":..,"v":..} object across the full real catalog
(measured 2026-09-15: 80,631 vs 61,908 bytes minified for 2,532
languages), and gzip narrows that further, so this is about client parse
cost more than wire size.

Output: export/dbt/_app/language-names.json
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, DATA, EXPORT  # noqa: E402

MEDIA_INDEX = EXPORT / "dbt" / "_app" / "media-index.json"
PKF_MANIFEST = API_CACHE / "pkf-manifest.json"
OBS_INDEX = EXPORT / "catalog" / "obs-index.json"
OBS_UNRESOLVED_NAMES = DATA / "obs-unresolved-language-names.toml"
OUTPUT = EXPORT / "dbt" / "_app" / "language-names.json"


def main():
    if not MEDIA_INDEX.exists():
        sys.exit(f"[generate-language-names] {MEDIA_INDEX} missing — run generate_audio_metadata.py first")

    with open(MEDIA_INDEX) as f:
        media_index = json.load(f)["l"]

    def clean_vernacular(v: str | None) -> str | None:
        # A real upstream bug (DBS bible_details cache, unfixed there as of
        # 2026-09-15): 21 entries store the literal placeholder string
        # "<ISO> (vernacular name not cached)" as if it were a real
        # vernacular name, instead of leaving the field absent. Filtered
        # here rather than fixed at the source — out of scope for this
        # file, and this is the one place that specifically cares about
        # clean display names. Don't confuse with legitimate parenthetical
        # annotations on real vernacular names (e.g. "(O)lugwere",
        # "Kim (Garab)") — only the exact known-bad suffix is excluded.
        if v and v.endswith("(vernacular name not cached)"):
            return None
        return v

    names: dict[str, tuple[str, str | None]] = {}
    for iso, entry in media_index.items():
        nm = entry.get("nm")
        if nm:
            names[iso] = (nm, clean_vernacular(entry.get("v")))

    dbt_family_count = len(names)

    pkf_added = 0
    if PKF_MANIFEST.exists():
        with open(PKF_MANIFEST) as f:
            pkf_langs = json.load(f).get("languages", {})
        for iso, entry in pkf_langs.items():
            if iso in names:
                continue
            nm = entry.get("nm")
            if nm:
                names[iso] = (nm, entry.get("v"))
                pkf_added += 1
    else:
        print(f"[generate-language-names] WARNING: {PKF_MANIFEST} missing, skipping PKF source")

    obs_resolved_from_table = 0
    resolved_names = {}
    if OBS_UNRESOLVED_NAMES.exists():
        with open(OBS_UNRESOLVED_NAMES, "rb") as f:
            resolved_names = tomllib.load(f).get("names", {})

    obs_unnamed = 0
    if OBS_INDEX.exists():
        with open(OBS_INDEX) as f:
            obs_isos = {row[0] for row in json.load(f).get("entries", [])}
        for iso in obs_isos:
            if iso in names:
                continue
            if iso in resolved_names:
                entry = resolved_names[iso]
                if isinstance(entry, list):
                    names[iso] = (entry[0], entry[1])
                else:
                    names[iso] = (entry, None)
                obs_resolved_from_table += 1
            else:
                names[iso] = (iso, None)
                obs_unnamed += 1
    else:
        print(f"[generate-language-names] WARNING: {OBS_INDEX} missing, skipping OBS union")

    compact = {}
    for iso in sorted(names):
        nm, v = names[iso]
        compact[iso] = [nm, v] if v and v != nm else nm

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(compact),
        "l": compact,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    print(f"[generate-language-names] {dbt_family_count} from media-index.json, "
          f"+{pkf_added} new from PKF, +{obs_resolved_from_table} OBS-only resolved via "
          f"{OBS_UNRESOLVED_NAMES.name}, +{obs_unnamed} OBS-only still with no real name "
          f"(code used as-is) -> {len(compact)} total -> {OUTPUT}")


if __name__ == "__main__":
    main()
