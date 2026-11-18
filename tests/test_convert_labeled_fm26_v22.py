#!/usr/bin/env python3
import copy,unittest
import convert_labeled_fm26_v22 as m

RZ={'uid':'71100666','name':'Dmytro Riznyk','position':'GK ','dob':'1999/1/30','club':'Shakhtar Donetsk','nationality':'Ukraine','raw_attributes_7_84': '1;2;3;2;5;1;2;3;3;1;10;3;1;10;8;12;12;13;14;13;14;6;11;5;16;12;11;13;12;14;15;13;15;12;12;13;14;5;11;4;1;13;13;12;10;14;9;13;15;8;9;12;10;9;5;16;11;17;15;7;20;1;1;1;1;1;1;1;1;1;1;1;1;1'}
class ConversionTests(unittest.TestCase):
 def test_36_labeled_and_38_unlabeled(self):
  d=m.labeled(RZ)
  self.assertEqual(len(d),36)
  self.assertEqual(d['corners'],1);self.assertEqual(d['crossing'],2)
  self.assertEqual(d['dribbling'],3);self.assertEqual(d['off_the_ball'],5)
 def test_gk_special_missing_not_guessed(self):
  d=m.convert(m.labeled(RZ),True)
  self.assertEqual(len(d),15)
  for n in ['defense','response','technique','pass_accuracy','jump_power']:
   self.assertIsNone(d[n]['value']);self.assertEqual(d[n]['evidence'],'MISSING_GOALKEEPER_FIELD')
 def test_source_dribble_iss_scale(self):
  d=m.convert(m.labeled(RZ),True)
  self.assertEqual(d['dribble']['value'],13)
  self.assertEqual(d['curve']['value'],12)
 def test_cannot_guess_unnamed_goalkeeper_field(self):
  bad=copy.deepcopy(RZ)
  q=bad['raw_attributes_7_84'].split(';');q[41]='20';bad['raw_attributes_7_84']=';'.join(q)
  self.assertEqual(m.labeled(bad),m.labeled(RZ))
 def test_native_only_six_fields_changed(self):
  stats=m.convert(m.labeled(RZ),True)
  after,changed=m.native_profile(bytes.fromhex(m.ISS_RECORD_HEX),stats)
  self.assertEqual(set(changed),set(m.CORRECTION))
  self.assertEqual(len(after),12)
  self.assertEqual(int.from_bytes(after,'little')&15,0)
 def test_wrong_native_rec_fails(self):
  with self.assertRaises(ValueError):m.native_profile(b'\0'*12,m.convert(m.labeled(RZ),True))
 def test_invalid_source_raw_count(self):
  bad=copy.deepcopy(RZ);bad['raw_attributes_7_84']=';'.join(['10']*73)
  with self.assertRaises(ValueError):m.labeled(bad)
 def test_invalid_over20(self):
  bad=copy.deepcopy(RZ);q=bad['raw_attributes_7_84'].split(';');q[0]='30';bad['raw_attributes_7_84']=';'.join(q)
  with self.assertRaises(ValueError):m.labeled(bad)
 def test_outfield_conversion_named_skills(self):
  d=m.convert(m.labeled(RZ),False)
  self.assertEqual(len(d),15)
  self.assertEqual(d['stamina']['evidence'],'PARTIAL_NAMED_SOURCE')
  self.assertEqual(sum(x['value'] is None for x in d.values()),0)
if __name__=='__main__':unittest.main()
