import unittest
from stage2_roster_case_patch import roster_base, recase, raw_offset, ROSTER_START, SLOT_STRIDE, NAMES_PER_ROSTER, CAPS_TEAM_SLOTS

class TeamRosterCaseTests(unittest.TestCase):
    def test_team_slot_layout_reverse_order(self):
        self.assertEqual(roster_base(53),293204)
        self.assertEqual(roster_base(24),299584)
        self.assertEqual(roster_base(0),304864)
        self.assertEqual(roster_base(0)+NAMES_PER_ROSTER*10,305084)
    def test_recase_preserves_player_name_shapes(self):
        for source,dest in [
            ('VOZINHA','Vozinha'),('DA COSTA','Da Costa'),('DA ROSA','Da Rosa'),
            ('K.PINA','K.Pina'),('W.SEMEDO','W.Semedo'),('TRUBIN','Trubin'),
            ('MATVIIENKO','Matviienko'),('PONOMARENK','Ponomarenk'),
            ('ZABARNYI','Zabarnyi')]:
            with self.subTest(name=source):
                self.assertEqual(recase(source),dest)
                self.assertEqual(len(source),len(dest))
    def test_only_uppercase_recased(self):
        with self.assertRaises(ValueError):recase('McTominay')
        with self.assertRaises(ValueError):recase('O\'Neill')
        self.assertEqual(CAPS_TEAM_SLOTS,{24,53})
    def test_form1_raw_address_uses_user_data_offset(self):
        self.assertEqual(raw_offset(24,0),24*2352+24)
        self.assertEqual(raw_offset(24,2048),25*2352+24)
        self.assertEqual(raw_offset(24,293204),(24+293204//2048)*2352+24+293204%2048)
    def test_illegal_team_slots_fail(self):
        for n in [-1,54,88]:
            with self.assertRaises(ValueError):roster_base(n)
if __name__=='__main__': unittest.main()
