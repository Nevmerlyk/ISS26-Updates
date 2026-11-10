class DecodeError(ValueError):pass
def decode(data, expected_size):
    if not 0<=expected_size<=4_000_000:raise DecodeError('size')
    out=bytearray();i=0;bits=0;flags=0
    while True:
        if bits==0:
            if i>=len(data):raise DecodeError('flags eof')
            flags=data[i];i+=1;bits=8
        if i>=len(data):raise DecodeError('token eof')
        token=data[i];i+=1
        if not(flags&1):
            if len(out)>=expected_size:raise DecodeError('literal over')
            out.append(token)
        elif token>=0xc0:
            if token==0xff:
                if len(out)!=expected_size:raise DecodeError(f'size {len(out)} expected {expected_size}')
                return bytes(out),i
            length=token-0xB9+1
            if i+length>len(data) or len(out)+length>expected_size:raise DecodeError('packet overflow')
            out.extend(data[i:i+length]);i+=length
        else:
            if token>=0x80:offset=(token&15)+1;length=(token>>4)-6
            else:
                if i>=len(data):raise DecodeError('backref eof')
                offset=data[i]|((token&3)<<8);i+=1
                length=(token>>2)+3
            if not offset or offset>len(out) or len(out)+length>expected_size:raise DecodeError('backref range')
            for j in range(length):out.append(out[-offset])
        flags >>=1;bits-=1
def encode(data:bytes)->bytes:
    from collections import defaultdict,deque
    n=len(data);pos=0;hits=defaultdict(deque);chunks=[];packet=[];bits=0;mask=1
    def flush():
        nonlocal packet,bits,mask
        if packet:
            chunks.append(bytes([bits])+b''.join(packet));packet=[];bits=0;mask=1
    def add(seq,is_ref):
        nonlocal bits,mask
        if is_ref:bits|=mask
        packet.append(seq);mask<<=1
        if mask==256:flush()
    while pos<n:
        length=0;dist=0
        if pos+2<n:
            key=data[pos:pos+3]
            for start in reversed(hits.get(key,())):
                d=pos-start
                if d>1023:break
                cap=min(34,n-pos);count=3
                while count<cap and data[pos+count]==data[pos+count-d]:count+=1
                if count>length:length=count;dist=d
                if count==34:break
        if length<3 and pos+1<n:
            for d in range(1,min(16,pos)+1):
                if data[pos:pos+2]==data[pos-d:pos-d+2]:length=2;dist=d;break
        if length>=2 and ((length<=5 and dist<=16) or length>=3):
            if length<=5 and dist<=16:token=bytes([((length+6)<<4)|(dist-1)])
            else:
                if length==2:raise AssertionError('invalid long match')
                token=bytes([((length-3)<<2)|((dist>>8)&3),dist&255])
            add(token,True);jump=length
        else:add(data[pos:pos+1],False);jump=1
        for i in range(pos,pos+jump):
            if i+2>=n:continue
            key=data[i:i+3];dq=hits[key];dq.append(i)
            while dq and i-dq[0]>1024:dq.popleft()
        pos+=jump
    add(b'\xFF',True);flush()
    return b''.join(chunks)
def optimize_literal_packets(data: bytes) -> bytes:
    """Losslessly replace runs of literal commands with WE raw packets (8..70 bytes)."""
    tokens=[];i=0;bits=0;flags=0
    while True:
        if bits==0:flags=data[i];i+=1;bits=8
        bit=bool(flags&1);token=data[i];i+=1;payload=bytes([token])
        if bit and token>=0xC0 and token!=0xFF:
            length=token-0xB9+1;payload+=data[i:i+length];i+=length
        elif bit and token<0x80:
            payload+=data[i:i+1];i+=1
        tokens.append((bit,payload));flags>>=1;bits-=1
        if bit and token==0xFF:break
    assert i==len(data),('bad trailer',i,len(data))
    optimized=[];i=0
    while i<len(tokens):
        if tokens[i][0]:optimized.append(tokens[i]);i+=1;continue
        j=i
        while j<len(tokens) and not tokens[j][0]:j+=1
        literals=b''.join(tokens[k][1] for k in range(i,j))
        while len(literals)>=8:
            if len(literals)>70:take=70
            else:take=len(literals)
            # Need >=8; avoid tiny leftover if possible by reducing current packet
            if 0<len(literals)-take<8:take-=8-(len(literals)-take)
            if take<8:break
            optimized.append((True,bytes([take+0xB8])+literals[:take]));literals=literals[take:]
        optimized.extend((False,bytes([v])) for v in literals)
        i=j
    chunks=[]
    for k in range(0,len(optimized),8):
        piece=optimized[k:k+8];flag=sum((1<<idx) for idx,(isref,_) in enumerate(piece) if isref)
        chunks.append(bytes([flag])+b''.join(s for _,s in piece))
    return b''.join(chunks)
