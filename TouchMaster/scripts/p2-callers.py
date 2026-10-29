"""List call sites (call rel32) to given virtual addresses in an ELF32 exe.
  python scripts/p2-callers.py <exe> name=0xaddr [name=0xaddr ...]
For each site prints the enclosing-function guess (nearest preceding
'push ebp; mov ebp,esp') and the site vaddr."""
import struct, sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from elfsym import ELF

e = ELF(sys.argv[1])
targets = {int(v, 16): n for n, v in (a.split('=') for a in sys.argv[2:])}
text = [p for p in e.ph if p[0] == 1 and p[7] & 1 == 0 or p[0] == 1][0]
d = e.d
for p in e.ph:
    if p[0] != 1: continue
    off, va, sz = p[1], p[2], p[4]
    for i in range(off, off + sz - 5):
        if d[i] != 0xE8: continue
        rel, = struct.unpack_from('<i', d, i + 1)
        tgt = va + (i - off) + 5 + rel
        if tgt in targets:
            j = i
            while j > off and d[j:j + 3] != b'\x55\x89\xe5': j -= 1
            print('%-8s called from %08x  (func ~%08x)' % (targets[tgt], va + i - off, va + j - off))
