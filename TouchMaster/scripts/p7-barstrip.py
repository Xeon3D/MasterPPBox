"""Stack a crop (the menu's message bar, by default) of each PNG frame into
one tall strip, top to bottom in argv order (stdlib only; reuses
p5-contact's PNG reader).
  python -I scripts/p7-barstrip.py <out.png> <x0> <y0> <x1> <y1> <in.png> ..."""
import os, struct, sys, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import util
spec = util.spec_from_file_location('contact', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'p5-contact.py'))
src = open(spec.origin).read().split("out, cols, k = sys.argv[1]")[0]   # just the reader
ns = {}
exec(compile(src, spec.origin, 'exec'), ns)
read_png = ns['read_png']

out = sys.argv[1]
x0, y0, x1, y1 = (int(v) for v in sys.argv[2:6])
W, h1 = x1 - x0, y1 - y0
rows = []
for f in sys.argv[6:]:
    w, h, rgb = read_png(f)
    for y in range(y0, y1):
        rows.append(bytes(rgb[(y * w + x0) * 3:(y * w + x1) * 3]))
    rows.append(b'\x80' * (W * 3))                       # separator line
def chunk(t, b): return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b))
raw = b''.join(b'\0' + r for r in rows)
open(out, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', W, len(rows), 8, 2, 0, 0, 0)) +
                      chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))
