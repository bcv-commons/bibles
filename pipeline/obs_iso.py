"""Normalize door43's OBS language codes to ISO 639-3, the convention
every other file in this repo uses (catalog-index.json, /dbt/<iso>/media.json,
etc — zero ISO 639-1 codes anywhere). door43 tags 36 of its 214 OBS
languages with a 2-letter 639-1 code instead; left as-is, that silently
breaks cross-referencing against every other catalog file here. See
data/obs-iso-639-1.toml for the table and the ambiguity notes on 6 of the
36 (macrolanguage codes DBT itself resolves to a specific individual
language, not a verified 1:1 fact like the other 30).
"""
import tomllib
from functools import lru_cache

from paths import OBS_ISO_MAP_FILE


@lru_cache(maxsize=1)
def _load_map() -> dict:
    data = tomllib.loads(OBS_ISO_MAP_FILE.read_text())
    return data.get("iso639_1_to_3", {})


@lru_cache(maxsize=1)
def _load_reverse_map() -> dict:
    return {v: k for k, v in _load_map().items()}


def normalize_obs_iso(iso: str) -> str:
    """door43's raw iso code -> ISO 639-3, when a mapping exists; unchanged otherwise
    (3-letter codes, dialect/region subtags like kfx-x-innerseraji or zh-hant, etc)."""
    return _load_map().get(iso, iso)


def denormalize_obs_iso(iso: str) -> str:
    """ISO 639-3 -> door43's raw code, when this iso is one of the 36 door43
    tags with 639-1 instead — the reverse of normalize_obs_iso(), needed to
    compute audio-sync's real align/obs/<raw_iso>/ path from bibles' own
    published (639-3) iso. Unchanged otherwise (the other 178 already match)."""
    return _load_reverse_map().get(iso, iso)
