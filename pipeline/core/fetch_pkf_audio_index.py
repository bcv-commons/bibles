#!/usr/bin/env python3
"""PKF's audio and verse timing, per language and book, into internal-data/pkf-audio-index.json.

PKF (se-regional-pwa, cdn.bibel.wiki/pkf/) publishes timing at
pkf/<iso>/timing/<BOOK>-<chapter>.json, and pkf/<iso>/info.json lists each language's audio:
media.audio.items[] with the file name, `src`, `hasTiming` and `timingFile` (e.g.
"C01-02-MAT-01-timing.txt"; its book code can be mixed case, "-Heb-"). Two kinds of audio:

- DBT audio, `src` "h1"/"h2"/... (SAB's fcbh source): PKF's apps stream it from DBT
  (se-regional-pwa, 2026-10-28). The DBT fileset is in the file name, in one of four forms:
    B01___01_Matthew_____ACAWBTP2DA.mp3     (DBT's old names, padded book name)
    B07___01_1CorinthiansADETBLN2DA.mp3     (same, book name fills the padding)
    B01___01_Matthew_______N1IZZTBL.mp3     (old DAM id: N1 + IZZTBL = IZZTBLN1DA)
    BSNWBTN2DA_B03_LUK_001.mp3              (DBT's new names)
  Recorded under "filesets", timed books only: it counts toward the DBT editions' timing.
- Everything else ("d1", "d2", "a1", ...): audio PKF gets from elsewhere, mostly
  scriptureearth.org, playable without a key. Its URL is the item's `url`, else
  media.audio.base_url + "/" + filename, else
  https://www.scriptureearth.org/data/<iso>/audio/<filename> (the folder PKF's own `url`s and
  base_urls point to; 2026-10-28: every such guess sampled answered), percent-encoded
  (file names can have spaces: "ded_01_01-Gen 01.mp3"). Recorded under "own":
  media.json lists it as the language's PKF edition, <ISO>PKF. One request per (language, src)
  checks the first file answers with audio; a src that doesn't is left out ("dropped": e.g.
  huv's and poe's "a1", copies of DBT files that aren't on scriptureearth.org). Items with no
  book and chapter (trc's "d3" summaries) are left out too.

Since 2026-10-29 (se-regional-pwa's client-data-spec §8) every item has bookCode and chapter,
DBT items a damId, media.audio.sources maps each src to its type ("fcbh" = DBT, "download",
"assets" = bundled in the app), and every non-DBT item its percent-encoded url, or null where
the app doesn't reveal it (huv, maj, nhw, poe "a1"). Those fields are used when present; the
file-name and URL rules above remain for info.json published before that. Two exceptions:
- An old-style file name names the fileset the file is in; damId is used when the file name
  contains it or is a new-style one (bsn: BSNWBTN2DA_B03_LUK_001.mp3 is in BSNTBLN2DA), else
  the file name's fileset. Since 2026-10-29 PKF sets damId per item to that fileset; until
  then, in 9 languages (ame, fab, icr, kmu, kqe, kxf, maj, moa, plu) it was the source's, and
  PKF's `size` matched the file name's fileset byte for byte.
- Items whose book isn't a Bible book, or whose chapter the book doesn't have, are left out
  (trc: a hymnal B001, Genesis summaries XXA, a radio programme XXB; enq's INT 0).

A book counts as timed when PKF timed any of its chapters, as for align-index.json.

    {"checked_at": "...", "languages": 334,
     "filesets": {"<iso>": {"<DBT audio fileset>": ["MAT", ...]}},
     "own": {"<iso>": {"src": ["d1"], "audio": {"MAT": [1, 2, ...]}, "timing": {"MAT": [1, ...]}}},
     "dropped": {"<iso>": {"<src>": "<status of the checked URL>"}}}

No key needed. Usage: python3 pipeline/core/fetch_pkf_audio_index.py
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import DATA, INTERNAL_DATA  # noqa: E402
from generate_vrs_map import load_vrs  # noqa: E402

CHAPTERS = {book: max(chs) for book, chs in load_vrs(DATA / "vrs" / "eng.vrs").items()}

OUT = INTERNAL_DATA / "pkf-audio-index.json"
PKF = "https://cdn.bibel.wiki/pkf"
UA = {"User-Agent": "Mozilla/5.0 (bcv-commons/bibles)"}   # Cloudflare refuses urllib's own

FILESET_RE = (re.compile(r"^([A-Z0-9]{10})_[AB]\d\d_"),        # DBT's new names
              re.compile(r"([A-Z0-9]{10})\.mp3$"))             # DBT's old names
OLD_DAM_RE = re.compile(r"_([NOP][12])([A-Z0-9]{6})\.mp3$")     # N1IZZTBL -> IZZTBLN1DA
TIMING_FILE_RE = re.compile(r"-([1-4A-Za-z]{3})-(\d+)-timing\.txt$")


def get_json(url: str, tries: int = 4):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError(f"failed after {tries} tries: {url}")


def audio_status(url: str, tries: int = 3) -> str:
    """"ok" if the URL answers with audio, else what it answered."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, method="HEAD", headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                kind = r.headers.get("Content-Type", "")
                return "ok" if kind.startswith("audio/") else f"not audio: {kind}"
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410):
                return f"http {e.code}"
        except Exception:
            pass
        time.sleep(2 ** attempt)
    return "no answer"


