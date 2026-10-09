"""Versification labels for PKF collections (cdn.bibel.wiki/pkf/), for
fingerprint_versification.py's index.json.

Each collection's manifest entry declares its versification (`vrs`): a standard scheme
name, or the hash of a custom Paratext .vrs file published at pkf/_vrs/<hash>.vrs.

- Declared standard scheme (eng, org, rso, ...): that scheme.
- Custom file, Old Testament: compared chapter by chapter with each of our schemes
  (at least MIN_OT_CHAPTERS in common). These files record what the translation
  contains, so a partly translated chapter is simply shorter (PSA 119 with 52 verses):
  a chapter only counts against a scheme when its length is another scheme's length for
  that chapter (evidence of another tradition). Chapters matching no scheme are
  `unexplained` (listed in the diagnostics). No conflicts: that scheme; up to NEAR:
  that scheme, listed as assumed (`near_match`); more: `irregular`. A file without an Old Testament takes its label from the New Testament
  side and is listed as assumed (`nt_only`).
- Custom file, New Testament: compared with eng.vrs. A differing chapter that matches a
  TVTMS variant (_vrs/map/nt-variants.json) is that variant; any other is
  `unexplained`. An `nt` entry is written only when the result is not what the
  label's own scheme already has (e.g. org's 2CO 13 and ACT 19); it carries the
  variants, a profile name when the set matches one, and the unexplained chapters.

Key: `pkf:<collection id>`, the .pkf file name without its content hash (aai_C01).
"""
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from nt_versification import NtClassifier

MIN_OT_CHAPTERS = 100
MIN_NT_CHAPTERS = 100
NEAR = 5
NT = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL", "1TH",
      "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"}
SCHEMES = ["eng", "org", "orgw", "rso", "vul", "catm", "lxx"]
_HASH = re.compile(r"^[0-9a-f]{16}$")


def parse_vrs(text: str) -> dict:
    """{BOOK: {chapter: last verse}} from a Paratext .vrs (mapping lines ignored)."""
    shape = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts or parts[0].startswith("#") or "=" in line:
            continue
        chapters = {}
        for tok in parts[1:]:
            c, _, v = tok.partition(":")
            if c.isdigit() and v.isdigit():
                chapters[int(c)] = int(v)
        if chapters:
            shape[parts[0]] = chapters
    return shape


def _diff(a: dict, b: dict, books) -> tuple[int, list]:
    """(chapters compared, [(book, chapter, a's last, b's last) that differ]) over books."""
    n, out = 0, []
    for book in books:
        if book not in a or book not in b:
            continue
        for c, v in a[book].items():
            if c in b[book]:
                n += 1
                if b[book][c] != v:
                    out.append((book, c, v, b[book][c]))
    return n, out


def fetch_custom(hashes, cache_dir: Path, base: str = "https://cdn.bibel.wiki/pkf/_vrs/") -> dict:
    """{hash: shape}, downloading each custom .vrs once into cache_dir."""
    cache_dir.mkdir(parents=True, exist_ok=True)

    def one(h):
        p = cache_dir / f"{h}.vrs"
        if not p.is_file():
            try:
                req = urllib.request.Request(base + f"{h}.vrs", headers={"User-Agent": "bibles-vrs/1"})
                p.write_bytes(urllib.request.urlopen(req, timeout=30).read())
            except Exception:
                return h, None
        return h, parse_vrs(p.read_text(encoding="utf-8", errors="replace"))

    with ThreadPoolExecutor(12) as ex:
        return dict(ex.map(one, sorted(set(hashes))))


def classify_pkf(manifest: dict, schemes: dict, nt_variants: dict, cache_dir: Path):
    """Returns (labels, assumed, nt, diagnostics), all keyed `pkf:<collection id>`.

    schemes: {name: shape} for SCHEMES; nt_variants: nt-variants.json's document.
    """
    ntc = NtClassifier(schemes, nt_variants)
    collections_ = [(iso, c) for iso, e in manifest.items() for c in e.get("collections", [])]
    custom = fetch_custom([c["vrs"] for _, c in collections_ if _HASH.match(str(c.get("vrs")))], cache_dir)
    labels, assumed, nt, diag = {}, {}, {}, {}
    for iso, c in collections_:
        key = f"pkf:{c['pkf'].split('.')[0]}"
        vrs = str(c.get("vrs") or "")
        if vrs in schemes:
            labels[key] = vrs
            continue
        shape = custom.get(vrs) if _HASH.match(vrs) else None
        if not shape:
            continue  # no declared scheme and no readable file: not labelled
        # Old Testament
        ot_books = [b for b in shape if b not in NT]
        ot_fit, ot_unexplained = [], []
        lengths = {}  # (book, chapter) -> {length: schemes with it}
        for s in SCHEMES:
            for b in ot_books:
                for ch, v in schemes[s].get(b, {}).items():
                    lengths.setdefault((b, ch), {}).setdefault(v, set()).add(s)
        for s in SCHEMES:
            n, d = _diff(shape, schemes[s], ot_books)
            if n < MIN_OT_CHAPTERS:
                continue
            conflicts = [x for x in d if x[2] in lengths.get((x[0], x[1]), {})]
            ot_fit.append((len(conflicts), SCHEMES.index(s), s, conflicts))
        if ot_fit:
            ot_unexplained = sorted(f"{b} {ch}" for b in ot_books for ch, v in shape[b].items()
                                    if (b, ch) in lengths and v not in lengths[(b, ch)])
        # New Testament, against eng
        nt_lengths = {(b, ch): v for b in shape if b in NT for ch, v in shape[b].items()}
        n_nt = len(nt_lengths)
        variants, _ = ntc.variants_of(nt_lengths)
        if ot_fit:
            k, _, s, d = min(ot_fit)
            info = {"nearest": s, "conflicts": [f"{b} {ch}: {v} vs {w}" for b, ch, v, w in d[:20]]}
            if ot_unexplained:
                info["unexplained"] = ot_unexplained[:40]
            if k == 0:
                labels[key] = s
            elif k <= NEAR:
                labels[key] = s
                assumed[key] = "near_match"
            else:
                labels[key] = "irregular"
            if k or ot_unexplained:
                diag[key] = info
            if k > NEAR:
                continue
        elif n_nt >= MIN_NT_CHAPTERS:
            # no Old Testament: label by the scheme whose own NT this is, else eng
            s = next((s for s, sv in ntc.scheme_nt.items() if sv == variants and s != "eng"), "eng")
            labels[key] = s
            assumed[key] = "nt_only"
        else:
            continue
        if n_nt < MIN_NT_CHAPTERS:
            continue
        e = ntc.entry(nt_lengths, labels[key])
        if e:
            nt[key] = e
    return labels, assumed, nt, diag
