"""Write-side counterpart to ../pkf-decode-py/byte_array.py — port of
proskomma-core's util/byteArray.js push*/base64() methods. Encoding doesn't
need to replicate the real library's growth/allocation strategy exactly
(round-trip correctness only needs the bytes to be self-consistent, not
byte-identical to what proskomma-core itself would allocate), so this uses
a plain growable bytearray rather than mirroring byteArray.js's manual
Uint8Array grow() logic.
"""
import base64


class ByteArray:
    def __init__(self):
        self.byte_array = bytearray()

    @property
    def length(self):
        return len(self.byte_array)

    def push_byte(self, v):
        if not (0 <= v <= 255):
            raise ValueError(f"Expected value 0-255 when pushing to ByteArray, found {v}")
        self.byte_array.append(v)

    def push_bytes(self, values):
        for v in values:
            self.push_byte(v)

    def push_n_byte(self, v):
        # Base-128 varint, low byte(s) first; matches byte_array.py's n_byte()
        # read logic — a byte >127 is the terminal byte, contributing (v-128).
        if v < 0:
            raise ValueError(f"Expected positive number in push_n_byte, found {v}")
        if v < 128:
            self.push_byte(v + 128)
        else:
            self.push_byte(v % 128)
            self.push_n_byte(v >> 7)

    def push_counted_string(self, s):
        s_bytes = s.encode("utf-8")
        if len(s_bytes) > 255:
            raise ValueError(f"String too long for counted string ({len(s_bytes)} bytes): {s!r}")
        self.push_byte(len(s_bytes))
        self.byte_array.extend(s_bytes)

    def set_byte(self, n, v):
        self.byte_array[n] = v

    def byte(self, n):
        return self.byte_array[n]

    def base64(self):
        return base64.b64encode(bytes(self.byte_array)).decode("ascii")
