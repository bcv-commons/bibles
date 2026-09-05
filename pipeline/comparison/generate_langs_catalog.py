#!/usr/bin/env python3
"""Phase 2: generate catalog/langs.json + catalog/langs-mini.json directly
from data `bibles` already owns and regenerates every run — replacing the
Phase 1 frozen mirror of `bible-story-builder`'s (now-private) export.
See doc/catalog-langs.md for full background.

Same shape as the original MONO export (verified against the real
mirrored file): {metadata: {...}, canons: {nt: {category: {iso: {n,v,s}}},
ot: {...same...}}}, PLUS a new "obs" canon bucket the original never had
— the actual fix for "new OBS languages need to be in this list," since
this generator derives it from data this repo produces itself rather
than depending on any external export ever again.

## Category derivation

Five categories, derived per (iso, canon) from three booleans:
  TEXT  = catalog/index.json has a row for this (iso, canon-family), any source
  AUDIO = catalog/audio-index.json has a row for this (iso, canon-family), any source
  TIMED = confirmed real per-verse timing exists (DBT-only today — the
          only source with cataloged real timing; see doc/sources.md)

  TEXT AUDIO TIMED -> with-timecode        (all three)
  ---  AUDIO TIMED -> audio-with-timecode  (audio+timing, no text)
  TEXT AUDIO  ---   -> syncable            (text+audio, not yet aligned)
  TEXT  ---   ---   -> text-only
  ---  AUDIO  ---   -> audio-only
  ---   ---   ---   -> (no row at all — excluded)

For nt/ot: TEXT collapses ntp into nt and otp into ot (Portions still
counts as "has some text"); TIMED reads /dbt/_app/media-index.json's
`m == "at"` per canon (the compact roll-up generate_audio_metadata.py
already produces, itself DBT's own with-timecode/audio-only convention).

For obs: TEXT/AUDIO/TIMED read directly from each language's own
/obs/<iso>/media.json (storyCount/audioStories/timingStories > 0) — OBS
has no canon or Portions concept, this is the whole language's coverage.

## Language names

Primary: /dbt/_app/media-index.json's `nm`/`v`/`sc` (generate_audio_metadata.py's
own helloAO -> DBS -> optional-frozen-file chain, reordered 2026-09-03 to
prefer live sources). Fallback, OBS-only languages neither source covers
(mostly door43's dialect/private-use-tagged codes, e.g. bfz-x-baghati):
door43's own `language_title` (captured in fetch_obs_repos.py's cache) —
NOT guaranteed to be strictly an English gloss the way DBS/helloAO names
are, just door43's own display title for that language; used as `n` on
a best-effort basis since the alternative is no name at all.

Usage:
    python3 pipeline/comparison/generate_langs_catalog.py [--out DIR]
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from obs_iso import normalize_obs_iso  # noqa: E402
from paths import CATALOG_DIR, EXPORT, OBS_DIR, OBS_REPOS_FILE  # noqa: E402

MEDIA_INDEX_FILE = EXPORT / "dbt" / "_app" / "media-index.json"


def classify(text: bool, audio: bool, timed: bool) -> str | None:
    if text and audio and timed:
        return "with-timecode"
    if audio and timed and not text:
        return "audio-with-timecode"
    if text and audio:
        return "syncable"
    if text:
        return "text-only"
    if audio:
        return "audio-only"
    return None


def load_bible_signals():
    """{iso: {"nt": (text, audio, timed), "ot": (...)}} for every iso with any signal."""
    text = {}   # iso -> {"nt": bool, "ot": bool}
    audio = {}  # iso -> {"nt": bool, "ot": bool}

    def mark(store, iso, canon):
        family = "nt" if canon in ("nt", "ntp") else "ot" if canon in ("ot", "otp") else None
        if family:
            store.setdefault(iso, {"nt": False, "ot": False})[family] = True

    idx = json.loads((CATALOG_DIR / "index.json").read_text())
    for row in idx["entries"]:
        mark(text, row[0], row[1])

    aidx = json.loads((CATALOG_DIR / "audio-index.json").read_text())
    for row in aidx["entries"]:
        mark(audio, row[0], row[1])

    timed = {}  # iso -> {"nt": bool, "ot": bool}
    if MEDIA_INDEX_FILE.exists():
        media_index = json.loads(MEDIA_INDEX_FILE.read_text())
        for iso, entry in media_index.get("l", {}).items():
            timed[iso] = {
                "nt": entry.get("n", {}).get("m") == "at",
                "ot": entry.get("o", {}).get("m") == "at",
            }

    isos = set(text) | set(audio) | set(timed)
    signals = {}
    for iso in isos:
        t = text.get(iso, {"nt": False, "ot": False})
        a = audio.get(iso, {"nt": False, "ot": False})
        tm = timed.get(iso, {"nt": False, "ot": False})
        signals[iso] = {
            "nt": (t["nt"], a["nt"], tm["nt"]),
            "ot": (t["ot"], a["ot"], tm["ot"]),
        }
    return signals


def load_obs_signals():
    """{iso: (text, audio, timed)} for every published OBS language."""
    signals = {}
    if not OBS_DIR.exists():
        return signals
    for media_path in OBS_DIR.glob("*/media.json"):
        media = json.loads(media_path.read_text())
        iso = media["iso"]
        signals[iso] = (
            media.get("storyCount", 0) > 0,
            media.get("audioStories", 0) > 0,
            media.get("timingStories", 0) > 0,
        )
    return signals


def load_names():
    """{iso: {"n": ..., "v": ..., "s": ...}} merged from media-index.json + door43 fallback."""
    names = {}
    if MEDIA_INDEX_FILE.exists():
        media_index = json.loads(MEDIA_INDEX_FILE.read_text())
        for iso, entry in media_index.get("l", {}).items():
            nm = {"n": entry["nm"]}
            if "v" in entry:
                nm["v"] = entry["v"]
            if "sc" in entry:
                nm["s"] = entry["sc"]
            names[iso] = nm

    if OBS_REPOS_FILE.exists():
        repos = json.loads(OBS_REPOS_FILE.read_text())
        for detail in repos.values():
            iso = normalize_obs_iso(detail["iso"])
            if iso not in names and detail.get("language_title"):
                names[iso] = {"n": detail["language_title"]}

    return names


def build(names: dict, bible_signals: dict, obs_signals: dict) -> dict:
    canons = {"nt": {}, "ot": {}, "obs": {}}
    all_isos = set(names) | set(bible_signals) | set(obs_signals)

    for iso in all_isos:
        entry = names.get(iso, {"n": iso})  # iso itself as a last-resort label, never silently dropped

        bs = bible_signals.get(iso)
        if bs:
            for canon in ("nt", "ot"):
                cat = classify(*bs[canon])
                if cat:
                    canons[canon].setdefault(cat, {})[iso] = entry

        os_ = obs_signals.get(iso)
        if os_:
            cat = classify(*os_)
            if cat:
                canons["obs"].setdefault(cat, {})[iso] = entry

    return canons


def write_mini(canons: dict) -> dict:
    return {
        canon: {cat: sorted(langs.keys()) for cat, langs in cats.items()}
        for canon, cats in canons.items()
    }


def main():
    args = sys.argv[1:]
    out_dir = Path(args[args.index("--out") + 1]) if "--out" in args else CATALOG_DIR

    names = load_names()
    bible_signals = load_bible_signals()
    obs_signals = load_obs_signals()
    canons = build(names, bible_signals, obs_signals)

    total_languages = len({iso for cats in canons.values() for langs in cats.values() for iso in langs})

    full = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_languages": total_languages,
        },
        "canons": canons,
    }
    mini = {
        "metadata": full["metadata"],
        "canons": write_mini(canons),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "langs.json").write_text(
        json.dumps(full, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "langs-mini.json").write_text(
        json.dumps(mini, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )
    print(f"[generate-langs-catalog] {total_languages} language(s) -> {out_dir}/langs.json, langs-mini.json")


if __name__ == "__main__":
    main()
