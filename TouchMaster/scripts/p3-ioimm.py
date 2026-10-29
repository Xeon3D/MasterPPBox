"""List every x86 instruction in an ELF32's executable segments whose immediate
or displacement falls in [lo,hi] (default: Rage I/O 0xD800-0xD8FF and ES1371
I/O 0xEF00-0xEF3F), with the enclosing symbol. Used to size the 'patch the
hard-coded PCI I/O bases' option.
  python scripts/p3-ioimm.py <elf> [lo hi ...]"""
import bisect, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
from elfsym import ELF

e = ELF(sys.argv[1])
rng = [(int(a, 16), int(b, 16)) for a, b in zip(sys.argv[2::2], sys.argv[3::2])] or \
      [(0xD800, 0xD8FF), (0xEF00, 0xEF3F)]
funcs = sorted((v, n) for n, (v, sz, i) in e.syms.items() if v)
fv = [v for v, n in funcs]
def sym(a):
    k = bisect.bisect_right(fv, a) - 1
    return '%s+%#x' % (funcs[k][1], a - funcs[k][0]) if k >= 0 else '?'
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); md.skipdata = True
hits = 0
for ph in e.ph:
    if ph[0] != 1 or not ph[6] & 1: continue
    for i in md.disasm(e.d[ph[1]:ph[1] + ph[4]], ph[2]):
        for m in re.findall(r'0x[0-9a-f]+', i.op_str):
            v = int(m, 16)
            if any(lo <= v <= hi for lo, hi in rng):
                hits += 1
                print('%08x %-28s %s %s' % (i.address, sym(i.address), i.mnemonic, i.op_str))
                break
print('hits:', hits)
