import unittest
from datsel_primary import parse_primary
class DATSELValidationTests(unittest.TestCase):
    def test_rejects_truncated(self):
        with self.assertRaisesRegex(ValueError,'truncated'):
            parse_primary(b'\0'*16)
    def test_rejects_invalid_pointer(self):
        with self.assertRaisesRegex(ValueError,'bad pointer'):
            parse_primary(b'\0'*64)
if __name__=='__main__':unittest.main()