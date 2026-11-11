#!/usr/bin/env python3
"""Rebuild T_NAME_E/F/G graphical national-team name atlas for 17 ISS26 replacements.

Research-based: 26 WE-compressed indexed 4bpp tiles, 128x128px each, 4 names
per tile in 32-high rows. 54 national team names are stored in reverse slot
order (slot 53 -> sprite0,row0; slot0 -> sprite13,row1). Two bonus labels
follow. File footer contains pointer table of 26 GPU upload commands.

All non-target pixels in decoded atlas are preserved exactly. Stage15 is an
experiment: new text visually derived from the old raster font, with a 4bpp
PIL fallback glyph renderer. Fonts are not packaged in release artifacts.
"""
from __future__ import annotations
import hashlib,io,json,struct,sys,collections
from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter,ImageFont
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from team_identity_audit import PatchedDisc
from merge_verified import merge
from wecodec_stage5 import decode,encode,optimize_literal_packets

TRACK=Path('/mnt/data/ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin')
BASELINE=ROOT/'stage12_results'/'ISS26_0.9.5_Stage12_Test08_LargeGPU_AB_CANDIDATE.iss26p'
BASELINE_SHA='FA5E3DC3702808E8ABC197C9BB27B0707A4D44575D765918911AD846738D71B2'
BASELINE_IMAGE_SHA='6F81648EDCF02D5115FFD313DDE4DA3F5768EA4FBEAD4C1831D91EC813B70647'
NAMES={2:'Qatar',4:'Uzbekistan',10:'Panama',11:'Ecuador',14:'Canada',18:'Senegal',23:'Bosnia',26:'New Zealand',27:'Iraq',28:'Jordan',29:'Curacao',31:'Haiti',34:'DR Congo',36:'Ghana',50:'Ivory Coast',52:'Algeria',53:'Cabo Verde'}
LABELS=['T_NAME_E','T_NAME_F','T_NAME_G']
FILES={name:{'lba':8200+(i*30),'size':56256} for i,name in enumerate(LABELS)}
FONT='/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf'
BG=0; CORE=15; SHADOW=13; OUTLINE=14
OUTDIR=ROOT/'stage15_results';OUTDIR.mkdir(parents=True,exist_ok=True)


def unpack4(raw):
 p=np.frombuffer(raw,dtype=np.uint8)
 return np.stack((p&15,p>>4),axis=-1).reshape((128,128)).copy()
def pack4(raw):
 p=np.asarray(raw,dtype=np.uint8).ravel()
 assert np.max(p)<=15 and len(p)%2==0
 return bytes((p[::2]|(p[1::2]<<4)).tolist())


def get_original_tiles(data):
 table,=struct.unpack_from('<I',data,0);table-=0x800F0000
 assert table==0xDA10 and len(data)==56256
 chunks=[];meta=[]
 for i in range(26):
  cmd=struct.unpack_from('<6HI',data,table+i*16)
  op,x,y,w,h,flags,ptr=cmd
  assert(op,w,h,flags)==(10,32,128,0)
  at=ptr-0x800f0000
  raw,used=decode(data[at:table],8192)
  chunks.append(unpack4(raw))
  meta.append({'id':i,'x':x,'y':y,'before_at':at,'before_encoded_size':used})
 assert struct.unpack_from('<6HI',data,table+26*16)[0]==255
 return table,chunks,meta


