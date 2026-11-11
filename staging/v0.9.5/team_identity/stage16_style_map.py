from pathlib import Path
import csv
from PIL import Image,ImageDraw
from collections import defaultdict
ROOT=Path(__file__).parent
src=Image.open(ROOT/'GDC_AD_full_vram_flags_4bpp.png').convert('RGB')
owners=defaultdict(list)
with open(ROOT/'stage4_results/national_style_ownership_54.csv',newline='') as f:
 for a in csv.DictReader(f):
  owners[int(a['was_style'])].append(a['team'])
fig=Image.new('RGB',(4*300,7*200),(21,25,32))
d=ImageDraw.Draw(fig)
for style in range(28):
 col,row=divmod(style,4)
 # style enumerates four per row
 yy=256+(style//4)*32;xx=(832+16*(style%4)-672)*4
 px=src.crop((xx,yy,xx+64,yy+28)).resize((256,112),Image.Resampling.NEAREST)
 X=(style%4)*300+20;Y=(style//4)*200+20
 fig.paste(px,(X,Y+25))
 d.text((X,Y),f'Style {style:02d} - UV ({832+16*(style%4)},{yy})',fill='white')
 text=', '.join(owners.get(style,[]))
 while text:
  d.text((X,Y+145),text[:35],fill='#dce1eb')
  if len(text)<=35:break
  text=text[35:];Y+=17
fig.save(ROOT/'stage16_original_style_28_contact.png')
print('wrote preview',ROOT/'stage16_original_style_28_contact.png')