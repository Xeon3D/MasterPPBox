"""For each ELF32 exe/lib: resolve PLT stubs of time()/gettimeofday()/
localtime() via .rel.plt + .dynsym, find every call site, and print any
compare-with-immediate in the following N instructions (time-bomb audit).
  python scripts/p2-timeuse.py <elf> [<elf> ...]"""
import re, struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
from elfsym import ELF

FUNCS = ('time', 'gettimeofday', 'localtime', 'difftime', 'mktime')
N = 25

def plt_map(e):
    d = e.d
    secs = e.sh
    shstr = secs[struct.unpack_from('<H', d, 50)[0]]
    name = lambda sh: d[shstr[4] + sh[0]:d.index(b'\0', shstr[4] + sh[0])].decode()
    byname = {name(s): s for s in secs}
    dynsym, dynstr = byname.get('.dynsym'), byname.get('.dynstr')
    relplt, plt = byname.get('.rel.plt'), byname.get('.plt')
    if not (dynsym and relplt and plt): return {}
    got2name = {}
    for o in range(relplt[4], relplt[4] + relplt[5], 8):
        off, info = struct.unpack_from('<II', d, o)
        nm = struct.unpack_from('<I', d, dynsym[4] + (info >> 8) * 16)[0]
        got2name[off] = d[dynstr[4] + nm:d.index(b'\0', dynstr[4] + nm)].decode()
    out = {}
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for i in md.disasm(d[plt[4]:plt[4] + plt[5]], plt[3]):
        m = re.fullmatch(r'dword ptr \[(0x[0-9a-f]+)\]', i.op_str)
        if i.mnemonic == 'jmp' and m and int(m.group(1), 16) in got2name:
            out[i.address] = got2name[int(m.group(1), 16)]
        m = re.fullmatch(r'dword ptr \[ebx \+ (0x[0-9a-f]+)\]', i.op_str)   # PIC plt
        if i.mnemonic == 'jmp' and m:
            pass
    return out

for path in sys.argv[1:]:
    e = ELF(path)
    plt = {a: n for a, n in plt_map(e).items() if n in FUNCS}
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); md.skipdata = True
    sites = 0; flagged = []
    for ph in e.ph:
        if ph[0] != 1 or not ph[6] & 1: continue
        ins = list(md.disasm(e.d[ph[1]:ph[1] + ph[4]], ph[2]))
        for k, i in enumerate(ins):
            if i.mnemonic == 'call' and re.fullmatch(r'0x[0-9a-f]+', i.op_str) and int(i.op_str, 16) in plt:
                sites += 1
                for j in ins[k + 1:k + 1 + N]:
                    if j.mnemonic == 'call': break
                    m = re.search(r'cmp .*, (0x[0-9a-f]{5,})$', j.mnemonic + ' ' + j.op_str)
                    if m:
                        flagged.append('%08x %s -> %08x cmp %s' % (i.address, plt[int(i.op_str, 16)], j.address, j.op_str))
    print('%-45s time-call sites: %3d   immediate compares after them: %d' % (path, sites, len(flagged)))
    for f in flagged: print('    ' + f)
