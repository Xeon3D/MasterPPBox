"""Generate programmed Dolphin (U9) and Abyss (key card) chip images for an
emulated Midway Dolphin board -- i.e. what TouchMaster II's own dBetty()
('diag init') and dChris() (ProgramAbyss) would write into blank chips.

Clean-room re-implementation of t/coinmgr/dolphin.c write order, so the
output is byte-identical to the original code (checked by the Phase 1
harness). Output .nvr = 256 bytes chip memory + 1 byte fuses.

  python -I scripts/p1-mkchips.py --serial 100123456 --country 1 \
         --out-u9 u9.nvr --out-abyss abyss.nvr [--time T] [--devseed S]

--devseed makes the run deterministic (mirrors the harness' srandomdev());
without it the 'random' fields come from os.urandom like srandomdev().
"""
import argparse, hashlib, os, struct, sys, time

M32 = 0xFFFFFFFF
HERE = os.path.dirname(os.path.abspath(__file__))
LUT_PATH = os.path.join(HERE, '..', 'analysis', 'p1', 'raw', 'masterpal_lut.bin')

DLOFFSET = bytes([
    0x7f, 0x45, 0x4c, 0x46, 0x54, 0xf2, 0x05, 0x00, 0xd4, 0x80, 0x04, 0x08, 0xf4, 0xe0, 0x19, 0xa0,
    0x65, 0x78, 0x65, 0x63, 0x46, 0x72, 0x65, 0xF2, 0x54, 0xf2, 0xc4, 0x60, 0x2f, 0xc6, 0x69, 0x92,
    0x80, 0x40, 0x84, 0x15, 0x19, 0x37, 0xae, 0xea, 0x08, 0x83, 0x3d, 0x3c, 0xed, 0xb0, 0x05, 0xff,
    0xbb, 0xec, 0xc7, 0xd0, 0xab, 0x50, 0xc8, 0x1d, 0x8d, 0x7d, 0x08, 0x8b, 0x38, 0x00, 0xef, 0x0a])
SNOF = bytes([0x42, 0x31, 0x54, 0x2a, 0xfe, 0x91, 0xeb, 0x24, 0x99, 0x4d]) + bytes(6)


class FbsdRandom:
    """FreeBSD 3.2 libc random()/srandom(), 32-bit long semantics."""
    def __init__(self):
        self.state = [0] * 31
        self.f, self.r = 3, 0

    @staticmethod
    def _s32(x):
        x &= M32
        return x - (1 << 32) if x & 0x80000000 else x

    def srandom(self, x):
        st = self.state
        st[0] = self._s32(x)
        for i in range(1, 31):
            v = st[i - 1]
            hi, lo = int(v / 127773), v - int(v / 127773) * 127773   # C truncation
            v = 16807 * lo - 2836 * hi
            if v <= 0:
                v += 0x7fffffff
            st[i] = self._s32(v)
        self.f, self.r = 3, 0
        for _ in range(310):
            self.random()

    def random(self):
        st = self.state
        st[self.f] = self._s32(st[self.f] + st[self.r])
        out = ((st[self.f] & M32) >> 1) & 0x7fffffff
        self.f += 1
        if self.f >= 31:
            self.f = 0
            self.r += 1
        else:
            self.r += 1
            if self.r >= 31:
                self.r = 0
        return out


class Chip:
    """Blank AT88SC153 as the emulator presents it, with dwriteeprom() semantics."""
    def __init__(self):
        m = bytearray(b'\xff' * 256)
        m[0xC0:0xC8] = bytes([0x3B, 0xB2, 0x11, 0x00, 0x10, 0x80, 0x00, 0x01])
        m[0xC8:0xCA] = b'\xAE\x60'
        m[0xF9:0xFC] = b'\xD5\xFE\x7E'
        self.mem, self.fuses = m, 0x07

    def write(self, addr, data):            # dwriteeprom(): XOR obfuscation below 0xC0
        addr &= 0xFF
        data &= 0xFF
        self.mem[addr] = data ^ DLOFFSET[addr & 0x3F] if addr < 0xC0 else data

    def blow(self, bits):
        self.fuses &= ~bits & 0xFF

    def nvr(self):
        return bytes(self.mem) + bytes([self.fuses])


