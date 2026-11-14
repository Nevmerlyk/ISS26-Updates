#!/usr/bin/env python3
"""Read-only instruction-window audit of the actual clean and patched SELECT.
Static disassembly is not runtime tracing or proof of the last writer.
"""
from __future__ import annotations
import struct
from test27_stage_writer_guard import SELECT_RAM, STAGE_CALLS, verify_select_calls
from v095_static_prematch_ram_trace import SELECT_BYTES, SELECT_SHA, sha

REGS=("zero","at","v0","v1","a0","a1","a2","a3","t0","t1","t2","t3","t4","t5","t6","t7",
      "s0","s1","s2","s3","s4","s5","s6","s7","t8","t9","k0","k1","gp","sp","fp","ra")
def signed16(n):
    return n-65536 if n&0x8000 else n

def decode(pc,w):
    op=w>>26; rs=(w>>21)&31; rt=(w>>16)&31; rd=(w>>11)&31
    sh=(w>>6)&31; fn=w&63; imm=w&65535
    a,b,c=REGS[rs],REGS[rt],REGS[rd]
    row={"pc":f"{pc:08X}","opcode":f"{w:08X}",
         "instruction":f".word 0x{w:08X}","control_transfer":False}
    if w==0:
        row["instruction"]="nop"
    elif op in (2,3):
        target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
        row.update(instruction=f"{'jal' if op==3 else 'j'} 0x{target:08X}",
                   target=f"{target:08X}",control_transfer=True)
    elif op in (4,5,6,7,1):
        target=(pc+4+4*signed16(imm))&0xffffffff
        if op==1:
            name={0:"bltz",1:"bgez",16:"bltzal",17:"bgezal"}.get(rt,"regimm")
        else:
            name={4:"beq",5:"bne",6:"blez",7:"bgtz"}[op]
        args=f"{a}, {b}" if op in (4,5) else a
        row.update(instruction=f"{name} {args}, 0x{target:08X}",
                   target=f"{target:08X}",control_transfer=True)
    elif op==0:
        if fn in (8,9):
            row.update(instruction=f"{'jr' if fn==8 else 'jalr'} {a}",control_transfer=True)
        elif fn in (0,2,3):
            row["instruction"]=f"{ {0:'sll',2:'srl',3:'sra'}[fn]} {c}, {b}, {sh}"
        elif fn in (0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x2a,0x2b):
            name={32:"add",33:"addu",34:"sub",35:"subu",36:"and",37:"or",38:"xor",39:"nor",42:"slt",43:"sltu"}[fn]
            row["instruction"]=f"{name} {c}, {a}, {b}"
    elif op==15:
        row["instruction"]=f"lui {b}, 0x{imm:04X}"
    elif op in (8,9,10,11,12,13,14):
        name={8:"addi",9:"addiu",10:"slti",11:"sltiu",12:"andi",13:"ori",14:"xori"}[op]
        row["instruction"]=f"{name} {b}, {a}, {signed16(imm) if op<12 else hex(imm)}"
        if rs==0 and op in (8,9,13):
            value=signed16(imm) if op<12 else imm
            if value in (16,28,56,560,384,896,1792):
                row["rectangle_or_buffer_constant"]=value
    elif op in (32,33,35,36,37,40,41,43):
        name={32:"lb",33:"lh",35:"lw",36:"lbu",37:"lhu",40:"sb",41:"sh",43:"sw"}[op]
        row["instruction"]=f"{name} {b}, {signed16(imm)}({a})"
        if op in (40,41,43):
            row["store"]={"source_register":b,"base_register":a,"offset":signed16(imm),
                          "size_bytes":{40:1,41:2,43:4}[op],"explicit_zero":rt==0}
    return row

def window(buf,start,stop):
    if start%4 or stop%4 or not SELECT_RAM<=start<=stop<=SELECT_RAM+len(buf):
        raise ValueError("Invalid SELECT instruction window")
    rows=[]
    delay=False
    for pc in range(start,stop,4):
        r=decode(pc,struct.unpack_from("<I",buf,pc-SELECT_RAM)[0])
        r["lexically_after_control_transfer"]=delay
        rows.append(r)
        delay=r["control_transfer"]
    return rows

def audit(clean,patched):
    if len(clean)!=SELECT_BYTES or len(patched)!=SELECT_BYTES or sha(clean)!=SELECT_SHA:
        raise ValueError("Actual clean SELECT overlay hash/size mismatch")
    verify_select_calls(clean)
    verify_select_calls(patched)
    start=0x80092F18
    stop=0x800933E0
    rows=window(patched,start,stop)
    old=window(clean,start,stop)
    changes=[{"pc":b["pc"],"clean":a["opcode"],"patched":b["opcode"]}
             for a,b in zip(old,rows) if a["opcode"]!=b["opcode"]]
    calls=[]
    for name,pc,target in STAGE_CALLS:
        calls.append({"name":name,"callsite":f"{pc:08X}",
                      "known_wrapper":f"{target:08X}",
                      "context":window(patched,pc-48,pc+12)})
    return {"schemaVersion":1,"kind":"Static SELECT stage code; no emulated execution",
            "clean_select_sha256":sha(clean),"patched_select_sha256":sha(patched),
            "window":[f"{start:08X}",f"{stop:08X}"],
            "changed_instructions_in_window":changes,"call_contexts":calls,
            "candidate_explicit_zero_stores":[r for r in rows if r.get("store",{}).get("explicit_zero")],
            "candidate_rectangle_constants":[r for r in rows if "rectangle_or_buffer_constant" in r],
            "all_instructions":rows,
            "runtime_argument_values_proven":False,"final_stage_writer_proven":False,
            "game_code_modified":False,
            "warning":"Lexical instruction order is not an executed path. A zero store might target stack or unrelated data. No correction inferred."}
