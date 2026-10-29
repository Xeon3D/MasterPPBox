import sys,struct; sys.path.insert(0,'scripts'); from elfsym import ELF
e=ELF(sys.argv[1])
def rd(va,n): o=e.off(va); return e.d[o:o+n]
def cstr(va):
    o=e.off(va); return e.d[o:e.d.index(b'\0',o)].decode() if o else '?'
print("== ISA devtab")
for t in ['isa_devtab_bio','isa_devtab_tty','isa_devtab_net','isa_devtab_cam','isa_devtab_ha','isa_devtab_null']:
    va,sz,_=e.syms[t]
    for i in range(sz//68):
        f=struct.unpack('<17i',rd(va+i*68,68))
        if f[1]==0: continue
        drv=struct.unpack('<4I',rd(f[1]&0xffffffff,16)); name=cstr(drv[2])
        irq=f[3]; irqn=[b for b in range(16) if irq & (1<<b)]
        print("%-5s %s%d port=%s irq=%s drq=%d maddr=%s msize=%d flags=0x%x"%(t[11:],name,f[8],hex(f[2]) if f[2]!=-1 else '?',irqn or '?',f[4],hex(f[5]&0xffffffff) if f[5] else '-',f[6],f[9]))
print("== PCI drivers")
s,_,_=e.syms['pcidevice_set']
n=struct.unpack('<I',rd(s,4))[0]
for i in range(n):
    p=struct.unpack('<I',rd(s+4+4*i,4))[0]
    name,probe,attach,cnt,sd=struct.unpack('<5I',rd(p,20))
    print(" %-10s probe=%s"%(cstr(name),e.name(probe)))
