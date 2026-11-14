#!/usr/bin/env python3
"""Synthetic test of actual resource rewriting and independent sector composition."""
import io
import struct
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test27_gpu_stream_edit as stream
import test27_build_standalone_atlas_candidate as build
from test27_flag_art_4bpp import bgr555,COLORS
from v095_name_lz_codec import encode_stream,decode_stream,encode_stream_compact,encode_with_budget
from build_v095_test12_gdc_descriptor_repair import valid_parity

def palette():
    values=[0]+list(dict.fromkeys(bgr555(x) for flag in ("cape_verde","bosnia") for x in COLORS[flag][1:]))
    return struct.pack("<16H",*(values+[0]*(16-len(values))))

def resource(capacity=32768, *, noisy=True):
    base=0x800F0000
    w,h=64,140
    raw=bytearray(bytes([0x97])*(w*h*2))
    if noisy:
        import random
        rng=random.Random(27)
        for x,y in stream.TARGETS.values():
            for row in range(28):
                at=2*((y-256+row)*w+x-800)
                raw[at:at+32]=bytes(rng.randrange(256) for _ in range(32))
    raw=bytes(raw)
    packed=encode_stream(raw,expected_bytes=len(raw))
    start=32
    table=start+capacity
    if len(packed)>capacity: raise ValueError("Fixture capacity")
    blob=bytearray(table+32)
    struct.pack_into("<I",blob,0,base+table)
    blob[start:start+len(packed)]=packed
    struct.pack_into("<HHHHHHI",blob,table,10,800,256,w,h,0,base+start)
    struct.pack_into("<H",blob,table+16,255)
    return bytes(blob),raw,table

