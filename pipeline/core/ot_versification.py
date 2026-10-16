"""Old Testament layout of one edition, from its chapter lengths: which variants
(_vrs/map/ot-variants.json) it follows, as an index.json `ot` entry.

Unlike the New Testament's `nt` entry, which lists every difference from eng, an `ot` entry
lists only the blocks where the edition differs from its OWN scheme's shape: the scheme
maps already cover thousands of Old Testament rows, and these variants are the places where
editions sharing a scheme disagree (generate_ot_variants.py). A block that differs from the
scheme but matches no variant is listed as `unexplained`.

Used for DBT and helloAO editions (lengths probed, ot_probes.py) and PKF collections
(lengths from their .vrs files).
"""


class OtClassifier:
    def __init__(self, schemes: dict, ot_variants: dict):
        """schemes: {name: {BOOK: {chapter: last verse}}}; ot_variants: ot-variants.json."""
        self.schemes = schemes
        self.blocks = {}  # (book, chapters tuple) -> {lengths tuple: variant id}
        for vid, v in ot_variants["variants"].items():
            refs = list(v["chapters"])
            book = refs[0].split()[0]
            chapters = tuple(int(r.split()[1]) for r in refs)
            self.blocks.setdefault((book, chapters), {})[tuple(v["chapters"].values())] = vid
        self.tested = sorted({(b, c) for b, cs in self.blocks for c in cs})

    def entry(self, lengths: dict, label: str) -> dict | None:
        """lengths: {(BOOK, chapter): last verse}; label: the edition's `l` scheme."""
        shape = self.schemes.get(label)
        if not shape:
            return None
        variants, unexplained = [], []
        for (book, chapters), known in sorted(self.blocks.items()):
            mine = tuple(lengths.get((book, c)) for c in chapters)
            if None in mine:
                continue  # block not in this edition (or not probed)
            base = tuple(shape.get(book, {}).get(c) for c in chapters)
            if mine == base:
                continue
            vid = known.get(mine)
            if vid:
                variants.append(vid)
            else:
                unexplained.append(f"{book} {chapters[0]}-{chapters[-1]}: " + "/".join(map(str, mine)))
        if not variants and not unexplained:
            return None
        out = {}
        if variants:
            out["variants"] = sorted(variants)
        if unexplained:
            out["unexplained"] = unexplained
        return out


def pkf_ot_entries(manifest: dict, labels: dict, cache_dir, otc: "OtClassifier") -> dict:
    """`ot` entries for PKF collections with a custom .vrs file (a collection that declares a
    standard scheme has that scheme's shape, so nothing to list)."""
    import pkf_versification as pv
    out = {}
    collections_ = [c for e in manifest.values() for c in e.get("collections", [])]
    custom = pv.fetch_custom([c["vrs"] for c in collections_ if pv._HASH.match(str(c.get("vrs")))], cache_dir)
    for c in collections_:
        key = f"pkf:{c['pkf'].split('.')[0]}"
        shape = custom.get(str(c.get("vrs") or ""))
        if not shape or key not in labels:
            continue
        lengths = {(b, ch): v for b, chs in shape.items() for ch, v in chs.items()}
        e = otc.entry(lengths, labels[key])
        if e:
            out[key] = e
    return out
