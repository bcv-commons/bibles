#!/usr/bin/env python3
"""Generate export/door43-usj/<iso>/<repo>/<BOOK>.json — book-level USJ from Door43 aligned
Bibles (git.door43.org) — plus each edition's _meta.json (see edition_formats.py). Chapter-level
Sofria is the downstream step (tools/usj-to-sofria/convert_batch.mjs), as for openbible.

Why these editions: lexeme-aligner's full-alignments-manual-sa dataset publishes the word
alignments Door43's translators made in these texts (layers `<edition>+manual+door43`). Its
files are named by the text fingerprint of the edition's verse text, so a client needs exactly
that text to use them. Publishing it here saves every client fetching USFM from git.

Each edition is pinned to a commit (EDITIONS): the commit lexeme-aligner aligned (fetched
2026-09-26 from Door43-Catalog's master branch; byte-identical to its cache). The USFM is
cached under internal-data/downloads/door43/<repo>/<commit>/.

Conversion (unalign, then usfmtc as for eBible):
- Door43's alignment markup is dropped, keeping the words: \\zaln-s |...\\* and \\zaln-e\\*
  milestones, and the attributes of \\w word|...\\w* (the word stays, as plain text).
- translationStudio leftovers are dropped: \\ts\\* (chunk milestone; a bare `\\ts ` swallowed the
  next \\v in usfmtc) and empty \\s5 lines (chunk headings with no text; usfmtc put the next
  verse inside the heading, which removed 1,317 Nepali verses from verse text).

A repo is written only if its LICENSE.md is CC BY-SA 4.0 (or a more open licence) and its text
isn't already reachable from another source (the same comparison as generate_crosswire_usj.py).

Usage:
    python3 generate_door43_usj.py [--force] [--edition REPO]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_ebible_chapters as eb  # noqa: E402  (shared conversion and comparison helpers)
import generate_crosswire_usj as cw  # noqa: E402  (find_duplicate)
from edition_formats import FORMATS, write_meta  # noqa: E402
from verse_text import extract_usj  # noqa: E402  (on sys.path via generate_ebible_chapters)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, DOWNLOADS, EXPORT  # noqa: E402

HOST = "https://git.door43.org"
CACHE = DOWNLOADS / "door43"
DUPLICATES_FILE = API_CACHE / "door43" / "duplicates.json"
USJ_OUT_DIR = EXPORT / "door43-usj"

# repo -> (iso we catalog it under, owner, pinned commit). 2026-10-22: the nine Gateway Language
# texts of lexeme-aligner's full-alignments-manual-sa (its edition ids in the comment).
EDITIONS = {
    "hi_glt": ("hin", "Door43-Catalog", "851d96693614e06bfd7661acf4c6903af3e25619"),      # hin_higlt
    "bn_gst": ("ben", "Door43-Catalog", "fff4aadcc2948fe63845e70c2038fe692114c71b"),      # bengst
    "gu_glt": ("guj", "Door43-Catalog", "550ec220cb0afdd627cc3e4d02df681ce3ff07a0"),      # gujglt
    "kn_glt": ("kan", "Door43-Catalog", "bfd92e32864fb6cbb272964d228729e1dadcc548"),      # kan_knglt
    "mr_glt": ("mar", "Door43-Catalog", "79718d638754ce9b4162c39e15292cc90f49e26b"),      # marglt
    "ne_glt": ("npi", "Door43-Catalog", "1609359370bdf34269e20450b753a90196fa95ea"),      # npi_neglt
    "or_glt": ("ory", "Door43-Catalog", "e9b57f364477f2020b7cd708fd88590bf5b72cb9"),      # ory_orglt
    "te_glt": ("tel", "Door43-Catalog", "b4fdfdaaa1c5e55c688fe9aec69f7cb3cf9acbd0"),      # telglt
    "es-419_glt": ("spa", "Door43-Catalog", "d6f5a0cd1b4544424ff91e0b58a14c7f3f046b3b"),  # spa_es419glt
}
LANGUAGE_NOTE = {"es-419_glt": "Latin American Spanish (es-419), catalogued under spa"}
LICENCES = {  # LICENSE.md heading -> the licence we record
    "CC BY-SA 4.0": {"type": "CC BY-SA", "url": "https://creativecommons.org/licenses/by-sa/4.0/"},
    "CC BY 4.0": {"type": "CC BY", "url": "https://creativecommons.org/licenses/by/4.0/"},
}

ZALN = re.compile(r"\\zaln-s\s*\|[^\\]*\\\*|\\zaln-e\\\*")
WORD = re.compile(r"\\w\s+([^|\\]*?)(?:\|[^\\]*?)?\\w\*")
TS = re.compile(r"\\ts\b(?:\\\*)?")
EMPTY_S5 = re.compile(r"(?m)^\\s5[ \t]*$\n?")


def unalign(usfm: str) -> str:
    """Door43 aligned USFM -> plain USFM with the same text (see the module docstring)."""
    usfm = ZALN.sub("", usfm)
    usfm = WORD.sub(r"\1", usfm)
    usfm = TS.sub("", usfm)
    return EMPTY_S5.sub("", usfm)


def fetch(owner: str, repo: str, commit: str, name: str) -> str:
    f = CACHE / repo / commit / name
    if not f.exists():
        body = eb.http_get(f"{HOST}/{owner}/{repo}/raw/commit/{commit}/{name}")
        if body is None:
            raise SystemExit(f"[door43] could not download {repo}/{name} at {commit[:10]}")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(body)
    return f.read_text(encoding="utf-8")


def usfm_files(owner: str, repo: str, commit: str) -> list[str]:
    f = CACHE / repo / commit / "_contents.json"
    if not f.exists():
        body = eb.http_get(f"{HOST}/api/v1/repos/{owner}/{repo}/contents?ref={commit}")
        if body is None:
            raise SystemExit(f"[door43] could not list {repo} at {commit[:10]}")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(body)
    return sorted(x["name"] for x in json.loads(f.read_text()) if x["name"].endswith(".usfm"))


def manifest_field(manifest: str, key: str) -> str | None:
    """A top-level dublin_core field (two-space indent) from manifest.yaml, without a YAML parser."""
    m = re.search(rf"(?m)^  {key}: ['\"]?(.*?)['\"]?\s*$", manifest)
    return m.group(1) if m else None


def licence(text: str) -> dict | None:
    for name, lic in LICENCES.items():
        if f"({name})" in text:
            return lic
    return None


def process(repo: str, iso: str, owner: str, commit: str, force: bool) -> None:
    out = USJ_OUT_DIR / iso / repo
    if out.exists() and not force:
        print(f"[door43] {repo}: already written (--force redoes it)")
        return
    lic = licence(fetch(owner, repo, commit, "LICENSE.md"))
    if lic is None:
        print(f"[door43] {repo}: skipped, LICENSE.md is not a licence we can republish under")
        return
    manifest = fetch(owner, repo, commit, "manifest.yaml")
    usj = {}
    for name in usfm_files(owner, repo, commit):
        book = name.split("-", 1)[1].split(".")[0].upper()
        usj[book] = eb.convert_book(unalign(fetch(owner, repo, commit, name)))
    samples = {}
    for order in (eb.OT_FIRST, eb.NT_FIRST):
        b = next((x for x in order if x in usj), None)
        if b:
            samples[(b, "1")] = eb.letters(extract_usj(usj[b])["1"])
    dup, compared = cw.find_duplicate(iso, samples)
    print(f"[door43] {repo}: compared with {len(compared)} editions: " +
          ", ".join(f"{c['source']}:{c['edition']} {min(c['scores'].values()) if c['scores'] else '-'}" for c in compared))
    if dup:
        DUPLICATES_FILE.parent.mkdir(parents=True, exist_ok=True)
        known = json.loads(DUPLICATES_FILE.read_text()) if DUPLICATES_FILE.exists() else {}
        known[repo] = dup
        DUPLICATES_FILE.write_text(json.dumps(known, indent=1, ensure_ascii=False))
        print(f"[door43] {repo}: skipped, same text as {dup['source']}:{dup['edition']} {dup['scores']}")
        return
    out.mkdir(parents=True, exist_ok=True)
    for b, doc in usj.items():
        (out / f"{b}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    meta = {
        "name": manifest_field(manifest, "title"),
        "licenses": [lic],
        "provider": manifest_field(manifest, "publisher") or "Door43",
        "source": f"{HOST}/{owner}/{repo}/src/commit/{commit}",
        "door43": {"owner": owner, "repo": repo, "commit": commit,
                   "version": manifest_field(manifest, "version"), "issued": manifest_field(manifest, "issued")},
    }
    if repo in LANGUAGE_NOTE:
        meta["language_note"] = LANGUAGE_NOTE[repo]
    write_meta(out, meta, FORMATS)
    nv = sum(len(vs) for doc in usj.values() for vs in extract_usj(doc).values())
    print(f"[door43] {repo}: wrote {len(usj)} books, {nv} verses -> {out}")


def main():
    args = sys.argv[1:]
    only = args[args.index("--edition") + 1] if "--edition" in args else None
    for repo, (iso, owner, commit) in EDITIONS.items():
        if only in (None, repo):
            process(repo, iso, owner, commit, "--force" in args)


if __name__ == "__main__":
    main()
