"""Extract the FreeBSD 3.x kernel message buffer (dmesg) from a running 86Box
guest through the automation socket: scan physical RAM top-down for struct
msgbuf (magic 0x063062, header at the end of the buffer area), then unroll the
ring. Read-only (memr).
  python -I scripts/p3-msgbuf.py <vmdir> <port> [out.txt]"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
Auto = import_module('p3-auto').Auto

a = Auto(sys.argv[1], sys.argv[2])
mem = a.req('info')['mem_kb'] * 1024
CH = 0x10000
def memr(addr, n):
    out = b''
    while n:
        k = min(n, CH)
        out += bytes.fromhex(a.req('memr %d %d' % (addr, k))['data'])
        addr += k; n -= k
    return out
MAGIC = struct.pack('<I', 0x063062)
for base in range(mem - CH, 0, -CH):
    blk = memr(base, CH)
    i = blk.rfind(MAGIC)
    while i >= 0:
        if i + 20 <= len(blk):
            magic, size, bufx, bufr, ptr = struct.unpack_from('<5I', blk, i)
            if 0 < size <= 0x100000 and bufx < size:
                hdr = base + i
                buf = memr(hdr - size, size)
                text = (buf[bufx:] + buf[:bufx]).replace(b'\0', b'').decode('latin-1')
                print('msgbuf header @%#x size %d bufx %d ptr %#x' % (hdr, size, bufx, ptr), file=sys.stderr)
                if len(sys.argv) > 3: open(sys.argv[3], 'w', newline='\n').write(text)
                else: sys.stdout.write(text)
                sys.exit(0)
        i = blk.rfind(MAGIC, 0, i)
sys.exit('msgbuf not found')
