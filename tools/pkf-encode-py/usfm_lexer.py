"""Tokenizes raw USFM text into a flat stream of markers/text, scoped to
"core Scripture text + word-level attributes + milestones" (not full
general USFM — see this package's README). Marker classification is a
fixed table rather than an attempt at full USFM-spec generality; unknown
markers raise rather than silently guessing.
"""
import re

HEADER_MARKERS = {"id", "usfm", "ide", "h", "toc1", "toc2", "toc3", "toca1", "toca2", "toca3", "rem", "sts"}

PARAGRAPH_MARKERS = {
    "mt1", "mt2", "mt3", "mt4", "mte1", "mte2", "ms1", "ms2", "mr",
    "s1", "s2", "s3", "s4", "sr", "r", "d", "sp",
    "p", "m", "pmo", "pm", "pmc", "pmr", "pi", "pi1", "pi2", "pi3", "pi4",
    "mi", "nb", "cls", "li", "li1", "li2", "li3", "li4", "pc",
    "q", "q1", "q2", "q3", "q4", "qc", "qr", "qm1", "qm2", "qm3", "qm4", "qa", "b",
    # front matter / book introduction — common enough in real content to be
    # worth including even though this package's scope is "core Scripture
    # text": structurally these are just ordinary paragraph-level blocks.
    "imt1", "imt2", "imt3", "imt4", "imte1", "imte2",
    "is", "is1", "is2", "ip", "ipi", "ipq", "ipr", "im", "imi", "imq", "imte",
    "iot", "io", "io1", "io2", "io3", "io4", "iex", "ie", "ib",
    "ili1", "ili2", "iq1", "iq2",
}

CHAR_MARKERS = {
    "bd", "it", "bdit", "em", "sc", "sup", "nd", "tl", "dc", "pn", "qs", "qt",
    "wj", "k", "ord", "sig", "sls", "add", "bk", "no", "rq",
    "ior",  # Introduction Outline Reference range — inline within \io, explicit close
}

NOTE_MARKERS = {"f": "footnote", "x": "xref"}
NOTE_CHAR_MARKERS = {"fr", "fq", "fqa", "fk", "fl", "fw", "fp", "ft", "fv", "fdc",
                      "xo", "xk", "xq", "xt", "xta", "xop", "xdc"}

MILESTONE_MARKERS = {"zaln"}  # \zaln-s ... \zaln-e — 'ts' handled separately per decode's mark path

_MARKER_RE = re.compile(
    r"\\([A-Za-z][A-Za-z0-9]*)(\*)?"
    r"(?:-(s|e))?"       # milestone -s/-e suffix
    r"([^\\\n]*)"        # rest of the marker's own line-fragment (attrs / leading text on paragraph markers)
)


class Token:
    __slots__ = ("kind", "tag", "value", "attrs", "is_end")

    def __init__(self, kind, tag=None, value=None, attrs=None, is_end=False):
        self.kind = kind  # 'header' | 'chapter' | 'verse' | 'para' | 'char_start' | 'char_end' |
                           # 'note_start' | 'note_end' | 'note_char_start' | 'note_char_end' |
                           # 'word_start' | 'word_end' | 'milestone_start' | 'milestone_end' | 'text'
        self.tag = tag
        self.value = value
        self.attrs = attrs or {}
        self.is_end = is_end

    def __repr__(self):
        return f"Token({self.kind!r}, tag={self.tag!r}, value={self.value!r}, attrs={self.attrs!r})"


_ATTR_RE = re.compile(r'([A-Za-z][A-Za-z0-9-]*)="([^"]*)"')


def _parse_attrs(s):
    return dict(_ATTR_RE.findall(s))


def _strip_one_leading_space(s):
    # decode's renderer hardcodes exactly one space after opening a
    # character-style/note-field/word wrapper tag (`\\{tag} `, see
    # ../pkf-decode-py/usfm_render.py's start_wrapper/startParagraph-note
    # actions) — real USFM source also conventionally has exactly one space
    # there, so without this the two combine into a double space.
    # Paragraph markers do NOT get this treatment: their renderer emits
    # `\n\\{tag}\n` (a newline, not a space) after the tag.
    return s[1:] if s[:1] == " " else s


def _split_word_content(rest):
    """'text|attr="val" attr2="val2"' -> ('text', {attr:val,...})."""
    if "|" not in rest:
        return rest.strip(), {}
    text, attr_str = rest.split("|", 1)
    return text.strip(), _parse_attrs(attr_str)


