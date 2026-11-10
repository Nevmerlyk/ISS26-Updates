import unittest
from stage4_identity_preflight import (shared_style_risk,INTENDED,ROLE_STRINGS,REPLACED,STYLE_OFFSETS,STAGE3_SHA)

class Stage4PreflightTests(unittest.TestCase):
    def test_role_table_has_15_teams_and_330_players(self):
        self.assertEqual(len(ROLE_STRINGS),15)
        self.assertEqual(sum(len(x) for x in ROLE_STRINGS.values()),330)
        self.assertEqual(set(ROLE_STRINGS),REPLACED-{14,53})
    def test_9_position_mismatches(self):
        self.assertEqual(len(INTENDED),22)
        counts={slot:sum(a!=b for a,b in zip(source,INTENDED)) for slot,source in ROLE_STRINGS.items()}
        self.assertEqual(sum(counts.values()),9)
        self.assertEqual({slot:n for slot,n in counts.items() if n},{2:2,4:2,10:1,31:2,36:1,50:1})
    def test_shared_style_must_not_be_edited(self):
        m={13:7,20:7,32:7,33:7,40:7,44:7,23:7,34:24}
        self.assertEqual(shared_style_risk(m,7,23),[13,20,32,33,40,44])
        self.assertEqual(shared_style_risk(m,10,23),[])
    def test_exact_physical_offsets_and_sha_guard(self):
        self.assertEqual(STYLE_OFFSETS,[0x1e94cc,0x224c50])
        self.assertEqual(len(STAGE3_SHA),64)
    def test_all_roles_valid(self):
        self.assertEqual(set(INTENDED),{'G','D','M','F'})
        self.assertTrue(all(set(source)<={'G','D','M','F'} for source in ROLE_STRINGS.values()))

if __name__=='__main__':unittest.main()
