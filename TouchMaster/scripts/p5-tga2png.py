"""Convert dl's 640x480 16-bit (1555) uncompressed TGA screen dumps to PNG
(stdlib only: zlib + struct).
  python -I scripts/p5-tga2png.py <in.tga> <out.png>"""
import struct, sys, zlib

d = open(sys.argv[1], 'rb').read()
idlen, cmtype, itype, cmfirst, cmlen, cmbits, xo, yo, w, h, bpp, desc = struct.unpack_from('<BBBHHBHHHHBB', d)
assert itype == 2 and bpp == 16, (itype, bpp)
px = d[18 + idlen:]
rows = []
for y in range(h):
    sy = y                                         # dl writes rows top first, without the TGA origin bit
    row = bytearray(b'\0')
    for x in range(w):
        v = struct.unpack_from('<H', px, (sy * w + x) * 2)[0]
        r, g, b = (v >> 10) & 31, (v >> 5) & 31, v & 31
        row += bytes(((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2)))
    rows.append(bytes(row))
def chunk(t, b): return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b))
png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + \
      chunk(b'IDAT', zlib.compress(b''.join(rows), 9)) + chunk(b'IEND', b'')
open(sys.argv[2], 'wb').write(png)
