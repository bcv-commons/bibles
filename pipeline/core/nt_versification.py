"""New Testament numbering of one edition, from its chapter lengths: which TVTMS variants
(_vrs/map/nt-variants.json) it follows, as an index.json `nt` entry.

Used for PKF collections (lengths from their .vrs files, every chapter) and for DBT and
helloAO editions (lengths probed for the chapters TVTMS tests, nt_probes.py).
"""
import re

NT = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL", "1TH",
      "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"}


class NtClassifier:
    def __init__(self, schemes: dict, nt_variants: dict):
        """schemes: {name: {BOOK: {chapter: last verse}}}, eng included; nt_variants:
        nt-variants.json's document."""
        self.eng = schemes["eng"]
        self.by_chapter = {}
        for vid, v in nt_variants["variants"].items():
            book, chap = v["chapter"].split()
            last = int(re.search(r"has (\d+) verses", v["detect"]).group(1))
            self.by_chapter.setdefault((book, int(chap), last), vid)  # a plain id wins over a suffixed one
        self.tested = {(b, c) for b, c, _ in self.by_chapter}
        self.profiles = {tuple(sorted(p["variants"])): name
                         for name, p in nt_variants.get("profiles", {}).items()}
        # each scheme's own New Testament, as variants of eng: what its map already covers
        self.scheme_nt = {}
        for s, shape in schemes.items():
            if not any(b in shape for b in NT):
                continue
            vs, _ = self.variants_of({(b, c): n for b in NT for c, n in shape.get(b, {}).items()})
            self.scheme_nt[s] = vs

    def variants_of(self, lengths: dict) -> tuple[list[str], list[str]]:
        """lengths: {(BOOK, chapter): last verse}. -> (variants, unexplained chapters)."""
        variants, unexplained = set(), []
        for (b, c), n in lengths.items():
            if b not in NT:
                continue
            e = self.eng.get(b, {}).get(c)
            if e is None or n == e:
                continue
            vid = self.by_chapter.get((b, c, n))
            if vid:
                variants.add(vid)
            else:
                unexplained.append(f"{b} {c}")
        return sorted(variants), sorted(unexplained)

    def entry(self, lengths: dict, label: str, swap: dict | None = None) -> dict | None:
        """The `nt` entry for an edition labelled `label`, or None when its label's own
        map already describes its New Testament. swap: {variant id: replacement} for a
        variant refined by text (REV12-17 -> REV12-17esv)."""
        variants, unexplained = self.variants_of(lengths)
        if swap:
            variants = sorted(swap.get(v, v) for v in variants)
        base = label if label in self.scheme_nt else "eng"
        if variants == self.scheme_nt[base] and not unexplained:
            return None
        out = {"variants": variants}
        if tuple(variants) in self.profiles:
            out["profile"] = self.profiles[tuple(variants)]
        if unexplained:
            out["unexplained"] = unexplained
        return out
