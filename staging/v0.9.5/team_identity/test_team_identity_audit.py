import unittest
from team_identity_audit import parse_entries,canon,NEW_CODE,parse_patch
from pathlib import Path
import tempfile,struct

class TeamIdentityUnitTests(unittest.TestCase):
    def test_normalized_aliases(self):
        self.assertEqual(canon('s.africa'),canon('SOUTH AFRICA'))
        self.assertEqual(canon('Dr Congo'),canon('DR CONGO'))
        self.assertEqual(canon('Czecho'),canon('CZECH'))
        self.assertNotEqual(canon('U.A.E.'),canon('QATAR'))
    def test_exact_country_replacement_count(self):
        self.assertEqual(len(NEW_CODE),17)
        self.assertEqual(NEW_CODE[23],'BIH')
        self.assertEqual(NEW_CODE[14],'CAN')
    def test_padded_names(self):
        source=b'\0Australia\0\0Qatar\0\0New Zealand\0\0'
        names=parse_entries(source,1,len(source))
        self.assertEqual([v for _,v in names],['Australia','Qatar','New Zealand'])
    def test_guard_malformed_patch(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.iss26p';p.write_bytes(b'ISS26X01'+struct.pack('<I',2))
            with self.assertRaises(ValueError):parse_patch(p)

if __name__=='__main__':unittest.main()