def label_lines(text):
 f=ImageFont.truetype(FONT,18)
 if f.getlength(text)*1.4<=123 or ' ' not in text:
  return [text]
 words=text.split(' ')
 if len(words)>2:
  first=' '.join(words[:len(words)//2]);second=' '.join(words[len(words)//2:])
  return [first,second]
 return words


def draw_native_style_text(text:str)->np.ndarray:
 """Return native-size 128x32 indexed glyphs, black background (0), white core 15 and shadow 13/14."""
 arr=np.zeros((32,128),dtype=np.uint8)
 lines=label_lines(text)
 f=ImageFont.truetype(FONT,18)
 for li,line in enumerate(lines):
  # Original native source letters use ~1.40x horizontal scale of this italic font.
  # Render at 18px font with a constant vertical baseline across glyphs.
  src=Image.new('L',(256,35),0)
  draw=ImageDraw.Draw(src)
  draw.text((1,-2),line,font=f,fill=255)
  bb=src.getbbox()
  if not bb:continue
  # Avoid cropping descenders relative to other words: take full 19 source rows.
  w=int(round(f.getlength(line)*1.40))
  w=min(122,max(w,1))
  crop=src.crop((0,2, min(255,int(f.getlength(line))+5),21))
  glyph=crop.resize((w,13),Image.Resampling.LANCZOS)
  mask=np.asarray(glyph).astype('uint8')
  yy=2+li*14
  if yy+15>32:raise ValueError('Label overflow '+text)
  h,w=mask.shape
  # Pixel-art shadow below and right, not a solid bounding rectangle.
  shadow=(mask>96)
  for sy,sx,idx in [(2,2,SHADOW),(1,1,OUTLINE)]:
   for y in range(h):
    for x in range(w):
     if shadow[y,x] and yy+y+sy<32 and x+sx<128:
      arr[yy+y+sy,x+sx]=idx
  for y in range(h):
   for x in range(w):
    val=mask[y,x]
    if val>187:idx=CORE
    elif val>112:idx=8
    elif val>50:idx=3
    else:continue
    if yy+y<32:arr[yy+y,x]=idx
 return arr


def create_art(src):
 table,original,meta=get_original_tiles(src)
 updated=[a.copy() for a in original]
 pixel_report={}
 for slot,label in NAMES.items():
  rev=53-slot
  tile_idx,row=divmod(rev,4)
  tile=updated[tile_idx]
  pos=row*32
  before=tile[pos:pos+32,:].copy()
  after=draw_native_style_text(label)
  tile[pos:pos+32,:]=after
  pixel_report[str(slot)]={'team':label,'block':tile_idx,'row':row,'changed_pixels':int(np.count_nonzero(before!=after)),'drawn_pixels':int(np.count_nonzero(after)), 'lines':label_lines(label)}
  if not np.any(before!=after):raise ValueError('Target name did not change '+label)
 # Explicit preservation of 39 other national slots and both bonuses.
 for slot in range(54):
  if slot in NAMES:continue
  idx,row=divmod(53-slot,4)
  start=row*32
  if not np.array_equal(original[idx][start:start+32],updated[idx][start:start+32]):
   raise ValueError('Unmodified national name changed '+str(slot))
 for i in range(14,26):
  if not np.array_equal(original[i],updated[i]):raise ValueError('Club/stadium sprites changed '+str(i))
 for row in (2,3):
  if not np.array_equal(original[13][32*row:32*(row+1)],updated[13][32*row:32*(row+1)]):
   raise ValueError('All star sprite changed')
 return table,original,updated,meta,pixel_report


def rebuild_source(original_file:bytes,modified_tiles,meta,table:int):
 # Preserve pointer table and untouched compressed stream bytes when possible,
 # recalculate all GPU upload pointers for relocation in fixed original file size.
 blobs=[];size_report=[]
 for i,(tile,entry) in enumerate(zip(modified_tiles,meta)):
  old_raw,used=decode(original_file[entry['before_at']:],8192)
  after=pack4(tile)
  if after==old_raw:
   blob=original_file[entry['before_at']:entry['before_at']+used]
   algorithm='identical_original_compressed'
  else:
   basic=encode(after)
   choices=[basic,optimize_literal_packets(basic)]
   blob=min(choices,key=len)
   raw_check,used_check=decode(blob,len(after))
   assert raw_check==after and used_check==len(blob)
   algorithm='custom_WE_optimized'
  blobs.append(blob)
  size_report.append({'id':i,'before_bytes':used,'after_bytes':len(blob),'method':algorithm})
 # Repacks compressed chunks; keeps 0xDA10 command-table position unchanged.
 out=bytearray(original_file)
 at=4
 offsets=[]
 for blob in blobs:
  while at%4:
   at+=1
  offsets.append(at)
  out[at:at+len(blob)]=blob
  at+=len(blob)
 # before command table: alignment + buffer space required.
 used=at+(-at%4)
 if used>table:
  raise ValueError(f'T_NAME_E repack overflow: {used} > {table} ({used-table} extra bytes)')
 out[at:table]=bytes(table-at)
 for i,p in enumerate(offsets):
  struct.pack_into('<I',out,table+i*16+12,0x800f0000+p)
 assert len(out)==len(original_file)
 for i,p in enumerate(offsets):
  raw,consumed=decode(out[p:table],8192)
  if raw!=pack4(modified_tiles[i]):raise ValueError('Decoded stream different '+str(i))
  if consumed!=len(blobs[i]):raise ValueError('Decoded size mismatch '+str(i))
 return bytes(out),{'used_encoded_end':used,'table_offset':table,'slack_bytes':table-used,'chunks':size_report,'updated_command_ptrs':len(offsets)}


def visual_preview(before,after,report):
 color=np.array([[0,0,0],[245,246,248],[26,27,31],[179,188,204],[0,62,160],[0,135,65],[255,220,53],[200,170,80],[218,225,245],[150,152,166],[0,35,95],[228,229,233],[220,220,220],[75,75,80],[129,129,138],[255,255,255]],dtype=np.uint8)
 # Target slots only, two-column comparison per each 17 teams.
 im=Image.new('RGB',(1000, 17*78+70),(25,29,35));draw=ImageDraw.Draw(im)
 draw.text((28,14),'ISS26 Prematch Names - Original / Rebuilt 4bpp Atlas',fill='white')
 draw.text((180,42),'Before',fill='white');draw.text((615,42),'After',fill='white')
 for n,(slot,newname) in enumerate(sorted(NAMES.items())):
  tile,row=divmod(53-slot,4)
  left=before[tile][row*32:row*32+32,:]
  right=after[tile][row*32:row*32+32,:]
  y=65+n*77
  draw.text((12,y+22),f'{slot:02d} {newname[:13]}',fill='#d6dbe3')
  for x,z in ((180,left),(615,right)):
   small=Image.fromarray(color[z],mode='RGB')
   im.paste(small.resize((384,64),Image.Resampling.NEAREST),(x,y))
 im.save(OUTDIR/'national_names_17_before_after.png')


def main():
 if hashlib.sha256(BASELINE.read_bytes()).hexdigest().upper()!=BASELINE_SHA:
  raise ValueError('Wrong Test09 baseline patch')
 disc=PatchedDisc(TRACK,BASELINE,verify=True)
 try:
  sources={n:disc.logical(d['lba'],0,d['size'],True) for n,d in FILES.items()}
  for name in LABELS[1:]:
   if sources[name]!=sources[LABELS[0]]:
    raise ValueError('Localized T_NAME atlas differs unexpectedly; requires individual study')
  table,before,after,meta,targets=create_art(sources['T_NAME_E'])
  rebuilt,meta2=rebuild_source(sources['T_NAME_E'],after,meta,table)
  visual_preview(before,after,targets)
  edits=[]
  for name,info in FILES.items():
   original=sources[name]
   assert len(original)==len(rebuilt)
   # Segment edits to stay within mode2 2048-byte data region.
   for off in range(0,len(rebuilt),2048):
    old=original[off:off+2048];new=rebuilt[off:off+2048]
    if old==new:continue
    lba=info['lba']+off//2048
    assert lba in range(info['lba'],info['lba']+(len(original)+2047)//2048)
    edits.append({'raw_offset':lba*2352+24,
                  'expected_hex':old.hex(),'replacement_hex':new.hex(),
                  'purpose':'17 official renamed nations prematch bitmap atlas '+name})
  (OUTDIR/'stage15_name_edits.json').write_text(json.dumps(edits,indent=2,ensure_ascii=False)+'\n')
  out_patch=OUTDIR/'ISS26_0.9.5_Stage15_NationalPrematchNames_CANDIDATE.iss26p'
  result=merge(TRACK,BASELINE,OUTDIR/'stage15_name_edits.json',out_patch,BASELINE_IMAGE_SHA)
  # Verify exact expected graphics from patched disc; all other assets untouched.
  checked=PatchedDisc(TRACK,out_patch,verify=False)
  try:
   for name,d in FILES.items():
    buf=checked.logical(d['lba'],0,d['size'],True)
    if buf!=rebuilt:raise ValueError('patched source differs from expected '+name)
    _,blk,_=get_original_tiles(buf)
    for i in range(26):
     if not np.array_equal(blk[i],after[i]):raise ValueError('Patched stream content mismatch '+name+' block'+str(i))
   for x in (167,168,169,170,171,172,5328,5329,6082,6083,6084,6085,6086,6087,6088,6089,6090,6250,6251,6252,6253,6254,6255,6256,6257,6277,6279):
    if checked.sector(x,True)!=disc.sector(x,True):raise ValueError('Small flags or rosters changed')
   for x in (12560,12561,12562,12563,12730,12731,16300):
    if checked.sector(x,True)!=disc.sector(x,True):raise ValueError('Stadium graphics changed')
  finally:checked.close()
  report={'stage':15,'status':'STATIC-VALIDATED; EMULATOR PREMATCH VISUAL CONFIRMATION REQUIRED',
          'source':'T_NAME_E/F/G.BIN 26 GPU-4bpp national/club/stadium name textures, confirmed rasterized Russia/Greece/Jamaica',
          'supported_54_national_slots':True,'replaced_labels':targets,'replacement_count':len(targets),
          'rendering_style':'custom pixel-font approximation based on original 4bpp palette, not a bit-exact reconstruction of Konami glyphs',
          'localized_atlases_identical_originally':True,'repack_meta':meta2,
          'new_patch_sha256':result['patch_sha256'],'result_disc_sha256':result['result_sha256'],
          'patch_size':out_patch.stat().st_size,'edited_sectors':result['edited_sectors'],
          'changed_national_name_cells':17,'unchanged_national_name_cells':37,
          'other_labels_preserved':'2 bonus labels, clubs and all stadium names',
          'large_flag_texture_modified':False,'stadium_gdc_modified':False,
          'notes':['UI labels are a GPU texture: language files all identical in this EU disc.',
          'This test only updates prematch names; large flags are a distinct unresolved GPU/CLUT mapping.',
          'Need verify Test09 or later in PCSX-Redux before publishing into Test Game.']}
  (OUTDIR/'stage15_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
  print(json.dumps({k:v for k,v in report.items() if k not in ('replaced_labels','repack_meta')},indent=2,ensure_ascii=False))
  return report
 finally:disc.close()

if __name__=='__main__':main()
