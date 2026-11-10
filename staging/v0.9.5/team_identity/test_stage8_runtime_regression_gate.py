import struct,tempfile,unittest
from pathlib import Path
from stage8_runtime_regression_gate import sectors,changed_lbas,classify,stadium_extents

class RegressionGateTests(unittest.TestCase):
    def test_real_inventory(self):
        p=Path(__file__).with_name('stage6_gdc_extent_eu.txt')
        self.assertEqual(len(stadium_extents(p)),34)
    def test_compare_changed_sectors(self):
        self.assertEqual(changed_lbas({1:b'a',2:b'b'},{1:b'a',2:b'c',3:b'd'}),[2,3])
    def test_classify_stadium_changes(self):
        self.assertEqual(classify([5,10,12],{'GDC_X.BIN':(10,13)}),{'GDC_X.BIN':[10,12]})
    def test_full_patch_parsing(self):
        with tempfile.TemporaryDirectory() as t:
            file=Path(t)/'v.iss26p'
            file.write_bytes(b'ISS26X01'+struct.pack('<I',1)+struct.pack('<I',10)+b'G'*32+b'\0'*2352)
            self.assertEqual(set(sectors(file)),{10})
            file.write_bytes(file.read_bytes()[:-1])
            with self.assertRaises(ValueError):sectors(file)

if __name__=='__main__':unittest.main()
