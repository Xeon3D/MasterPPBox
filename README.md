# ⚠️ No support or instructions will be given for this fork.

# This was AI coded... grab an AI to sort it out.

# Do not bug the 86Box devs about this. They have nothing to do with it, other than writing the base code this is messed up with.

---

MasterPPBox
===========

**MasterPPBox is a fork of [86Box](https://github.com/86Box/86Box) (by way of
[86Box-Next2](https://github.com/Xeon3D/86Box-Next2)) that runs untouched disk
images of Midway's TouchMaster II countertop cabinets (FreeBSD 3.2, 2000–2001)
on their own hardware: an Intel BL440ZX board with its on-board ATI Rage Pro
Turbo AGP, a Celeron, the on-board Ensoniq ES1373, Midway's Dolphin I/O board
and a MicroTouch touchscreen.**

The game checks its hardware, and the emulated hardware answers:

- **The Dolphin I/O board** (ISA, D0000h), with its AT88SC153 U9 chip and the
  Abyss key. The game's protection reads both. MasterPPBox emulates the board
  and the chips, including their Answer-To-Reset, so `diag`'s Dolphin I/O Test
  passes. It programs them as the game's own factory flow would, from
  **Tools → TouchMaster Key Generator**: a serial number, one of the game's 54
  countries, and a key version.
- **The ATI Rage Pro Turbo AGP** (1002:4742), which Midway's display server
  `dl` drives from user space, with the 2D engine, the 3D front-end scaler
  (sprites, fades, masking) and the VLINE interrupt. The BL440ZX's own BIOS
  supplies the chip's video BIOS and puts it at I/O D800h, and the ES1373 at
  EF00h: the two addresses Midway's kernel hard-codes.
- **Coins and buttons:** the Dolphin's electronic coin lines, TEST and
  Calibrate, from the I/O Board menu and the toolbar.

No byte of the game is patched. Both releases run: **2.03** (the OEM field
release) and **3.0x** (the ALPHA10 development build).

Credit
------

**All credit for the emulator itself belongs to the 86Box project and its
authors** (see [AUTHORS](AUTHORS)). MasterPPBox adds a little TouchMaster
hardware on top of their work. Sibling of
[PeepeeBox](https://github.com/Xeon3D/PeepeeBox) (funworld Photo Play) and
[MegaPPBox](https://github.com/Xeon3D/MegaPPBox) (Merit Megatouch).

Released under the GNU General Public License version 2 or later, the same as
86Box. See [COPYING](COPYING). The ROMs in [roms/](roms/) belong to their
owners (Intel, ATI); see [roms/LICENSE](roms/LICENSE).

Running it (Windows)
--------------------

### What you need

- **A TouchMaster II hard disk image**: the disk of a real cabinet, copied into
  a file. MasterPPBox does not come with any.
- **A Windows x64 PC.**

### Step 1: Download and unzip

From the [latest release](https://github.com/Xeon3D/MasterPPBox/releases/latest),
download `MasterPPBox-windows-x64.zip` and extract it. Keep the folder together.

| In the folder | What it is |
|---|---|
| `MasterPPBox.exe` | The emulator |
| `roms\` | BL440ZX BIOS and the Rage Pro / Rage IIC video BIOSes |
| `TouchMaster-2.03-OEM\` | The 2.03 cabinet: settings, CMOS, keyed Dolphin chips (serial 100922889, Canada) |
| `TouchMaster-3.0x-ALPHA10\` | The 3.0x cabinet: settings, CMOS, keyed Dolphin chips (serial 60000922889, USA DBV, key 3.0) |
| `Run TouchMaster 2.03 (OEM).cmd`, `Run TouchMaster 3.0x (ALPHA10).cmd` | Start a cabinet |

### Step 2: Add your disk image

**Make a copy of your image first:** the game writes its settings, audits and
scores onto it.

The cabinets expect the disk trimmed to the size of its FreeBSD slice,
16841664 sectors (8622931968 bytes, 16708 cylinders × 16 heads × 63 sectors).
The rest of a field disk is empty. Make it with
[TouchMaster/scripts/p3-mkdisk.py](TouchMaster/scripts/p3-mkdisk.py), which
checks that the dropped tail really is empty:

```
python -I p3-mkdisk.py <your-image> tm-oem.img 16841664
```

Name it `tm-oem.img` (2.03) or `tm-alpha10.img` (3.0x) and put it in the
cabinet's folder, next to its `86box.cfg`.

### Step 3: Play

Double-click the cabinet's `Run … .cmd`. It boots to the game's menus in
about a minute.

- **The mouse is your finger**: click on the screen to touch it.
- **Coins, TEST and Calibrate** are in the I/O Board menu and on the toolbar.
- **Other keys:** Tools → TouchMaster Key Generator writes new Dolphin chips
  for another serial or country. A country different from the one in the
  game's settings makes it restore its factory settings.

What's here
-----------

| Path | |
|---|---|
| `src/` | The emulator: 86Box-Next2 plus the TouchMaster hardware (`src/device/dolphin_io.c`, `at88sc153.c`, `dolphin_keygen.c`; `src/video/vid_ati_mach64*.c`, the Rage IIC and Rage Pro; the BL440ZX's on-board video in `src/machine/`) |
| `rigs/` | The two cabinets' folders as in the release (without the emulator, ROMs and images) |
| `roms/` | The ROMs the cabinets need |
| `TouchMaster/` | The reverse-engineering work: [TouchMaster.md](TouchMaster/TouchMaster.md) (overview), [Docs/](TouchMaster/Docs/) (one document per phase, 00–10), [scripts/](TouchMaster/scripts/) (every tool used, reproducible) |

The research covers the boot chain, the Dolphin protection (fully documented
and re-implemented), the platform's hardware, video, coins and sound, the
3.0x build, the key generator, and why the hardware is a BL440ZX with a Rage
Pro Turbo ([Docs/10](TouchMaster/Docs/10-bl440zx-ragepro.md)). The extracted
game files, the disk images and Midway's binaries are not included.

Building
--------

As 86Box: CMake with Qt 6 (see [doc/](doc/) and `.github/workflows/`). The
release's Windows build is MSYS2 UCRT64, static (`-DSTATIC_BUILD=ON`), with
`-DAUTOMATION=OFF -DGDBSTUB=OFF`.
