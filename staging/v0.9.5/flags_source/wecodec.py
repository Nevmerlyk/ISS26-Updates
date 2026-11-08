"""Winning Eleven / ISS Pro 2 stream codec, based on public WECompressor source.

Reference: maxiducoli/WECompressor WECompress.cpp (read-only implementation).
Only decode and exact-match round-trip checks here; no unverified resource writes.
"""
class DecodeError(ValueError):
    pass

def decode(data: bytes, expected_size: int, *, allow_padding=True):
    if not 0 <= expected_size <= 4_000_000: raise DecodeError("invalid expected length")
    out=bytearray()
    i=0
    bits=0
    flags=0
    commands=0
    while True:
        if bits==0:
            if i>=len(data): raise DecodeError("missing flag byte")
            flags=data[i]; i+=1; bits=8
        if i>=len(data): raise DecodeError("missing token")
        token=data[i]; i+=1
        if not (flags & 1):
            if len(out)>=expected_size: raise DecodeError("literal exceeds output")
            out.append(token)
        elif token>=0xC0:
            if token==0xFF:
                if len(out)!=expected_size: raise DecodeError(f"unexpected output size {len(out)} / {expected_size}")
                if not allow_padding and any(data[i:]): raise DecodeError("nonzero trailing bytes")
                return bytes(out),i,commands
            length=token-0xB9+1
            if i+length>len(data):raise DecodeError("truncated raw packet")
            if len(out)+length>expected_size:raise DecodeError("packet exceeds output")
            out.extend(data[i:i+length]); i+=length
            commands+=1
        else:
            if token>=0x80:
                offset=(token&15)+1
                length=(token>>4)-6
            else:
                if i>=len(data):raise DecodeError("truncated backreference")
                offset=data[i]|((token&3)<<8); i+=1
                length=(token>>2)+3
            if offset==0 or offset>len(out):raise DecodeError("invalid backreference distance")
            if len(out)+length>expected_size: raise DecodeError("backref exceeds output")
            for _ in range(length):out.append(out[-offset])
            commands+=1
        flags >>=1
        bits-=1
        if i>len(data):raise DecodeError("source overflow")

def encode(data:bytes)->bytes:
    """Encode a valid WE stream (round-trips with decode).

    Not byte-identical to the historical encoder. Never overwrite a source
    resource unless the result fits its allocated blob and all pointers are audited.
    """
    from collections import defaultdict,deque
    n=len(data);pos=0
    hits=defaultdict(deque)
    chunks=[];packet=[];bits=0;mask=1
    def flush():
        nonlocal packet,bits,mask
        if packet:
            chunks.append(bytes([bits])+b''.join(packet))
            packet=[];bits=0;mask=1
    def add(seq,is_ref):
        nonlocal mask,bits
        if is_ref:bits|=mask
        packet.append(seq)
        mask<<=1
        if mask==256:flush()
    while pos<n:
        length=0;dist=0
        if pos+2<n:
            key=data[pos:pos+3];bucket=hits.get(key,())
            for start in reversed(bucket):
                d=pos-start
                if d>1023:break
                cap=min(34,n-pos)
                count=3
                while count<cap and data[pos+count]==data[pos+count-d]:count+=1
                if count>length:length=count;dist=d
                if count==34:break
        if length<3 and pos+1<n:
            for d in range(1,min(16,pos)+1):
                if data[pos:pos+2]==data[pos-d:pos-d+2]:
                    length=2;dist=d;break
        if length>=2 and ((length<=5 and dist<=16) or length>=3):
            if length<=5 and dist<=16:
                token=bytes([((length+6)<<4)|(dist-1)])
            else:
                if length==2: raise AssertionError('invalid long match')
                token=bytes([((length-3)<<2)|((dist>>8)&3),dist&255])
            add(token,True);jump=length
        else:
            add(data[pos:pos+1],False);jump=1
        for i in range(pos,pos+jump):
            if i+2>=n:continue
            key=data[i:i+3];dq=hits[key];dq.append(i)
            while dq and i-dq[0]>1024:dq.popleft()
        pos+=jump
    add(b'\xFF',True)
    flush()
    return b''.join(chunks)