class Gen:
    def __init__(self, devseed=None):
        self.rng = FbsdRandom()
        self.devseed = devseed
        self.lut = open(LUT_PATH, 'rb').read()
        assert len(self.lut) == 0xC0

    def srandomdev(self):
        if self.devseed is None:
            self.rng.srandom(struct.unpack('<I', os.urandom(4))[0])
        else:
            self.rng.srandom(self.devseed)
            self.devseed = (self.devseed + 1) & M32

    def L(self, i):                         # GetMasterPalEntry()
        return i if i > 0xBF else self.lut[i]

    def betty(self, c, serial, country, now):
        for i in range(0x80, 0xC0):
            c.write(i, 0)
        c.write(0x3F, 0x01)                 # original passes addr 0x3f (zone 0), later overwritten
        for i in range(0x44, 0x7F):
            c.write(i, 0xFF)
        c.write(0x40, country & 0xFF)
        c.write(0x41, country >> 8)
        c.write(0x42, 0)
        c.write(0x43, (country & 0xFF) ^ (serial & 0xFF) ^ 0xA3)
        signed = serial - (1 << 64) if serial >= 1 << 63 else serial       # sprintf "%qd"
        buf = ('%d' % signed).encode()
        if len(buf) > 14:
            raise SystemExit('serial does not fit the 14-byte chip field (original would overflow buff[16])')
        buf = buf.ljust(16, b'\0')
        s = 0
        for i in range(14):
            c.write(i, buf[i] ^ SNOF[i])
            s += buf[i] - 256 if buf[i] & 0x80 else buf[i]
        gt = now & M32
        s += sum((gt >> k) & 0xFF for k in (0, 8, 16, 24))
        gt ^= 0x1B47A122
        for k in range(4):
            c.write(0x0E + k, gt >> (8 * k))
        ck = ((s + (s << 16)) & M32) ^ 0xB2F43749
        for k in range(4):
            c.write(0x12 + k, ck >> (8 * k))
        c.write(0x16, country & 0xFF)
        c.write(0x17, country >> 8)
        c.write(0x18, 0xAE)
        c.write(0x19, 0xC0)
        self.srandomdev()
        r = self.rng.random()
        for k in range(4):
            c.write(0x1A + k, r >> (8 * k))
        for i in range(0x1E, 0x40):
            c.write(i, 0)
        c.write(0xBF, 1)
        for a, v in ((0xF1, 0x4D), (0xF2, 0x3A), (0xF3, 0xEC), (0xF5, 0xE0), (0xF6, 0xFF), (0xF7, 0x3C),
                     (0xF9, 0x17), (0xFA, 0xAB), (0xFB, 0xDC), (0xFD, 0xCD), (0xFE, 0xA3), (0xFF, 0x45),
                     (0xCC, 0x7D), (0xCD, 0x7F), (0xCE, 0x77)):
            c.write(a, v)
        c.blow(0x02)
        c.blow(0x04)

    def chris(self, c, serial, country, major, minor):
        L = self.L
        self.srandomdev()
        h = self.rng.random() & 0xFFFF
        self.rng.srandom(((serial & M32) + h) & M32)
        x = [(self.rng.random() & 0xFF) ^ 0xB5 for _ in range(0xBF)] + [0]
        s = 0
        for k in range(8):
            b = (serial >> (8 * k)) & 0xFF
            c.write(k, b)
            s += b
        v = ((major << 16) | minor) & M32
        for k in range(4):
            c.write(L(0x0C + k), v >> (8 * k))
            s += (v >> (8 * k)) & 0xFF
        c.write(L(0x10), 0x0B)
        s += 0x0B
        for i in list(range(0x08, 0x0C)) + list(range(0x11, 0x38)):
            c.write(L(i), 0)
        c.write(0x38, 0x02)
        s += 2
        for a, b in ((0xBC, 0x50), (0xBD, 0xAA), (0xBE, h & 0xFF), (0xBF, h >> 8)):
            c.write(a, b)
        ck = (s + (s << 16)) & M32
        for k in range(4):
            c.write(L(0x3C + k), x[0x3C + k] ^ ((ck >> (8 * k)) & 0xFF))
        for a, b in ((0xF1, 0x5E), (0xF2, 0xD4), (0xF3, 0xC6), (0xF5, 0x73), (0xF6, 0xE9), (0xF7, 0x3C),
                     (0xF9, 0x4B), (0xFA, 0x00), (0xFB, 0xD2), (0xFD, 0x32), (0xFE, 0x41), (0xFF, 0x72)):
            c.write(a, b)
        s = 0

        def put(idx, val):
            nonlocal s
            c.write(L(idx), x[idx] ^ (val & 0xFF))
            s += val & 0xFF

        for k in range(4):
            put(0x40 + k, v >> (8 * k))
        for k in range(2):
            put(0x48 + k, country >> (8 * k))
        t = country ^ 0xDA4B
        for k in range(2):
            put(0x4A + k, t >> (8 * k))
        t = v ^ 0xA41301B4
        for k in range(4):
            put(0x4C + k, t >> (8 * k))
        t = ((country ^ 0xDA4B) ^ (v ^ 0xA41301B4) ^ 0xC582) & M32
        for k in range(4):
            put(0x44 + k, t >> (8 * k))
        c.write(L(0x78), 0x01)
        s += 1
        for i in list(range(0x50, 0x78)) + [0x79]:
            c.write(L(i), x[i])
        self.srandomdev()
        r = self.rng.random()
        c.write(0x7A, r & 0xFF)
        c.write(0x7B, (r >> 8) & 0xFF)
        s += (r & 0xFF) + ((r >> 8) & 0xFF)
        ck = (s + (s << 16)) & M32
        for k in range(4):
            c.write(L(0x7C + k), x[0x7C + k] ^ ((ck >> (8 * k)) & 0xFF))
        for i in range(0x80, 0xBC):
            c.write(L(i), x[i] ^ L(i))
        c.write(L(0xBE), h & 0xFF)
        c.write(L(0xBF), h >> 8)
        c.write(0xCC, 0x7D)
        c.write(0xCD, 0x7F)
        c.write(0xCE, 0x77)
        c.blow(0x02)
        c.blow(0x04)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--serial', type=int, required=True, help='system serial number (diag init takes 9 digits)')
    ap.add_argument('--country', type=int, default=1, help='country code (1 = USA 2-coin)')
    ap.add_argument('--version', default='3.0', help='Abyss authorisation version major.minor')
    ap.add_argument('--time', type=int, default=None, help='manufacture date, unix time (default now)')
    ap.add_argument('--devseed', type=lambda v: int(v, 0), default=None)
    ap.add_argument('--out-u9', required=True)
    ap.add_argument('--out-abyss', required=True)
    a = ap.parse_args()
    major, minor = (int(p) for p in a.version.split('.'))
    g = Gen(a.devseed)
    u9, ab = Chip(), Chip()
    g.betty(u9, a.serial, a.country, int(time.time()) if a.time is None else a.time)
    g.chris(ab, a.serial, a.country, major, minor)
    for path, chip in ((a.out_u9, u9), (a.out_abyss, ab)):
        open(path, 'wb').write(chip.nvr())
        print(hashlib.sha256(chip.nvr()).hexdigest(), path)


if __name__ == '__main__':
    sys.exit(main())
