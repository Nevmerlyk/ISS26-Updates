import unittest
from wecodec import encode,decode
from repack import StreamSpan,replace_stream

class RepackTests(unittest.TestCase):
    def test_only_selected_bytes_change(self):
        original=b'PREFIX'+encode(b'abcdefg'*20)+bytes(100)+b'SUFFIX'
        span=StreamSpan(6,len(original)-6,140)
        desired=b'q'*140
        new=replace_stream(original,span,desired)
        self.assertEqual(new[:6],b'PREFIX')
        self.assertEqual(new[-6:],b'SUFFIX')
        self.assertEqual(len(new),len(original))
        self.assertEqual(decode(new[span.start:span.end],140)[0],desired)

    def test_reject_overgrown_payload(self):
        origin=encode(bytes(512))
        span=StreamSpan(0,len(origin),512)
        with self.assertRaisesRegex(ValueError,'allocated'):
            replace_stream(origin,span,bytes(range(256))*2)

if __name__=='__main__':unittest.main()