def tokenize(usfm_text):
    tokens = []
    pos = 0
    n = len(usfm_text)
    while pos < n:
        backslash = usfm_text.find("\\", pos)
        if backslash == -1:
            trailing = usfm_text[pos:]
            if trailing:
                tokens.append(Token("text", value=trailing))
            break
        if backslash > pos:
            tokens.append(Token("text", value=usfm_text[pos:backslash]))

        m = _MARKER_RE.match(usfm_text, backslash)
        if not m:
            raise ValueError(f"Malformed marker at position {backslash}: {usfm_text[backslash:backslash + 20]!r}")
        tag, star, milestone_suffix, rest = m.groups()
        pos = m.end()

        if milestone_suffix:
            base = tag
            if base not in MILESTONE_MARKERS and base != "ts":
                raise ValueError(f"Unsupported milestone marker \\{base}-{milestone_suffix}")
            if milestone_suffix == "s":
                attrs = _parse_attrs(rest)
                tokens.append(Token("milestone_start", tag=base, attrs=attrs))
            else:
                tokens.append(Token("milestone_end", tag=base))
            continue

        if tag == "c":
            tokens.append(Token("chapter", value=rest.strip()))
        elif tag == "v":
            # Only strip the leading space between \v and the number — the
            # trailing text after the number (e.g. "1 In the beginning...")
            # must keep its own whitespace exactly as-is (including right
            # up to the next marker), or a following inline marker like
            # \bd loses the space that belongs before it.
            stripped = rest.lstrip(" ")
            m2 = re.match(r"(\S+)(.*)", stripped, re.DOTALL)
            number, text = (m2.group(1), m2.group(2)) if m2 else (stripped, "")
            tokens.append(Token("verse", value=number))
            if text:
                tokens.append(Token("text", value=text))
        elif tag == "w":
            if star:
                tokens.append(Token("word_end"))
                if rest:
                    tokens.append(Token("text", value=rest))
            else:
                # _split_word_content() already fully strips the text part
                # (both sides), so there's no leading-space-doubling risk
                # here the way there is for char/note markers below.
                text, attrs = _split_word_content(rest)
                tokens.append(Token("word_start", attrs=attrs))
                if text:
                    tokens.append(Token("text", value=text))
        elif tag in HEADER_MARKERS:
            tokens.append(Token("header", tag=tag, value=rest.strip()))
        elif tag in PARAGRAPH_MARKERS:
            tokens.append(Token("para", tag=tag))
            if rest.strip():
                tokens.append(Token("text", value=rest))
        elif tag in NOTE_MARKERS:
            if star:
                tokens.append(Token("note_end", tag=tag))
                if rest:
                    tokens.append(Token("text", value=rest))
            else:
                tokens.append(Token("note_start", tag=tag))
                text = _strip_one_leading_space(rest)
                if text.strip():
                    tokens.append(Token("text", value=text))
        elif tag in NOTE_CHAR_MARKERS:
            # note-internal char markers are USUALLY self-closing-by-next-
            # marker (no explicit \fr*) — but some (confirmed for real:
            # \fv) DO also support an explicit closing marker in real
            # content. Handle both: an explicit close (star) triggers the
            # same close as auto-close-on-next-marker would, right away
            # rather than waiting; treating a star here as just another
            # open (as this package did before this fix) duplicates the
            # field instead of closing it.
            if star:
                tokens.append(Token("note_char_end", tag=tag))
                if rest:
                    tokens.append(Token("text", value=rest))
            else:
                tokens.append(Token("note_char_start", tag=tag))
                text = _strip_one_leading_space(rest)
                if text.strip():
                    tokens.append(Token("text", value=text))
        elif tag in CHAR_MARKERS:
            if star:
                tokens.append(Token("char_end", tag=tag))
                if rest:
                    tokens.append(Token("text", value=rest))
            else:
                nested = rest.startswith("+")
                text = rest[1:] if nested else rest
                tokens.append(Token("char_start", tag=tag, attrs={"nested": nested}))
                text = _strip_one_leading_space(text)
                if text:
                    tokens.append(Token("text", value=text))
        else:
            raise ValueError(f"Unsupported/unrecognized USFM marker \\{tag} — not in this package's "
                              f"header/paragraph/character/note/word/milestone marker tables")
    return tokens