def is_dbt(audio: dict, item: dict) -> bool:
    kind = ((audio.get("sources") or {}).get(item.get("src")) or {}).get("type")
    return kind == "fcbh" if kind else str(item.get("src", "")).startswith("h")


def dbt_fileset(item: dict) -> str | None:
    filename = item.get("filename") or ""
    dam_id = item.get("damId")
    if dam_id and dam_id in filename:
        return dam_id
    m = OLD_DAM_RE.search(filename)
    if m:
        return m.group(2) + m.group(1) + "DA"
    m = FILESET_RE[1].search(filename)          # old-style name: its fileset, not damId
    if m:
        return m.group(1)
    if dam_id:
        return dam_id
    m = FILESET_RE[0].search(filename)
    return m.group(1) if m else None


def book_chapter(audio: dict, item: dict) -> tuple[str, int] | None:
    """bookCode and chapter; in older info.json (no sources) timingFile goes first, as its
    bookCode could be wrong (ztp's Ruth was "RTH")."""
    m = None if audio.get("sources") else TIMING_FILE_RE.search(item.get("timingFile") or "")
    if m:
        return m.group(1).upper(), int(m.group(2))
    if item.get("bookCode") and item.get("chapter"):
        return str(item["bookCode"]).upper(), int(item["chapter"])
    m = TIMING_FILE_RE.search(item.get("timingFile") or "")
    return (m.group(1).upper(), int(m.group(2))) if m else None


def is_chapter(bc: tuple[str, int] | None) -> bool:
    """A Bible book and one of its chapters (0: an introduction)."""
    return bool(bc) and bc[0] in CHAPTERS and 0 <= bc[1] <= CHAPTERS[bc[0]]


def own_url(iso: str, audio: dict, item: dict) -> str | None:
    """Percent-encoded: some file names have spaces and parentheses (ded, gvs)."""
    if audio.get("sources"):          # PKF's own url, already encoded; None where unknown
        return item.get("url")
    if item.get("url"):
        url = item["url"]
    elif audio.get("base_url"):
        url = f"{audio['base_url'].rstrip('/')}/{item['filename']}"
    else:
        url = f"https://www.scriptureearth.org/data/{iso}/audio/{item['filename']}"
    return urllib.parse.quote(url, safe=":/%")


def main():
    languages = get_json(f"{PKF}/manifest.json")["languages"]
    isos = sorted(iso for iso, v in languages.items() if "a" in v.get("media", ""))
    with ThreadPoolExecutor(16) as ex:
        infos = dict(zip(isos, ex.map(lambda iso: get_json(f"{PKF}/{iso}/info.json"), isos)))

    filesets: dict = defaultdict(lambda: defaultdict(set))
    own_items: dict = defaultdict(lambda: defaultdict(list))   # iso -> src -> [(book, ch, item)]
    for iso, info in infos.items():
        audio = ((info or {}).get("media") or {}).get("audio") or {}
        for item in audio.get("items", []):
            bc = book_chapter(audio, item)
            if not is_chapter(bc):
                continue
            src = str(item.get("src", ""))
            if is_dbt(audio, item):
                fs = dbt_fileset(item)
                if fs and item.get("hasTiming"):
                    filesets[iso][fs].add(bc[0])
            elif own_url(iso, audio, item):
                own_items[iso][src].append((*bc, item))

    checks = [(iso, src, own_url(iso, infos[iso]["media"]["audio"], items[0][2]))
              for iso, by_src in own_items.items() for src, items in by_src.items()]
    with ThreadPoolExecutor(16) as ex:
        status = dict(zip([(i, s) for i, s, _ in checks], ex.map(lambda c: audio_status(c[2]), checks)))

    own: dict = {}
    dropped: dict = defaultdict(dict)
    for iso, by_src in sorted(own_items.items()):
        audio_ch, timing_ch, srcs = defaultdict(set), defaultdict(set), []
        for src, items in sorted(by_src.items()):
            if status[(iso, src)] != "ok":
                dropped[iso][src] = status[(iso, src)]
                continue
            srcs.append(src)
            for book, ch, item in items:
                audio_ch[book].add(ch)
                if item.get("hasTiming"):
                    timing_ch[book].add(ch)
        if srcs:
            own[iso] = {"src": srcs,
                        "audio": {b: sorted(c) for b, c in sorted(audio_ch.items())},
                        "timing": {b: sorted(c) for b, c in sorted(timing_ch.items())}}

    out = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "languages": len(isos),
        "filesets": {iso: {fs: sorted(b) for fs, b in sorted(v.items())} for iso, v in sorted(filesets.items())},
        "own": own,
        "dropped": dict(dropped),
    }
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    n_fs = sum(len(v) for v in filesets.values())
    print(f"[pkf-audio] {len(isos)} languages with audio; DBT: {n_fs} timed filesets in "
          f"{len(filesets)} languages; own audio: {len(own)} languages "
          f"({sum(1 for v in own.values() if v['timing'])} with timing); dropped: "
          f"{ {f'{i}/{s}': r for i, d in dropped.items() for s, r in d.items()} } "
          f"-> {OUT.relative_to(INTERNAL_DATA.parent)}")


if __name__ == "__main__":
    main()
