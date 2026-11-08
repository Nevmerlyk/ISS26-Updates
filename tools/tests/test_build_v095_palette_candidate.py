import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from build_v095_palette_candidate import physical_palette_zero_positions, sector_correction, SECTOR

class NationalPaletteTests(unittest.TestCase):
    def test_54_entries_bounded_without_ecc_overlap(self):
        offsets = list(physical_palette_zero_positions())
        self.assertEqual([slot for slot, _ in offsets], list(range(54)))
        self.assertEqual(len(set(physical for _, physical in offsets)), 54)
        for _, physical in offsets:
            self.assertGreaterEqual(physical % SECTOR, 24)
            self.assertLess(physical % SECTOR, 2071)
        self.assertEqual(offsets[0][1], 0xBF3B38)

    def test_ecc_edc_are_linear_in_palette_delta(self):
        a = sector_correction({24: bytes([1, 14])})
        b = sector_correction({34: bytes([15, 90])})
        joint = sector_correction({24: bytes([1, 14]), 34: bytes([15, 90])})
        self.assertEqual(bytes(x ^ y for x, y in zip(a, b)), joint)
        self.assertFalse(any(joint[:24]))
        self.assertTrue(any(joint[2072:2352]))

if __name__ == "__main__":
    unittest.main()
