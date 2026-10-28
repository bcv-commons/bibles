"""Language parity, Python side: the same lines as ../js/dump.mjs, from verse_text.py.

With --fp, each line also carries the chapter's text fingerprint (tokenizer v3) and content
fingerprint (verses with a plain number only; a chapter with none gets "-").

Usage: python dump.py <usj-root> <sofria-root> [--fp] > py.tsv
"""
import hashlib
import json
import os
import sys

from bcv_tokenize import fingerprints
from content_fingerprint import content_fingerprints
from verse_text import extract_sofria, extract_usj

FP = "--fp" in sys.argv


def digest(verses):
    d = hashlib.sha256("".join(f"{v['verse']}\t{v['text']}\n" for v in verses).encode()).hexdigest()
    if not FP:
        return d
    m = {(1, int(v["verse"])): v["text"] for v in verses if v["verse"].isascii() and v["verse"].isdigit()}
    t, c = fingerprints(m)[1].get(1, "-"), content_fingerprints(m)[1].get(1, "-")
    return f"{d}\t{t}\t{c}"


def main(usj_root, sof_root):
    lines = []
    for root, _, files in os.walk(usj_root):
        for f in files:
            if not f.endswith(".json") or f == "_meta.json":
                continue
            path = os.path.join(root, f)
            rel = os.path.relpath(path, usj_root)[: -len(".json")]
            with open(path, encoding="utf-8") as fh:
                for ch, verses in extract_usj(json.load(fh)).items():
                    lines.append(f"usj\t{rel}\t{ch}\t{digest(verses)}")
            d = os.path.join(sof_root, rel)
            if os.path.isdir(d):
                for g in os.listdir(d):
                    with open(os.path.join(d, g), encoding="utf-8") as fh:
                        lines.append(f"sofria\t{rel}\t{g[:-len('.json')]}\t{digest(extract_sofria(json.load(fh)))}")
    sys.stdout.buffer.write(("\n".join(sorted(lines)) + "\n").encode())


if __name__ == "__main__":
    main(*sys.argv[1:3])
