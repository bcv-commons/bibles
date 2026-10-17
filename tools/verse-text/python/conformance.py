"""Conformance suite, Python side (../js/conformance.mjs is the JS side; both check the same files).

1. ../conformance/rules.json: the extraction rule (clean, the plain reader, USJ cases) and the
   content fingerprint on short synthetic inputs.
2. ../conformance/helloao/: 169 helloAO chapters (lexeme-aligner's handover). The whole chain:
   helloAO JSON -> chapter_to_usj -> extract_usj -> verse text, tokens, hashed lines, chapter
   text fingerprint; and the chapter content fingerprint (../conformance/content.expected.json).
3. With --dbt: ../conformance/dbt-cases.json, fetched live from DBT on every route (needs this
   repo's pipeline/core and DBT_API_KEY / BIBLE_API_KEY in .env).

Usage: python conformance.py [--dbt] [--write-content]
"""
import json
import sys
from pathlib import Path

from bcv_tokenize import TEXT_FP_VERSION, TOKENIZER_VERSION, fingerprints, tokenize, verse_line
from content_fingerprint import CONTENT_FP_VERSION, content, content_fingerprints
from helloao_to_usj import chapter_to_usj
from plain_text import extract_plain
from verse_text import clean, extract_usj

HERE = Path(__file__).resolve().parent
SUITE = HERE.parent / "conformance"
bad = 0


def fail(*msg):
    global bad
    bad += 1
    print("FAIL", *msg)


def chapter_map(verses):
    return {(1, int(v["verse"])): v["text"] for v in verses if v["verse"].isascii() and v["verse"].isdigit()}


def rules():
    r = json.loads((SUITE / "rules.json").read_text(encoding="utf-8"))
    fns = {"clean": clean, "plain": extract_plain, "usj": extract_usj, "content": content}
    n = 0
    for kind, cases in r.items():
        for c in cases:
            n += 1
            if fns[kind](c["in"]) != c["out"]:
                fail(kind, c["why"])
    return n


def helloao(write_content):
    path = SUITE / "content.expected.json"
    expected_content = {} if write_content else json.loads(path.read_text())
    n = 0
    for f in sorted((SUITE / "helloao").glob("*/*.expected.json")):
        e = json.loads(f.read_text(encoding="utf-8"))
        src = e["source"]
        name = f"{f.parent.name}/{f.name[: -len('.expected.json')]}"
        raw = json.loads(f.with_name(f.name.replace(".expected.", ".input.")).read_text(encoding="utf-8"))
        verses = extract_usj(chapter_to_usj(raw, src["book"])).get(str(src["chapter"]), [])
        got = {int(v["verse"]): v["text"] for v in verses if v["verse"].isdigit()}
        for v in e["verses"]:
            if got.get(v["verse"]) != v["text"]:
                fail("text", name, v["verse"])
            if tokenize(v["text"]) != v["tokens"] or verse_line(v["verse"], v["text"]) != v["line"]:
                fail("tokens", name, v["verse"])
        m = chapter_map(verses)
        if fingerprints(m)[1].get(1) != e["chapter_fp"]:
            fail("text fp", name)
        cfp = content_fingerprints(m)[1].get(1)
        if write_content:
            expected_content[name] = cfp
        elif expected_content.get(name) != cfp:
            fail("content fp", name)
        n += 1
    if write_content:
        path.write_text(json.dumps(expected_content, indent=1, sort_keys=True) + "\n")
    return n


def dbt():
    sys.path.insert(0, str(HERE.parents[2] / "pipeline" / "core"))
    import requests
    from download_language_content import get_text_content
    from usx_to_usj import usx_to_usj
    from verse_text import extract_sofria

    def fetch(route, fid, book, ch):
        r = get_text_content(fid, book, 1 if route == "usx" else ch)
        if not r:
            return None
        if route == "plain":
            return extract_plain(r["data"]) if r.get("type") == "verses" else None
        body = requests.get(r["data"], timeout=90).content.decode("utf-8", "replace").lstrip("﻿")
        return extract_sofria(json.loads(body)) if route == "sofria" else extract_usj(usx_to_usj(body)).get(str(ch))

    n = 0
    for c in json.loads((SUITE / "dbt-cases.json").read_text())["cases"]:
        for route, want in c["routes"].items():
            verses = fetch(route, want["id"], c["book"], c["chapter"])
            m = chapter_map(verses or [])
            got = (fingerprints(m)[1].get(1), content_fingerprints(m)[1].get(1))
            if got != (want["text_fp"], want["content_fp"]):
                fail("dbt", c["edition"], c["book"], c["chapter"], route)
            n += 1
    return n


if __name__ == "__main__":
    print(f"tokenizer v{TOKENIZER_VERSION}, text fingerprint v{TEXT_FP_VERSION}, content fingerprint v{CONTENT_FP_VERSION}")
    print(f"rules: {rules()} cases")
    print(f"helloAO: {helloao('--write-content' in sys.argv)} chapters")
    if "--dbt" in sys.argv:
        print(f"DBT: {dbt()} chapter routes")
    print(f"{bad} failures")
    sys.exit(1 if bad else 0)
