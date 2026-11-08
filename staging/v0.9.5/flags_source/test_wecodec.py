import unittest
from wecodec import decode, encode, DecodeError

class WECodecTests(unittest.TestCase):
    def test_roundtrip_binary(self):
        for data in (b'a',b'ab',b'AAA',b'ABC'*40,bytes(range(256))*8,
                     bytes(range(16))*500, b'\x00'*8192,
                     b'0123456789abcdef'*2000):
            stream=encode(data)
            rebuilt, consumed, commands=decode(stream,len(data))
            self.assertEqual(rebuilt,data)
            self.assertLessEqual(consumed,len(stream))

    def test_reject_bad_distance(self):
        with self.assertRaises(DecodeError):
            decode(b'\x01\x00\x00',5)

    def test_reject_truncation(self):
        with self.assertRaises(DecodeError):
            decode(b'\x00',2)

    def test_reject_unexpected_length(self):
        with self.assertRaises(DecodeError):
            decode(encode(b'HELLO'),6)

    def test_compressed_raw_packet(self):
        # control bit 1: C0, then 8 literal bytes, then next flag 1: FF (end).
        stream=b'\x03\xC0abcdefgh\xFF'
        self.assertEqual(decode(stream,8)[0],b'abcdefgh')

if __name__=='__main__':unittest.main()