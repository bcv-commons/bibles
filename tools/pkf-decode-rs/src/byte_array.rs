//! Port of tools/pkf-decode-py/byte_array.py (itself a port of proskomma-core's
//! util/byteArray.js, read-only subset). See that file's docstring.

use base64::{engine::general_purpose::STANDARD, Engine as _};

pub struct ByteArray {
    pub bytes: Vec<u8>,
}

impl ByteArray {
    pub fn from_base64(s: &str) -> Self {
        let bytes = STANDARD.decode(s).expect("invalid base64 in succinct data");
        ByteArray { bytes }
    }

    pub fn length(&self) -> usize {
        self.bytes.len()
    }

    pub fn byte(&self, n: usize) -> u8 {
        self.bytes[n]
    }

    /// Base-128 varint, low byte(s) first; a byte >127 marks the terminal
    /// byte and contributes (v - 128) to the value (byteArray.js nByte()).
    pub fn n_byte(&self, n: usize) -> u32 {
        let v = self.bytes[n] as u32;
        if v > 127 {
            v - 128
        } else {
            v + 128 * self.n_byte(n + 1)
        }
    }

    pub fn n_byte_length(&self, v: u32) -> usize {
        let mut v = v;
        let mut ret = 1;
        while v > 127 {
            v >>= 7;
            ret += 1;
        }
        ret
    }

    pub fn counted_string(&self, n: usize) -> String {
        let s_length = self.bytes[n] as usize;
        String::from_utf8(self.bytes[n + 1..n + 1 + s_length].to_vec())
            .expect("invalid utf8 in counted string")
    }
}
