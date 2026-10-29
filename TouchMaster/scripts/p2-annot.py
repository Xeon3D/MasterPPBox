"""Annotated disassembly of a vaddr range in an ELF32 exe: resolves immediate
operands that point at C strings, and call targets given as name=0xaddr.
  python scripts/p2-annot.py <exe> <start> <end> [name=0xaddr ...] [--brief]
--brief prints only calls, cmp/test, string refs and immediates > 0xff."""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
from elfsym import ELF

args = [a for a in sys.argv[1:] if a != '--brief']
brief = '--brief' in sys.argv
e = ELF(args[0]); s, t = int(args[1], 16), int(args[2], 16)
names = {int(v, 16): n for n, v in (a.split('=') for a in args[3:])}
for n, (v, sz, i) in e.syms.items():
    if v: names.setdefault(v, n)

def cstr(va):
    o = e.off(va)
    if o is None or o >= len(e.d): return None
    end = e.d.find(b'\0', o)
    b = e.d[o:end]
    if 3 <= len(b) <= 200 and all(32 <= c < 127 or c in (9, 10) for c in b): return b.decode()

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
o = e.off(s)
for ins in md.disasm(e.d[o:o + (t - s)], s):
    note = ''
    for m in re.findall(r'0x[0-9a-f]+', ins.op_str):
        v = int(m, 16)
        if v in names: note += ' <%s>' % names[v]
        else:
            c = cstr(v)
            if c: note += ' "%s"' % c.replace('\n', '\\n')[:90]
    if brief and not (note or ins.mnemonic in ('call', 'cmp', 'test') or re.search(r'0x[0-9a-f]{3,}', ins.op_str)):
        continue
    print('%08x  %-6s %-40s%s' % (ins.address, ins.mnemonic, ins.op_str, note))
