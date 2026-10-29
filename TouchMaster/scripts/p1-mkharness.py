"""Derive the host-compilable copy of the ORIGINAL t/coinmgr/dolphin.c.
Four edits: the include, the two mmap pointer declarations, and dChris()'s
missing return. dChris falls off its end; the 2.03 menu binary (0x1e667)
shows gcc 2.7 leaves usleep()'s result in eax, so 'return usleep(100000);'
is the faithful model (modern g++ would otherwise emit ud2 there).
The protection logic itself is untouched. Prints input/output SHA256.
  python -I scripts/p1-mkharness.py <dolphin.c> <out.cc>"""
import hashlib, re, sys

src, dst = sys.argv[1], sys.argv[2]
data = open(src, 'rb').read()
repl = [
    (b'#include "/t/video/dlflags.h"', b'#include "harness_shim.h"'),
    (b'extern volatile unsigned char *dolphin;', b'extern DolPtr8 dolphin;'),
    (b'extern volatile unsigned short *dolphinw;', b'extern DolPtr16 dolphinw;'),
]
out = data
for a, b in repl:
    assert out.count(a) == 1, a
    out = out.replace(a, b)
out, n = re.subn(rb'(\tWriteFuses\(0x04\);[^\n]*\n\tusleep\(100000\);)(\s*\n\}\s*\n+// Get Dolphin Info)',
                 rb'\tWriteFuses(0x04);   // Blow PER\n\treturn usleep(100000); /* harness: gcc-2.7 eax fall-through */\2',
                 out)
assert n == 1, 'dChris tail not found'
open(dst, 'wb').write(out)
print('in ', hashlib.sha256(data).hexdigest(), src)
print('out', hashlib.sha256(out).hexdigest(), dst)
