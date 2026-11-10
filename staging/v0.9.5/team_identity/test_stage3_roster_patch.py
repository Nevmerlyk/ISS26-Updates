import unittest,json
from pathlib import Path
from stage3_roster_patch import validate_names,split_edit,TARGET_SLOTS
from stage2_roster_case_patch import raw_offset

ROOT=Path(__file__).resolve().parent
class Stage3RosterTests(unittest.TestCase):
    def test_all_15_teams_and_330_unique_names(self):
        data=json.loads((ROOT/'stage3_game_rosters_15.json').read_text())
        self.assertEqual(len(validate_names(data)),15)
        self.assertEqual(sum(map(len,data.values())),330)
    def test_no_cabo_verde_or_canada_overwrite(self):
        self.assertNotIn(14,TARGET_SLOTS);self.assertNotIn(53,TARGET_SLOTS)
    def test_bosnia_names_include_stars(self):
        bosnia=json.loads((ROOT/'stage3_game_rosters_15.json').read_text())['23']
        self.assertIn('Dzeko',bosnia);self.assertIn('Kolasinac',bosnia);self.assertIn('Vasilj',bosnia)
    def test_fixed_10_byte_fields_and_no_all_uppercase(self):
        data=json.loads((ROOT/'stage3_game_rosters_15.json').read_text())
        for names in data.values():
            for name in names:
                self.assertLessEqual(len(name.encode('ascii')),10)
                self.assertFalse(name.isupper())
    def test_no_name_can_cross_sector_in_single_edit(self):
        pieces=split_edit(2044,b'abcdefghij',b'ABCDEFGHIJ','test')
        self.assertEqual(len(pieces),2)
        self.assertEqual(pieces[0]['raw_offset'],raw_offset(24,2044))
        self.assertEqual(pieces[1]['raw_offset'],raw_offset(24,2048))
        self.assertEqual(len(bytes.fromhex(pieces[0]['expected_hex'])),4)
        self.assertEqual(len(bytes.fromhex(pieces[1]['expected_hex'])),6)
    def test_duplicate_roster_rejected(self):
        data=json.loads((ROOT/'stage3_game_rosters_15.json').read_text())
        data['23'][1]=data['23'][0]
        with self.assertRaises(ValueError):validate_names(data)
    def test_wrong_slot_count_rejected(self):
        data=json.loads((ROOT/'stage3_game_rosters_15.json').read_text())
        data.pop('52')
        with self.assertRaises(ValueError):validate_names(data)
if __name__=='__main__':unittest.main()
