"""Make the 86Box working disk: copy the first <sectors> 512-byte sectors of an
original image (the BSD label's d-partition size; the rest is zero) to <out>.
Prints SHA256 of the copied input range and of the output (identical by
construction) and verifies the dropped tail really is zero.
  python -I scripts/p3-mkdisk.py <orig.img> <out.img> <sectors>
OEM: 16841664 sectors = 16708 cyl x 16 heads x 63 spt."""
import hashlib, os, sys

src, dst, nsec = sys.argv[1], sys.argv[2], int(sys.argv[3])
CH = 1 << 24
n = nsec * 512
h = hashlib.sha256()
with open(src, 'rb') as f, open(dst, 'xb') as g:     # 'x': never overwrite
    left = n
    while left:
        b = f.read(min(CH, left))
        if not b: sys.exit('source shorter than requested')
        h.update(b); g.write(b); left -= len(b)
    nz = 0; tail = 0
    while True:
        b = f.read(CH)
        if not b: break
        tail += len(b)
        if b.count(0) != len(b): nz += 1
print('input  %s bytes [0,%d) sha256 %s' % (src, n, h.hexdigest()))
print('tail   %d bytes, non-zero chunks: %d' % (tail, nz))
h2 = hashlib.sha256()
with open(dst, 'rb') as g:
    for b in iter(lambda: g.read(CH), b''): h2.update(b)
print('output %s sha256 %s %s' % (dst, h2.hexdigest(), 'MATCH' if h2.digest() == h.digest() else 'MISMATCH'))
