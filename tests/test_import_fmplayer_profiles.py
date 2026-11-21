import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from import_fmplayer_profiles import parse_profile, converted, identity, checked_url

URL="https://fmplayer.net/fm-26/example-player-123"
# Synthetic fixture; not a real player's ratings.
PAGE="""# Example Player FM26 Profile
## Example Player
Example Club
AML, ST
Current Ability 140
Potential Ability 160
Age 24 y/o
* Nationality QAT
* Preferred Foot Right
* Left Foot 10
* Right Foot 20
* Height 177
All attributes are scaled from 1-20 to 10-200
* Pace 160
* Acceleration 170
* Stamina 130
* Natural Fitness 140
* Dribbling 180
* Off The Ball 150
* Anticipation 120
* Finishing 130
"""
ROW={"player_name":"Example Player","position_group":"FW","fm_uid_candidate":"123"}
ENTRY={"expected_uid":"123","expected_name":"Example Player","expected_nationality":"QAT"}

class ProfileTests(unittest.TestCase):
    def test_scale(self):
        p=parse_profile(PAGE,URL)
        self.assertEqual(p["raw"]["pace"],16)
        self.assertEqual(p["right_foot"],"20")
        self.assertEqual(p["ca"],"140")
        self.assertEqual(p["position"],"AML, ST")
        self.assertEqual(converted(p,"FW")["iss_stamina"],"17")
    def test_identity(self):
        p=parse_profile(PAGE,URL)
        self.assertEqual(identity(ROW,ENTRY,p),"candidate_uid_name_nationality_position_no_dob")
        self.assertEqual(identity(ROW,dict(ENTRY,expected_uid="999"),p),"uid_mismatch")
        self.assertEqual(identity(ROW,dict(ENTRY,expected_nationality="USA"),p),"nationality_conflict_or_missing")
        self.assertEqual(identity(dict(ROW,position_group="GK"),ENTRY,p),"position_conflict_or_missing")
    def test_missing(self):
        p=parse_profile(PAGE.replace("* Natural Fitness 140",""),URL)
        self.assertEqual(converted(p,"FW")["iss_stamina"],"")
    def test_conflicting_and_invalid_values(self):
        p=parse_profile(PAGE.replace("* Pace 160","* Pace 160\n* Pace 150").replace("Dribbling 180","Dribbling 185"),URL)
        self.assertNotIn("pace",p["raw"])
        self.assertNotIn("dribbling",p["raw"])
    def test_wrong_edition_or_scale(self):
        for body in (PAGE.replace("FM26 Profile","FM24 Profile"),PAGE.replace("All attributes are scaled from 1-20 to 10-200","Ratings from 1-99")):
            with self.assertRaises(ValueError):parse_profile(body,URL)
    def test_keeper(self):
        p=parse_profile(PAGE.replace("AML, ST","GK")+"\n* Aerial Reach 200\n* Jumping Reach 200\n* One on Ones 180\n* Command of Area 180\n* Positioning 160\n",URL)
        self.assertEqual(converted(p,"GK")["iss_jump_power"],"19")
        self.assertEqual(converted(p,"GK")["iss_defense"],"18")
    def test_html(self):
        html="<html><h1>Example Player FM26 Profile</h1><h2>Example Player</h2><div>GK</div><div>Current Ability <span>140</span></div><p>All attributes are scaled from 1-20 to 10-200</p><div><div>Pace</div><div>160</div></div></html>"
        p=parse_profile(html,URL)
        self.assertEqual(p["raw"]["pace"],16)
        self.assertEqual(p["position"],"GK")
    def test_url(self):
        for u in ("http://fmplayer.net/fm-26/p-123","https://other.invalid/fm-26/p-123","https://fmplayer.net/fm-24/p-123"):
            with self.assertRaises(ValueError):checked_url(u)

if __name__=="__main__":unittest.main()