class Standalone(unittest.TestCase):
    def test_rewrite_two_nations_roundtrip_preserves_neighbor_pixels(self):
        blob,raw,table=resource()
        routes=build.find_routes(blob)
        self.assertEqual(len(routes),2)
        result,changes=stream.rewrite_resource(blob,routes,palette(),require_clut_sha=False)
        self.assertEqual(len(changes),2)
        self.assertEqual(result[table:],blob[table:])
        self.assertEqual(result[:32],blob[:32])
        decoded=decode_stream(result[32:table],expected_bytes=len(raw),max_padding=table-32)
        expected=raw
        _,uploads=stream.parse_uploads(blob,0x800F0000,0)
        for name,(x,y) in stream.TARGETS.items():
            art,_=stream.mapped_art(name,palette())
            expected=stream.change_tile(expected,uploads[0],x-800,y-256,art)
        self.assertEqual(decoded,expected)
        self.assertNotEqual(result,blob)
    def test_palette_matching_finds_distinct_non_greedy_solution(self):
        # Intended BGR red levels ~10 and 12 both prefer the same slot 11.
        # Only the first can use level 6 within the stated tolerance.
        colors=((0,0,0),(82,0,0),(99,0,0),(255,255,255))
        pal=struct.pack("<16H",0,11,6,0x7fff,*([0]*12))
        with patch.dict(stream.COLORS,{"bosnia":colors}):
            _,meta=stream.mapped_art("bosnia",pal)
        self.assertEqual(meta["index_map"],{1:2,2:1,3:3})

    def test_duplicate_palette_values_do_not_count_as_distinct_colors(self):
        colors=((0,0,0),(82,0,0),(99,0,0),(255,255,255))
        pal=struct.pack("<16H",0,11,11,0x7fff,*([0]*12))
        with patch.dict(stream.COLORS,{"bosnia":colors}):
            with self.assertRaisesRegex(ValueError,"merges distinct"):
                stream.mapped_art("bosnia",pal)

    def test_compact_codec_varied_and_boundary_inputs(self):
        import random
        rng=random.Random(27)
        for raw in (b"Z",b"AB"*40,bytes(range(256))*3,
                    bytes(rng.randrange(256) for _ in range(1100)),
                    b"Hello"*43+bytes(range(70))+b"Hello"*9):
            with self.subTest(n=len(raw)):
                encoded=encode_stream_compact(raw,expected_bytes=len(raw))
                self.assertEqual(decode_stream(encoded,expected_bytes=len(raw)),raw)

    def test_budget_fallback_selects_compact_packet(self):
        raw=b"XYZ"*500
        compact=encode_stream_compact(raw,expected_bytes=len(raw))
        # Unit-level test of fallback routing: simulate a valid but longer
        # initial attempt; the compact output must still round-trip.
        with patch("v095_name_lz_codec.encode_stream",return_value=compact+bytes(1)):
            packet,method=encode_with_budget(raw,expected_bytes=len(raw),capacity=len(compact))
        self.assertEqual(method,"compact_search")
        self.assertEqual(decode_stream(packet,expected_bytes=len(raw)),raw)

    def test_real_format_flags_nonzero_aux_and_after_table_stream(self):
        blob,raw,table=resource()
        base=0x800F0000
        packed=encode_stream(raw,expected_bytes=len(raw))
        late=bytearray(128+len(packed)+16)
        struct.pack_into("<I",late,0,base+32)
        struct.pack_into("<HHHHHHI",late,32,0x10A,800,256,64,140,7,base+128)
        struct.pack_into("<H",late,48,255)
        late[128:128+len(packed)]=packed
        late[128+len(packed):]=b"X"*16
        routes=build.find_routes(bytes(late))
        edited,info=stream.rewrite_resource(bytes(late),routes,palette(),require_clut_sha=False)
        self.assertEqual(edited[:128],late[:128])
        self.assertEqual(edited[-16:],b"X"*16)
        self.assertEqual(len(info),2)

    def test_multiple_roots_disjoint_uploads(self):
        blob,raw,table=resource()
        mod=bytearray(blob)
        second=table+32
        mod.extend(bytes(32))
        struct.pack_into("<I",mod,4,0x800F0000+second)
        struct.pack_into("<HHHHHHI",mod,second,9,0,0,1,1,5,0x800F0000+16)
        struct.pack_into("<H",mod,second+16,255)
        routes=build.find_routes(bytes(mod))
        edited,info=stream.rewrite_resource(bytes(mod),routes,palette(),require_clut_sha=False)
        self.assertEqual(edited[table:],mod[table:])

    def test_inferred_aligned_base_unique(self):
        blob,raw,table=resource()
        mod=bytearray(blob)
        base=0x800b8000
        struct.pack_into("<I",mod,0,base+table)
        struct.pack_into("<I",mod,table+12,base+32)
        self.assertEqual(build.find_routes(bytes(mod))[0]["gpu_base"],base)

    def test_repacked_table_offsets_are_not_geometry_changes(self):
        blob,raw,table=resource()
        base=0x800F0000
        moved=bytearray(blob[:table]+bytes(780)+blob[table:])
        struct.pack_into("<I",moved,0,base+table+780)
        self.assertNotEqual(build.canonical_lists(blob,base),build.canonical_lists(moved,base))
        self.assertEqual(build.target_signature(blob,base),build.target_signature(moved,base))
        routes=build.find_routes(moved,base)
        self.assertTrue(all(r["upload_offset"]==table+780 for r in routes))
        result,_=stream.rewrite_resource(bytes(moved),routes,palette(),require_clut_sha=False)
        self.assertEqual(result[table+780:],moved[table+780:])

    def test_physical_extent_excludes_unattributed_gap_records(self):
        clean={"BIN/DATSEL3.BIN":(100,54948),"BIN/NEXT.BIN":(150,2048)}
        same=dict(clean)
        self.assertEqual(build.physical_resource_size(clean,same,"BIN/DATSEL3.BIN",{}),
                         (100,54948,55296))
        self.assertEqual(build.physical_resource_size(clean,same,"BIN/DATSEL3.BIN",{128:None,150:None}),
                         (100,54948,55296))
        changed=dict(clean)
        changed["BIN/DATSEL3.BIN"]=(100,58000)
        self.assertEqual(build.physical_resource_size(clean,changed,"BIN/DATSEL3.BIN",{}),
                         (100,58000,59392))
        changed["BIN/DATSEL3.BIN"]=(101,58000)
        with self.assertRaisesRegex(ValueError,"extent moved"):
            build.physical_resource_size(clean,changed,"BIN/DATSEL3.BIN",{})

    def test_patched_disc_view_reads_verified_sector_not_raw_original(self):
        a=bytearray(2352)
        a[:12]=bytes.fromhex("00FFFFFFFFFFFFFFFFFFFF00")
        a[15]=2
        source=io.BytesIO(a)
        records={}
        build.compose_resource(source,records,0,bytes(12),b"T"*12)
        view=build.PatchedDiscView(source,records)
        view.seek(0)
        self.assertEqual(view.read(2352)[24:36],b"T"*12)
        view.seek(0)
        with self.assertRaisesRegex(ValueError,"non-sector"):
            view.read(10)

    def test_real_cross_boundary_fragments_and_short_cape_packet(self):
        import random
        rng=random.Random(27)
        base=0x800F0000
        rects=[(832,256,32,128,6306),(800,256,32,128,8192),(800,384,32,128,8192)]
        blob=bytearray(32)
        packets=[]
        for x,y,w,h,n in rects:
            raw=bytes(rng.randrange(256) for _ in range(n))
            packet=encode_stream(raw,expected_bytes=n)
            at=len(blob)
            blob.extend(packet)
            blob.extend(bytes((-len(blob))%4))
            packets.append((at,raw))
        table=len(blob)
        struct.pack_into("<I",blob,0,base+table)
        for (x,y,w,h,n),(at,raw) in zip(rects,packets):
            blob.extend(struct.pack("<HHHHHHI",10,x,y,w,h,0,base+at))
        blob.extend(struct.pack("<H",255)+bytes(14))
        routes=build.find_routes(bytes(blob),base)
        self.assertEqual([r["fragment"] for r in routes],
                         [[848,256,16,28],[816,368,16,16],[816,384,16,12]])
        self.assertEqual(routes[0]["decoded_bytes"],6306)
        edited,info=stream.rewrite_resource(bytes(blob),routes,palette(),require_clut_sha=False)
        self.assertEqual(len(info),3)
        self.assertEqual(edited[table:],blob[table:])
        t,rows=stream.parse_uploads(edited,base,0)
        reconstructed={}
        for route in routes:
            u=rows[route["upload_index"]]
            raw,_=stream.stream_span(edited,base,t,rows,u)
            old=packets[route["upload_index"]][1]
            self.assertEqual(len(raw),len(old))
            art,_=stream.mapped_art(route["flag"],palette())
            self.assertEqual(raw,stream.fragment_replace(old,u,route["fragment"],art,route["flag"]))
            reconstructed.setdefault(route["flag"],bytearray()).extend(stream.fragment_read(raw,u,route["fragment"]))
        for name,data in reconstructed.items():
            self.assertEqual(bytes(data),stream.mapped_art(name,palette())[0])

    def test_short_packet_cannot_supply_missing_fragment(self):
        u=stream.Upload(100,10,800,256,32,128,32)
        with self.assertRaisesRegex(ValueError,"beyond actual decoded prefix"):
            stream.fragment_read(bytes(6306),u,(816,368,16,16))

    def test_wrong_hash_blocks_source_write(self):
        blob,_,_=resource()
        routes=build.find_routes(blob)
        routes[0]["old_tile_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"pre-edit tile"):
            stream.rewrite_resource(blob,routes,palette(),require_clut_sha=False)
    def test_no_usable_palette_refuses_edit(self):
        with self.assertRaisesRegex(ValueError,"No safe opaque"):
            stream.mapped_art("bosnia",bytes(32))
    def test_ambiguous_or_missing_gpu_upload_rejected(self):
        blob,_,table=resource()
        dup=bytearray(blob)
        struct.pack_into("<H",dup,table+2,850)
        with self.assertRaises(ValueError):
            build.find_routes(bytes(dup))
    def test_insufficient_stream_size_never_relocates_resource(self):
        big,raw,_=resource(noisy=False)
        capacity=(len(encode_stream(raw,expected_bytes=len(raw)))+3)&~3
        blob,_,_=resource(capacity,noisy=False)
        routes=build.find_routes(blob)
        with self.assertRaisesRegex(ValueError,"capacity"):
            stream.rewrite_resource(blob,routes,palette(),require_clut_sha=False)
    def test_style_collision_guard(self):
        # Five real tables are checked by build(); unit check one complete map.
        table=bytearray([20]*78)
        table[0]=1
        table[30]=55
        table[54]=10
        self.assertTrue(build.check_style_table(bytes(table))["bosnia_unique"])
        table[55]=55
        with self.assertRaisesRegex(ValueError,"collision"):
            build.check_style_table(bytes(table))
    def test_independent_xor_sector_add_and_preserve_tail(self):
        original=bytearray(2352)
        original[:12]=bytes.fromhex("00FFFFFFFFFFFFFFFFFFFF00")
        original[15]=2
        original[24:2072]=bytes([19])*2048
        old=bytes([19])*80
        new=bytes([21])*80
        source=io.BytesIO(original)
        records={}
        changed=build.compose_resource(source,records,0,old,new)
        self.assertEqual(changed,[0])
        guard,mask=records[0]
        self.assertEqual(guard.hex().upper(),stream.sha(original))
        self.assertTrue(valid_parity(mask))
        reconstructed=bytes(x^y for x,y in zip(original,mask))
        self.assertEqual(reconstructed[24:104],new)
        self.assertEqual(reconstructed[104:2072],original[104:2072])
        self.assertEqual(reconstructed[:24],original[:24])
        data=build.serialize(records)
        self.assertEqual(build.records_from_patch(data,stream.sha(data),1),records)
    def test_audio_and_non_target_records_unchanged_in_composition(self):
        a=bytearray(2352)
        a[:12]=bytes.fromhex("00FFFFFFFFFFFFFFFFFFFF00")
        a[15]=2
        a[24:2072]=bytes([21])*2048
        # Second record stands in for a wholly unrelated previous patch sector.
        source=io.BytesIO(a+a)
        records={1:(b"q"*32,b"\x00"*2352)}
        unchanged=records[1]
        build.compose_resource(source,records,0,bytes([21])*80,bytes([4])*80)
        self.assertEqual(records[1],unchanged)
    def test_variable_size_lz_round_trip(self):
        data=b"XYZ123"*183
        self.assertEqual(decode_stream(encode_stream(data,expected_bytes=len(data)),
                                       expected_bytes=len(data)),data)

if __name__=="__main__":
    unittest.main()
