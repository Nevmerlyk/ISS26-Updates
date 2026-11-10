import unittest
from build_bosnia_style10_assets import pack4,exact_large_bosnia,run,OUTPUT

class BosniaStyle10AssetTests(unittest.TestCase):
    def test_pack4_index_order(self):
        self.assertEqual(pack4([1,2,3,0]),b'\x21\x03')
    def test_pack4_rejects_invalid(self):
        with self.assertRaises(ValueError):pack4([1,2,3])
        with self.assertRaises(ValueError):pack4([1,16])
    def test_large_flag_has_3_semantic_colors(self):
        im=exact_large_bosnia()
        self.assertEqual(im.size,(64,28))
        self.assertEqual(set(im.getdata()),{1,2,3})
    def test_artwork_shapes(self):
        report=run(); assets=report['assets']
        self.assertEqual({v['4bpp_bytes'] for v in assets.values()},{192,96,896})
        for n,asset in assets.items():
            self.assertEqual((OUTPUT/(n+'.4bpp')).stat().st_size,asset['4bpp_bytes'])
        self.assertEqual(report['style'],10)
        self.assertEqual(report['status'],'ARTWORK READY FOR INTEGRATION, NOT ENOUGH TO FIX BOSNIA ALONE')

if __name__=='__main__':unittest.main()
