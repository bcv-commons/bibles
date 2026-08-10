"""Per-document dynamic enum tables (ids/wordLike/notWordLike/scopeBits/
graftTypes) — the write-side counterpart of ../pkf-decode-py/succinct.py's
enum_index()/enum_indexes(). Assigns each distinct string an index in
first-encounter order and finalizes to a ByteArray of counted strings.

Enum *order* doesn't need to match what the real proskomma-core would
assign for the same input — decode only ever looks entries up by the index
this same encoder wrote, so any consistent order round-trips correctly (see
this package's README for why the round-trip bar removes that constraint).
"""
from byte_array import ByteArray


class EnumBuilder:
    def __init__(self):
        self._index = {}
        self._order = []

    def get_index(self, s):
        if s not in self._index:
            self._index[s] = len(self._order)
            self._order.append(s)
        return self._index[s]

    def finalize(self):
        ba = ByteArray()
        for s in self._order:
            ba.push_counted_string(s)
        return ba


class Enums:
    def __init__(self):
        self.ids = EnumBuilder()
        self.word_like = EnumBuilder()
        self.not_word_like = EnumBuilder()
        self.scope_bits = EnumBuilder()
        self.graft_types = EnumBuilder()

    def by_category(self, category):
        return {
            "ids": self.ids,
            "wordLike": self.word_like,
            "notWordLike": self.not_word_like,
            "scopeBits": self.scope_bits,
            "graftTypes": self.graft_types,
        }[category]

    def finalize(self):
        return {
            "ids": self.ids.finalize().base64(),
            "wordLike": self.word_like.finalize().base64(),
            "notWordLike": self.not_word_like.finalize().base64(),
            "scopeBits": self.scope_bits.finalize().base64(),
            "graftTypes": self.graft_types.finalize().base64(),
        }
