"""USX -> USJ with usfmtc, for editions whose source publishes USX but no Sofria (158 DBT
editions, 2026-10-17). A last resort: where the source publishes Sofria, use it and
verse_text.extract_sofria().

usfmtc reads USX as XML, so a `|` in text stays text (no protection needed, unlike USFM).
Gives the same verse text as the JS route (tools/usj-to-sofria/usx_to_sofria.mjs) and as
the source's own Sofria where both exist.

    from usx_to_usj import usx_to_usj
    usj = usx_to_usj(usx_text)        # one book
    chapters = extract_usj(usj)       # verse_text.py
"""
import tempfile
from pathlib import Path

import usfmtc


def usx_to_usj(usx_text: str) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".usx", delete=False, encoding="utf-8") as tf:
        tf.write(usx_text.lstrip("﻿"))
        path = tf.name
    try:
        return usfmtc.readFile(path).outUsj()
    finally:
        Path(path).unlink(missing_ok=True)
