#!/usr/bin/env python3
"""p10-roms.py - install the user's ATI 3D Rage Pro (PCI ID 1002:4742) video BIOS
dumps into 86Box's ROM tree, as the 32K images the card decodes.

Inputs (read only): Info/Rage Pro/*.  The two 27C512 dumps hold the BIOS in
their lower 32K (upper half blank: 00h or FFh); the other two are 32K reads.
Each image is checked for 55AAh, a 32K length byte, a zero checksum and a PCI
data structure naming 1002:4742 before it is written.

Output: 86box/roms/video/mach64/ragepro_agp_*.bin, and the SHA256 of every
input and output in analysis/p10/raw/roms-sha256.txt.
"""
import hashlib
import os
import struct
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "Info", "Rage Pro")
DST = os.path.join(ROOT, "86box", "roms", "video", "mach64")
LOG = os.path.join(ROOT, "analysis", "p10", "raw", "roms-sha256.txt")

# (source, member in zip or None, output name)
IMAGES = [
    ("rage-pro-turbo-at27c512r-dip28.bin", None, "ragepro_agp_turbo_3.091.bin"),
    ("109-49800-11.zip", "109-49800-11.ROM", "ragepro_agp_113-49801-101_2000.bin"),
    ("d003vid.dmp", None, "ragepro_agp_113-49801-101_1998.bin"),
    ("rage2pr-bga-40212-103-mx27c512.bin", None, "ragepro_agp_113-40212-103.bin"),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def check(img, name):
    if img[:2] != b"\x55\xaa" or img[2] * 512 != 0x8000:
        sys.exit(f"{name}: no 32K option ROM header")
    if sum(img) & 0xFF:
        sys.exit(f"{name}: checksum not zero")
    pcir = struct.unpack_from("<H", img, 0x18)[0]
    if img[pcir:pcir + 4] != b"PCIR" or struct.unpack_from("<HH", img, pcir + 4) != (0x1002, 0x4742):
        sys.exit(f"{name}: PCI data structure is not 1002:4742")


def main():
    lines = []
    os.makedirs(DST, exist_ok=True)
    for src, member, out in IMAGES:
        path = os.path.join(SRC, src)
        raw = open(path, "rb").read()
        lines.append(f"in   {sha(raw)}  Info/Rage Pro/{src}")
        if member:
            raw = zipfile.ZipFile(path).read(member)
            lines.append(f"in   {sha(raw)}  Info/Rage Pro/{src}:{member}")
        img = raw[:0x8000]
        if len(raw) > 0x8000 and set(raw[0x8000:]) - {0x00} and set(raw[0x8000:]) - {0xFF}:
            sys.exit(f"{src}: upper half is not blank")
        check(img, src)
        open(os.path.join(DST, out), "wb").write(img)
        lines.append(f"out  {sha(img)}  86box/roms/video/mach64/{out}")
    open(LOG, "w", newline="\n").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
