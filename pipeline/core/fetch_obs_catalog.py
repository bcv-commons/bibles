#!/usr/bin/env python3
"""Fetch door43's own OBS catalog stats — the real existence source of
truth for catalog/obs-index.json.

Deliberately independent of audio-sync's _obs_batches/ staging tree
(fetch_obs_batches.py): that reflects only what audio-sync has picked up
and resolved so far (a handful of languages as of 2026-09), not what
actually exists on door43. Mirrors the DBT precedent exactly — DBT audio
existence is derived directly from DBT's own raw catalog (dbt-catalog.json),
not from any downstream alignment pipeline; audio-sync consumes existence
signals like this one, it doesn't produce them.

Fetches TWO queries against door43's catalog/stats-ext API, both filtered
to the "Open Bible Stories" subject:
  - unfiltered ("languages_all") — every language with OBS *text* at all
    (214 as of 2026-09-01, per door43's own healthy/prod repo listing)
  - hasAudio=true ("languages_audio") — the subset with real narrated
    audio (92)
Both `languages` fields are dicts of {iso: repo_count} — exactly the row
shape catalog-obs-index.json already uses (count omitted when 1). The
text-only set (languages_all - languages_audio, 122 languages) is what
fetch_obs_repos.py resolves per-language detail for, since audio-sync's
staging pipeline never touches them.

Keys here stay as door43's RAW codes (2-letter ISO 639-1 for 36
languages, not the 3-letter ISO 639-3 everything else in this repo uses)
— normalizing this early would break every downstream door43 API call,
which needs the raw code (`lang=am`, not `lang=amh`), and would mismatch
audio-sync's own `_obs_batches/`/`align/obs/` paths, which also key off
door43's raw code (confirmed: `en`/`fr`, both raw 2-letter, are among the
audio-bearing set). Normalization happens once, at the final publish
boundary, in generate_obs_index.py and generate_obs_metadata.py — see
pipeline/obs_iso.py and data/obs-iso-639-1.toml.

Usage:
    python3 pipeline/core/fetch_obs_catalog.py
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import OBS_DOOR43_CATALOG_FILE  # noqa: E402

STATS_URL = "https://git.door43.org/api/v1/catalog/stats-ext?subject=Open%20Bible%20Stories"
STATS_URL_AUDIO = STATS_URL + "&hasAudio=true"


def fetch_languages(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("languages", {})


def main():
    languages_all = fetch_languages(STATS_URL)
    languages_audio = fetch_languages(STATS_URL_AUDIO)

    OBS_DOOR43_CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    OBS_DOOR43_CATALOG_FILE.write_text(
        json.dumps(
            {"languages_all": languages_all, "languages_audio": languages_audio},
            indent=2, sort_keys=True,
        ),
        encoding="utf-8",
    )
    text_only = len(set(languages_all) - set(languages_audio))
    print(f"[fetch-obs-catalog] {len(languages_all)} total language(s), "
          f"{len(languages_audio)} with audio, {text_only} text-only "
          f"-> {OBS_DOOR43_CATALOG_FILE}")


if __name__ == "__main__":
    main()
