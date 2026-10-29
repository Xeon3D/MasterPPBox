"""Minimal ELF32 i386 helper: symbols, vaddr->file offset, disasm.
  elfsym.py <elf> syms [regex]
  elfsym.py <elf> dis <symbol|0xaddr> [nbytes]
  elfsym.py <elf> dump <symbol|0xaddr> <nbytes>"""
import struct,sys,re
class ELF:
    def __init__(s,p):
        s.d=d=open(p,'rb').read(); assert d[:4]==b'\x7fELF'
        (s.type,s.mach,_,s.entry,phoff,shoff,_,_,phes,phn,shes,shn,shstr)=struct.unpack_from('<HHIIIIIHHHHHH',d,16)
        s.ph=[struct.unpack_from('<8I',d,phoff+i*phes) for i in range(phn)]
        s.sh=[struct.unpack_from('<10I',d,shoff+i*shes) for i in range(shn)] if shoff else []
        s.syms={}
        for sh in s.sh:
            if sh[1] in (2,11):
                strtab=s.sh[sh[6]]
                for o in range(sh[4],sh[4]+sh[5],16):
                    nm,val,sz,info,oth,shx=struct.unpack_from('<IIIBBH',d,o)
                    n=d[strtab[4]+nm:d.index(b'\0',strtab[4]+nm)].decode('latin1')
                    if n: s.syms[n]=(val,sz,info)
    def off(s,va):
        for p in s.ph:
            if p[0]==1 and p[2]<=va<p[2]+p[4]: return va-p[2]+p[1]
    def addr(s,x): return int(x,16) if x.startswith('0x') else s.syms[x][0]
    def name(s,va):
        best=None
        for n,(v,sz,i) in s.syms.items():
            if v<=va and (best is None or v>best[1]): best=(n,v)
        return '%s+0x%x'%(best[0],va-best[1]) if best else hex(va)
if __name__=='__main__':
    e=ELF(sys.argv[1]); cmd=sys.argv[2]
    if cmd=='syms':
        rx=re.compile(sys.argv[3] if len(sys.argv)>3 else '.')
        for n,(v,sz,i) in sorted(e.syms.items(),key=lambda x:x[1][0]):
            if rx.search(n): print('%08x %6d %02x %s'%(v,sz,i,n))
    elif cmd in('dis','dump'):
        va=e.addr(sys.argv[3]); n=int(sys.argv[4],0) if len(sys.argv)>4 else (e.syms.get(sys.argv[3],(0,0x100))[1] or 0x100)
        o=e.off(va); b=e.d[o:o+n]
        if cmd=='dump':
            for i in range(0,len(b),16): print('%08x '%(va+i)+b[i:i+16].hex(' '))
        else:
            import capstone
            md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
            rev={v[0]:k for k,v in e.syms.items() if v[0]}
            for ins in md.disasm(b,va):
                c=''
                for m in re.findall(r'0x[0-9a-f]+',ins.op_str):
                    if int(m,16) in rev: c+=' <%s>'%rev[int(m,16)]
                print('%08x  %-8s %s%s'%(ins.address,ins.mnemonic,ins.op_str,c))
