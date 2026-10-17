"""Verse text from plain verse JSON (DBT's text_plain filesets): the reading rule for the
plain-text route, used only where an edition has no structured text (no Sofria, no USX).
Not a conversion: the result is the same list of verses the other extractors give.

    extract_plain(items) -> [{"verse": v, "text": t}, ...]
    items: DBT's per-chapter `data`, [{"verse_start", "verse_end", "verse_text", ...}, ...]

Rules (same as extract_usj / extract_sofria, plus what plain text needs):
- A verse is keyed by its first number (`verse_start`; a bridged 4-5 is verse 4). Several
  items with the same first number are joined by one space, in order.
- `~` is USFM's no-break space: read as a space.
- A literal `//` is USFM's optional line break, not text: read as a space.
- Then clean() from verse_text.py: proskomma's `| default="X"` -> `|X`, legacy formatting
  codes (|i |sc |r |d) dropped, whitespace collapsed and trimmed. A verse with no text is
  left out.
"""
from verse_text import Collector, clean


def extract_plain(items: list) -> list:
    out = Collector()
    for it in items or []:
        start = it.get("verse_start")
        if start is None:
            continue
        text = str(it.get("verse_text") or "").replace("~", " ").replace("//", " ")
        out.add(str(start), " " + text + " ")
    return out.result()
