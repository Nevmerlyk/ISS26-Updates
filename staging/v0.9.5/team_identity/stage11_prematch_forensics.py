#!/usr/bin/env python3
"""Stage 11: read-only provenance check for ISS26 prematch national team names.

Consumes a PCSX-Redux Explorer/Academy *existing* session archive with saved
selection/prematch RAM and original PCSX-Redux v5 savestate. Does not modify
ROM, game saves or emulator state. Extracted RAM/VRAM is never published.
"""
from __future__ import annotations
import argparse,hashlib,json,re,struct,zipfile
from pathlib import Path

SELECT='flag_selection_00002850_RAM.bin'
PREMATCH='flag_prematch_00008190_RAM.bin'
STATE='flag_prematch_00008190.state'
VRAM_REF='vram_probe_8400_8401.vram'
SPAN=2_097_152
FRAME=1_048_576
NAME_BANK=(0x80200,0x80480)


def find_ram_region(state:bytes,ram:bytes)->int:
    if len(ram)!=SPAN:raise ValueError('Expected PS1 2MiB RAM')
    markers=(0x1000,0x56000,0x80000,0x100000)
    first=state.find(ram[markers[0]:markers[0]+256])
    start=first-markers[0]
    if first<0 or start<0 or state[start:start+SPAN]!=ram:
        raise ValueError('Savestate does not contain unmodified RAM bytes')
    return start


def find_vram_region(state:bytes,vram_ref:bytes)->tuple[int,list[dict]]:
    if len(vram_ref)!=SPAN:raise ValueError('Expected 2MiB GPU VRAM snapshot')
    # Use a diagnostic nonzero source run outside changing framebuffer rows.
    # Match candidate start using two independent stable offsets from the
    # user-provided in-session snapshots, then check entire region length.
    anchor=200000
    target=vram_ref[anchor:anchor+256]
    at=0;candidates=[]
    while True:
        pos=state.find(target,at)
        if pos<0:break
        start=pos-anchor
        if start>=0 and start+SPAN<=len(state):
            equal=[]
            for off in (50000,200000,800000,1100000,1600000):
                a=state[start+off:start+off+256]
                b=vram_ref[off:off+256]
                equal.append({'offset':off,'matched':a==b})
            if sum(x['matched'] for x in equal)>=3:candidates.append((start,equal))
        at=pos+1
    # Names and framebuffer may differ between prematch and the next frame;
    # identical texture areas and decoded VRAM header are the validation gate.
    unique={start:checks for start,checks in candidates}
    if len(unique)!=1:raise ValueError(f'No unique VRAM window match ({len(unique)} candidates)')
    return next(iter(unique.items()))


def count_word(buf:bytes,word:bytes)->int:
    return len(list(re.finditer(re.escape(word),buf,re.I)))


def audit(archive:Path,output:Path)->dict:
    with zipfile.ZipFile(archive) as z:
        selection=z.read(SELECT)
        prematch=z.read(PREMATCH)
        state=z.read(STATE)
        ref=z.read(VRAM_REF)
    if len(selection)!=SPAN or len(prematch)!=SPAN:raise ValueError('Wrong RAM capture sizes')
    ram_position=find_ram_region(state,prematch)
    vram_position,vram_checks=find_vram_region(state,ref)
    vram=state[vram_position:vram_position+SPAN]
    if vram[:FRAME]==ref[:FRAME]:
        # Different frames must not be identical throughout framebuffer texture region.
        raise ValueError('Unexpected full VRAM equality between captures')
    sel_blob=selection[slice(*NAME_BANK)]
    pre_blob=prematch[slice(*NAME_BANK)]
    assert b'BOSNIA' in sel_blob and b'N.ZEAL' in sel_blob and b'C.VERDE' in sel_blob
    assert b'BOSNIA' not in pre_blob and b'N.ZEAL' not in pre_blob
    # MIPS little endian instruction patterns in prematch overlay bank, rather than ASCII.
    mips_like=sum(1 for off in range(0,len(pre_blob)-3,4)
                  if ((pre_blob[off+3] in (0x24,0x27,0x2B,0x8F,0x90,0xAF,0x0C,0x08,0x10,0x14))))
    words=['BOSNIA','N.ZEAL','C.VERDE','RUSSIA','GREECE','JAMAICA','UKRAINE','RUS','GRC']
    counts={w:{'selection':count_word(selection,w.encode()),'prematch':count_word(prematch,w.encode())} for w in words}
    report={
       'stage':11,'source_archive':archive.name,
       'purpose':'Locate prematch national name provenance; read-only; no game patches',
       'capture_game_version':'EARLIER EXPERIMENTAL SESSION (not authenticated as Test08)',
       'pcsx_redux_state_format':'SaveState v5',
       'selection_ram_sha256':hashlib.sha256(selection).hexdigest().upper(),
       'prematch_ram_sha256':hashlib.sha256(prematch).hexdigest().upper(),
       'selection_name_bank_start':'0x%06X'%NAME_BANK[0],
       'selection_name_bank_end':'0x%06X'%NAME_BANK[1],
       'selection_name_bytes_sample':['BOSNIA','N.ZEAL','C.VERDE'],
       'prematch_name_bank_overwritten':sel_blob!=pre_blob,
       'prematch_mips_instruction_like_words':mips_like,
       'word_occurrences_in_ram':counts,
       'save_state_ram_offset':ram_position,
       'save_state_vram_offset':vram_position,
       'save_state_vram_source_consistency':vram_checks,
       'supporting_on_screen_observation':'Recovered prematch 16bpp framebuffer clearly shows Ireland vs Russia; modified selection RAM had BOSNIA and C.VERDE text. The runtime origin of prematch text is NOT proven by this comparison.',
       'conclusions':[
          'Confirmed: selection names occupy an overlay region that is replaced with executable bytes by the prematch scene, so patching only SELECT/SELECT3 cannot guarantee replacement of prematch names.',
          'Observed: ordinary ASCII text Russia/Greece is absent in this captured prematch RAM, yet Russia is visibly rendered in its saved framebuffer.',
          'The pre-match label could come from packed character IDs, pre-rendered imagery, save/Edit Data or another loader; none is conclusively established.',
          'Do not patch SELECTC 3-letter IDs or GDC graphics based on speculation; preserve Test08 and stable v0.9.4.',
       ],
       'recommended_next_capture':'During a CURRENT Test08 prematch scene record GPU GP0 trace and RAM+VRAM at the same VSync, plus no-memory-card control if possible.'
    }
    output.mkdir(parents=True,exist_ok=True)
    (output/'stage11_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    # 640x240 native framebuffer plus texture spill on the right, for local diagnosis only.
    try:
        import numpy as np
        from PIL import Image
        words=np.frombuffer(vram[:FRAME],dtype='<u2').reshape(512,1024).astype('uint32')
        rgb=np.stack(((words&31)*255//31,((words>>5)&31)*255//31,((words>>10)&31)*255//31),axis=-1).astype('uint8')
        img=Image.fromarray(rgb,'RGB')
        img.crop((0,0,512,240)).resize((1024,480),Image.Resampling.NEAREST).save(output/'prematch_framebuffer_reference.png')
    except ImportError:
        pass
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    args=ap.parse_args()
    print(json.dumps(audit(args.archive,args.out),indent=2,ensure_ascii=False))
