"""Contact sheet of PNG frames (stdlib only): each frame scaled down by an
integer factor, laid out in a grid, labelled by nothing (order = argv order).
  python -I scripts/p5-contact.py <out.png> <cols> <shrink> <in.png> ..."""
import struct, sys, zlib

def read_png(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n'
    o = 8; idat = b''
    while o < len(d):
        n, t = struct.unpack_from('>I4s', d, o)
        body = d[o + 8:o + 8 + n]
        if t == b'IHDR':
            w, h, bd, ct = struct.unpack_from('>IIBB', body)
        elif t == b'IDAT':
            idat += body
        o += 12 + n
    assert bd == 8 and ct in (2, 6), (bd, ct)
    bpp = 3 if ct == 2 else 4
    raw = zlib.decompress(idat); stride = w * bpp
    out = bytearray(); prev = bytearray(stride); p = 0
    for y in range(h):
        f = raw[p]; line = bytearray(raw[p + 1:p + 1 + stride]); p += 1 + stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0; b = prev[i]; c = prev[i - bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += line; prev = line
    rgb = bytearray()
    for i in range(0, len(out), bpp): rgb += out[i:i + 3]
    return w, h, rgb

out, cols, k = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
frames = [read_png(f) for f in sys.argv[4:]]
fw, fh = frames[0][0] // k, frames[0][1] // k
rows = (len(frames) + cols - 1) // cols
W, H = cols * (fw + 2), rows * (fh + 2)
img = bytearray(b'\x40' * (W * H * 3))
for n, (w, h, rgb) in enumerate(frames):
    ox, oy = (n % cols) * (fw + 2), (n // cols) * (fh + 2)
    for y in range(min(fh, h // k)):
        for x in range(min(fw, w // k)):
            s = ((y * k) * w + x * k) * 3; t = ((oy + y) * W + ox + x) * 3
            img[t:t + 3] = rgb[s:s + 3]
def chunk(t, b): return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b))
raw = b''.join(b'\0' + bytes(img[y * W * 3:(y + 1) * W * 3]) for y in range(H))
open(out, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)) +
                      chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))
