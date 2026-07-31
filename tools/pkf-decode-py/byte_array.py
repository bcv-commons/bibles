"""Port of proskomma-core's util/byteArray.js — only the read-side methods
decode.mjs's call path actually exercises (byte/bytes/nByte/countedString/
fromBase64/length). Write-side methods (pushByte, grow, insert, ...) are not
needed for decoding and are intentionally omitted.
"""
import base64


class ByteArray:
    def __init__(self):
        self.byte_array = b""

    @property
    def length(self):
        return len(self.byte_array)

    def byte(self, n):
        return self.byte_array[n]

    def bytes(self, n, l):
        return self.byte_array[n:n + l]

    def n_byte(self, n):
        # Base-128 varint, low byte(s) first; a byte >127 marks the terminal
        # byte and contributes (v - 128) to the value (byteArray.js nByte()).
        v = self.byte_array[n]
        if v > 127:
            return v - 128
        return v + 128 * self.n_byte(n + 1)

    def n_byte_length(self, v):
        # byteArray.js nByteLength()
        ret = 1
        while v > 127:
            v = v >> 7
            ret += 1
        return ret

    def counted_string(self, n):
        s_length = self.byte_array[n]
        return self.byte_array[n + 1:n + 1 + s_length].decode("utf-8")

    def from_base64(self, s):
        self.byte_array = base64.b64decode(s)
