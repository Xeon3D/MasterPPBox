"""Re-point the PCI I/O bases that the OEM 2.03 software hard-codes, inside a
working disk image (never an original):
  /kernel        rag_intr/rag_read  mov edx,0xD818      (Rage CRTC_INT_CNTL)
                 est_intr/est_open  mov edx,0xEFxx      (ES1371 regs)
  /t/sound/sound push 0xEFxx (77 sites: args to its inb/outb wrappers)
Sites are found by disassembly (as scripts/p3-ioimm.py), checked against the
expected counts, and each 32-bit immediate is rewritten in place inside the
UFS1 file blocks (same size; nothing else in the image changes).
  python scripts/p3-patchio.py <image> --rage 0xE400 --es 0xE800 [--write]
Without --write it only reports. Prints SHA256 of each file before/after."""
import argparse, hashlib, os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
from ufs1 import UFS
from elfsym import ELF

ap = argparse.ArgumentParser()
ap.add_argument('image'); ap.add_argument('--rage', type=lambda x: int(x, 0), default=0xD800)
ap.add_argument('--es', type=lambda x: int(x, 0), default=0xEF00)
ap.add_argument('--write', action='store_true')
a = ap.parse_args()
assert a.rage % 0x100 == 0 and a.es % 0x40 == 0 and a.rage < 0x10000 and a.es < 0x10000
assert 'HDD Images' not in os.path.abspath(a.image), 'refusing to touch an original'

def sites(data, rngs, fn_ok):
    import tempfile
    t = tempfile.NamedTemporaryFile(delete=False); t.write(data); t.close()
    e = ELF(t.name); os.unlink(t.name)
    import bisect
    funcs = sorted((v, n) for n, (v, sz, i) in e.syms.items() if v); fv = [v for v, n in funcs]
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); md.skipdata = True; md.detail = True
    out = []
    for ph in e.ph:
        if ph[0] != 1 or not ph[6] & 1: continue
        for i in md.disasm(data[ph[1]:ph[1] + ph[4]], ph[2]):
            if i.mnemonic not in ('mov', 'push') or i.imm_size != 4: continue
            imm = struct.unpack_from('<I', i.bytes, i.imm_offset)[0]
            k = bisect.bisect_right(fv, i.address) - 1
            fn = funcs[k][1] if k >= 0 else '?'
            for lo, hi, newbase in rngs:
                if lo <= imm <= hi and fn_ok(fn, i):
                    out.append((ph[1] + i.address - ph[2] + i.imm_offset, imm, imm - lo + newbase, fn, i.mnemonic))
    return out

u = UFS(a.image, 0)                        # wd0a at sector 0 (dangerously dedicated)
byname = {p: n for p, n in u.walk() if p in ('/kernel', '/t/sound/sound')}
jobs = {
    '/kernel': ([(0xD800, 0xD8FF, a.rage), (0xEF00, 0xEF3F, a.es)],
                lambda fn, i: i.mnemonic == 'mov' and i.op_str.startswith('edx') and fn.startswith(('rag_', 'est_')), 10),
    '/t/sound/sound': ([(0xEF00, 0xEF3F, a.es)], lambda fn, i: i.mnemonic == 'push', 77),
}
f = open(a.image, 'r+b' if a.write else 'rb')
for path, (rngs, ok, want) in jobs.items():
    ino = byname[path]; data = u.read(ino); blocks = u.blocks(ino)
    s = sites(data, rngs, ok)
    print('%s: %d sites (expected %d)  sha256 before %s' % (path, len(s), want, hashlib.sha256(data).hexdigest()))
    if len(s) != want: sys.exit('site count mismatch, not patching')
    new = bytearray(data)
    for off, old, nw, fn, mn in s:
        assert struct.unpack_from('<I', data, off)[0] == old
        struct.pack_into('<I', new, off, nw)
    for off, old, nw, fn, mn in s[:3] + s[-1:]:
        print('    %-12s %s %#06x -> %#06x @file+%#x' % (fn, mn, old, nw, off))
    print('    sha256 after  %s' % hashlib.sha256(new).hexdigest())
    if a.write:
        for off, old, nw, fn, mn in s:
            for j in range(4):
                o = off + j; b = blocks[o // u.bsize]
                f.seek(u.base + b * u.fsize + o % u.bsize); f.write(bytes([new[o]]))
        f.flush()
        chk = UFS(a.image, 0).read(ino)
        print('    written; re-read sha256 %s %s' % (hashlib.sha256(chk).hexdigest(), 'OK' if chk == bytes(new) else 'MISMATCH'))
