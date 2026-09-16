#!/usr/bin/env python3
"""Generate a small, focused id-bridge: Biblica project id (the id used in
catalog/index.json's and catalog/overlap.json's `o:` entries) -> the real
edition abbreviation yaapi.bible uses (the <edition> path segment
openbible-chapters.json's per-chapter endpoint expects).

These are two genuinely different id spaces this repo already publishes
separately — Biblica's own project id (from openbible-api-1.biblica.com,
opaque hex) vs. yaapi.bible's own short `abbreviation` field — with
nothing bridging them until now. Client-requested 2026-09-16, after
finding `o:` ids in catalog/overlap.json unusable for constructing
openbible-chapters.json URLs without a manual per-language mapping.

Matched the same way the original yaapi.bible coverage-gap check was:
via the real artifact id embedded in yaapi.bible's own `link` field,
cross-referenced against each Biblica project's current-version USFM
artifact id (fetch_openbible_cache.py's cached data) — an exact id match,
never a name/language guess.

Only covers Biblica projects that actually have a yaapi.bible match (388
of 553 as of 2026-09-16, per the same coverage check) — a project with no
match here genuinely isn't on yaapi.bible yet, not a lookup failure.

Output: export/catalog/openbible-editions.json
    {"<project_id>": {"abbr": "<yaapi abbreviation>", "iso": "<iso 639-3>"}}
"""
import json
import re
import sys
import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, EXPORT  # noqa: E402

YAAPI_VERSIONS = API_CACHE / "yaapi" / "versions.json"
OPENBIBLE_TEXT = API_CACHE / "openbible" / "text"
OUTPUT = EXPORT / "catalog" / "openbible-editions.json"


def main():
    if not YAAPI_VERSIONS.exists():
        sys.exit(f"[generate-openbible-abbr] {YAAPI_VERSIONS} missing — run fetch_yaapi_cache.py first")

    yaapi_versions = json.loads(YAAPI_VERSIONS.read_text())
    # artifact_id -> yaapi version row
    by_artifact_id = {}
    for v in yaapi_versions:
        link = v.get("link", "")
        m = re.search(r"artifactContent/([0-9a-f]+)", link)
        if m:
            by_artifact_id[m.group(1)] = v

    mapping = {}
    for f in glob.glob(str(OPENBIBLE_TEXT / "*.json")):
        detail = json.loads(Path(f).read_text())
        project_id = detail["project"]["id"]
        artifact_id = None
        for v in detail.get("versions", []):
            if not v.get("current"):
                continue
            for a in v.get("artifacts", []):
                if a.get("format") == "USFM":
                    artifact_id = a.get("id")
                    break
        if not artifact_id:
            continue
        yv = by_artifact_id.get(artifact_id)
        if not yv:
            continue
        iso = (yv.get("language") or {}).get("iso639p3")
        abbr = yv.get("abbreviation")
        if not iso or not abbr:
            continue
        mapping[project_id] = {"abbr": abbr, "iso": iso}

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "schema_version": 1,
        "generated_at": None,
        "note": "project_id -> yaapi.bible edition abbreviation + iso, for constructing "
                "openbible-chapters.json URLs from an o: id. Only covers projects with a "
                "real yaapi.bible match (see doc/openbible-chapters.md).",
        "entries": mapping,
    }
    OUTPUT.write_text(json.dumps(output, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"[generate-openbible-abbr] {len(mapping)} project ids mapped -> {OUTPUT}")


if __name__ == "__main__":
    main()
