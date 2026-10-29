# TouchMaster II: HDD image deep dive (Phase 0)

**Goal:** make Midway TouchMaster II run keyless under 86Box.
**Inputs:** `HDD Images/OEM/TOUCHMASTEROEM.bin` and `HDD Images/TOUCHMASTERALPHA10/TOUCHMASTERALPHA10.img`.
**Method:** I read everything offline with a purpose-built read-only UFS1 reader (`scripts/ufs1.py`). The originals were never mounted or modified. Evidence is under `analysis/` and the scripts are under `scripts/`.

---

## 0. TL;DR

1. **What it is:** Midway Games **TouchMaster II**, a countertop touchscreen game. It runs on **FreeBSD 3.2-RELEASE** (i386, ELF, gcc 2.7.2.1) with a fully custom userland game stack under `/t`.
   - The **OEM** dump is release **2.03** (built 09 Oct 2000). It is a field machine that was used until Jan 2015.
   - The **ALPHA10** dump is a **3.0x development image** (2001). It contains **the complete C/C++ source tree** for the game OS, including the protection code, the video drivers, the I/O drivers and the build makefiles. It last booted on real hardware in April 2020.
2. **The "key":** the protection is the **Dolphin I/O board**, an ISA card at memory 0xD0000 / IRQ 5. There is also a later PCI variant, Xilinx `10EE:0001`. The board carries **two Atmel AT88SC153-class secure-memory chips** that the CPU accesses by bit-banging I²C through one FPGA register:
   - **"Dolphin" chip (U9, on the board):** system serial number, manufacture date and default country.
   - **"Abyss" chip, the "configuration card":** the removable key. It is paired to the Dolphin serial number and holds the version authorisation and the country code.
3. **The protection algorithm is fully known.** `t/coinmgr/dolphin.c` in ALPHA10 contains every routine (`dAndy` … `dGloria`), every password, the XOR tables and the checksums. The address-scramble LUT is in `t/video/olib.c` (`GetMasterPalEntry`).
4. **Missing key → free play, not a hard lock.** If the Abyss chip is absent, the menu shows *"Configuration security board not found … Free Play only"* and continues.
5. **Missing Dolphin board → hard lock.** If the Dolphin board is absent, the menu stops at **"Dolphin I/O card not found!"**.
6. **Blank chips are self-provisioning.** If the chips answer but are unprogrammed, the software runs its own factory serialisation flow (`diag init`, then `ProgramAbyss`) and writes them.
7. **Preferred route to keyless:** emulate an ISA Dolphin board in 86Box that contains two emulated blank or pre-built AT88SC153 chips, persisted to NVR. This needs **zero binary patches**. Binary patching of 4 statically linked binaries is the fallback.
8. **The real blocker is video, not the key.** `dl` (the display server) drives an **ATI Rage IIC** (`1002:4756`) directly from user space and needs:
   - the Mach64 GT **3D scaler/alpha-blend path**;
   - a **VLINE interrupt**;
   - **hard-coded I/O port 0xD818**.

   Sound likewise hard-codes the **ES1373 at I/O 0xEF00**. 86Box has an ES1371/1373 and an "ATI 3D Rage II+" (Mach64 GT-B), but **not a Rage IIC**, and the fixed I/O addresses depend on how the BIOS assigns PCI resources.

---

## 1. Image inventory and integrity

| Image | Size | SHA-256 | BSD label | Build |
|---|---|---|---|---|
| `OEM/TOUCHMASTEROEM.bin` | 20,020,396,032 | `0b994da7e8d72eaec6b8c870911e5c51288c78c7157f547a34aabd414aba8872` | 16,841,664 sectors (8.62 GB) | TM II **2.03**, release date 10/09/2000 |
| `TOUCHMASTERALPHA10/TOUCHMASTERALPHA10.img` | 10,005,037,056 | `a91d015f0de0cc02b278e49bd9d93a07a479006781e4a2962dec69b6a9074119` | identical label | TM II **3.0x** dev (dl.cc rev 212, 11/27/00; sources to 06/2001) |

- **Disk layout:** both disks are FreeBSD **"dangerously dedicated"**, with no real MBR partition table.
  - Sector 0 holds `boot1`, which carries a fake partition entry: type `0xA5`, start 0, 50 000 sectors.
  - Sector 1 holds the disklabel (`amnesiac`/`fictitious`, geometry 16 heads × 63 sectors × 16708 cylinders).
- **Space past the label:** everything beyond the 8.62 GB label is zero (sampled every 64 MB). Both dumps can be **trimmed to 8,622,931,968 bytes** for 86Box.
- **`/kernel` location:** LBA 2080–135632 (OEM) and 2080–290384 (ALPHA10). That is below cylinder 1024 under the 16/63 geometry, so CHS INT13 booting by `boot2` works.

| Partition | Offset (sectors) | Size | FS | Mount | Notes |
|---|---|---|---|---|---|
| `wd0a` | 0 | 7.99 GB | UFS1 (FFS, 8K/1K) | `/` **ro,async,noatime** | OS + `/t` game tree (≈5 GB, mostly media) |
| `wd0b` | 16,373,265 | 100 MB | UFS1 | `/rw` rw, `noauto` | Writable state: audits, settings, hiscores, tmp, crash |
| `wd0f` | 16,578,065 | 128.7 MB | swap | — | |

**Evidence:**
- `analysis/p0/raw/{OEM,ALPHA10}-{root,rw}.tsv`: full manifests (mode, size, mtime, uid:gid, flags, path, link target).
- `analysis/p0/raw/*-devnodes.txt`: /dev majors and minors.
- `analysis/p0/raw/image-sha256.txt`: image hashes.
- `analysis/fs/<img>/{root,rw}`: extracted trees (files over 4 MB on `/` were skipped; they are all `.tmz`/`.tm2` media).

### What differs between the images
- **ALPHA10 has extra files:**
  - all `*.c/*.cpp/*.h`, `makefile`s, `.o` objects and VSS `vssver.scc` files;
  - `/t/video/r2c|r128|cyrixmgx` driver sources;
  - `/t/mpn` (MPN network library) sources;
  - extra games (air hockey, billiards, bowling, golf, …);
  - new device nodes `/dev/pcidol0` (major 201), `/dev/eit0` (202) and `/dev/rot0` (225).
- **ALPHA10 kernel:** larger (1.9 MB vs 1.38 MB). It is build #34 of 4 Jul 2000 and adds the `pcidol`, `rot`, `iet`, USB and extra NIC drivers.
- **Identical between the images:** `/etc/rc.local`, `/etc/rc.conf`, `/etc/fstab`, `/etc/ttys` and the loader configuration.

---

## 2. System identity

- **OS:** FreeBSD **3.2-RELEASE**. The kernel is custom: OEM is `#0: Sun Apr 9 07:15:19 GMT 2000` and ALPHA10 is `#34: Tue Jul 4 17:16:33 GMT 2000`. It uses the old `wd` IDE driver (`/dev/wd0*`), and the ELF userland is linked against `ld-elf.so.1`.
- **CPU:**
  - The **OEM kernel has only I686_CPU** (`i686_pagezero`, `init_6x86MX`, no `i586_*`). It will **panic with "CPU class not configured" on a Pentium/P55C**. The current `86box/86box.cfg` (`pentium_p55c`) therefore **will not boot the OEM kernel**.
  - The ALPHA10 kernel adds I586_CPU.
  - Cyrix 6x86MX/MII and CS5530 IDE support are compiled in, which matches the `cyrixmgx` (MediaGX) video variant in the source.
- **Toolchain:** gcc 2.7.2.1 (kernel) and g++ with C sources compiled `-xc++`. The binaries are stripped of static symbols; the shared `libolib.so.1.0` keeps its dynamic symbols. Source control was Microsoft VSS (`$Header: /TouchMaster_II/2.0x|3.0x/source/...`). Developers named in headers: Kevin, Vince, Chris, Mark, Vinh, Glenn.
- **Packing and anti-debug:** none. All binaries are plain ELF. The only obfuscation is in the protection code:
  - an XOR table over EEPROM data (`dloffset`);
  - an address-scramble LUT deliberately misnamed `GetMasterPalEntry` ("this has NOTHING to do with palettes");
  - functions given girls' names (`dBetty` = init Dolphin, `dDana` = read Dolphin, `dEve` = read Abyss, …);
  - a passwords array named `dlcolortable`.

---

## 3. Boot chain (power-on → game)

```
BIOS ─► boot1 (sector 0, "dangerously dedicated")
     ─► boot2 (sectors 1-15) ─► /boot/loader (Forth; autoboot_delay=1, splash /loading2.bmp)
     ─► /kernel  (FreeBSD 3.2, console muted: kern.consmute=1)
     ─► init ─► /etc/rc   (stock 3.2 rc; root remounted rw; /rw is noauto here)
              ─► /etc/rc.local
                   sysctl kern.quantum=5000, kern.corefile=/var/crash/%N.core, consmute=1
                   cd /t/video ; ./dl mount &        ◄── display server + process supervisor
                   sleep 5
                   upgrade scan: mount wd1a, wd2a, wd3a, wfd0a, acd0a (cd9660) on /mnt
                                 and run /mnt/upgrade/upgrade <dev> if present
                   cd /t/menu ; ./menu               ◄── the game shell (foreground)
```

**`dl mount` (`/t/video/dl` → `dl.r2c`):**
- **`/rw` setup:** runs `umount -f /rw`, then `fsck -py /rw`. On failure it runs `newfs -b 8192 /dev/rwd0b`, recreates the `/rw` skeleton and reboots. On success it mounts `/rw` (sync) and runs `ldconfig /usr/lib /t/video`.
- **Emergency wipe:** if Dolphin DIP switch 8 is ON (`dolphin[0x60] & 0x80 == 0`), it wipes `/rw/{var/log,crash,aa,tmp,games}`.
- **Daemons:** forks `syslogd`, then `../sound/sound`, `../io/io`, `../coinmgr/coinmgr` (which runs `/t/coinmgr/uart`) and `../midas/midas`. It talks to all of them over FIFOs in `/tmp/{dl,sound,io,coinmgr,midas,comm}` and SysV shm/msg queues.
- **Video:** owns the video hardware through `/dev/rag0` and `/dev/mem`, and writes vsync ticks to `/tmp/vsync`.

**`menu` startup:**
1. Waits up to 60 s each for `/rw/aa/aa.dat`, `/tmp/io/touch` and `/tmp/sound/fifo.0`, and shows `ABORT (AA|IO|SND)` if one never appears.
2. Calls `CheckHardwareOK()`, the security gate described in §5.
3. Calls `setmodempresent()`, which tries to open `/dev/cuaa4`.
4. Calls `CheckFactoryRestore()`.
5. Builds the menu from `/rw/menu/menu.ini`. That file is written by `/t/system/mgl` according to the country code; erotic/Playboy titles are filtered per country.
6. Starts games as separate processes (`/t/games/<name>/<name>`), each of which calls `CallMeFirst()`. `CallMeFirst` is only a version-string hook (`_!@OLIB@!_ KDupdateversionsKD`), not a check.
7. The TEST switch is handled by `coinmgr`, which runs `/t/diag/diag` (operator menus) and relaunches `menu` afterwards.

**Lockdown layer** (so a missing tool is not mistaken for corruption):
- every getty in `/etc/ttys` is **off**, and there is no console login;
- `kern.consmute=1`;
- `/` is mounted ro in fstab;
- `/upgrade` → `t/upgrade`;
- `/tmp` → `/rw/tmp`;
- `/var/*` symlinks point into `/rw`.

---

## 4. Hardware the software expects

| Function | Expected device | How it's accessed | 86Box status (this build) |
|---|---|---|---|
| **CPU** | i686-class (P-II/Celeron/PPro, Cyrix 6x86MX/MII, MediaGX) | OEM kernel I686-only | ✅ use a P6-class CPU (e.g. Celeron/P-II on 440BX/LX/EX). ❌ the current cfg (P55C) is wrong for OEM |
| **Disk** | IDE primary master, `wd0`, CHS 16/63 | stock `wdc0` 0x1F0/IRQ14 | ✅ |
| **Video (primary)** | **ATI Rage IIC PCI `1002:4756`** (kernel `rag` also accepts Rage Pro `4742/4744/4749/4750/4751`) | kernel `rag` maps BAR0 8 MB; **ISR and `rag_read()` hard-code I/O `0xD818`** (CRTC_INT_CNTL, so the I/O BAR must be **0xD800**). `dl.r2c` mode-sets 640×480 15/16bpp itself, then uses the Mach64 GUI engine **plus the GT 3D scaler** (`SCALE_3D_CNTL`, `TEX_CNTL`, `ALPHA_START/X_INC/Y_INC`, `SCALE_*`) for scaled/alpha blits, and **blocks on a VLINE interrupt at line 478/479** (`read(/dev/rag0)`, *no timeout*) | ⚠️ 86Box has "ATI 3D Rage II+ DVD" (`1002:4755`, Mach64 GT-B), not IIC. The ID differs, and 3D-scaler and VLINE-IRQ fidelity are unverified |
| Video (alternates in source) | ATI **Rage 128** `5245/5246/524B/524C` (`rot` driver, ALPHA10 kernel only; `dl.r128` makefile target, **binary not present**); Cyrix **MediaGX** (`cyrixmgx`, no binary) | — | 86Box has Rage 128 / Rage 128 Pro, but `dl.r128` would have to be built |
| **Sound** | **Ensoniq ES1371/ES1373** `1274:1371` ("Ensoniq AudioPCI 1373 Driver, © 2000 Midway") | kernel `est` maps a 4 KB DMA page; **ISR and the `sound` daemon hard-code I/O base `0xEF00`** (`IOPORT` in `sounddef.h`; regs `0xEF04/0C/2A/38/3E`) | ✅ device exists ("Ensoniq AudioPCI (ES1371)") **if the BIOS puts BAR0 at 0xEF00** |
| Sound (alt, ALPHA10) | Intel ICH AC'97 `8086:2415/2425` (`iet` → `/dev/eit0`) | | n/a |
| **Touchscreen** | **MicroTouch serial** controller on **COM1** (`/dev/cuaa0`, 9600 8N1) | `io` sends `Z`, `PN81`, `OI`, `R`, `PN81`, `FT`, `SE1`, `FN03`, `MS`; Format-Tablet 5-byte packets; `checktsack()` **blocks forever** without a reply | ✅ "3M MicroTouch (Serial)" |
| **Security/I/O board** | **Midway Dolphin, ISA**: 64 KB memory window **0xD0000**, **IRQ 5** (`dolphin0`, `/dev/dolphin0` major 11). PCI variant: Xilinx `10EE:0001` → `/dev/dolpci0` (3.x only) | see §5 / §6 | ❌ **does not exist; must be written** |
| Modem (optional) | PCI 16550-class modem (`11c1:0480` Lucent, `12b9:1008` USR, or class 07/00/02) → `/dev/cuaa4` | only for MPN tournaments / dial-in | optional |
| NIC (dev only) | `fxp0` / `de0`, rc.conf `10.6.42.11/16` (hostname `kevin1.touchmaster`) | | optional |
| Serial peripherals (optional) | Dolphin on-board UART(s) (`SSCP_*`, EZ95/EZKEYII keypads, bill validators), MIDAS (EOT/ACK/NAK protocol), LED sign | via Dolphin regs `0x20..0x2E` | not needed for free play |

**ISA kernel config (OEM; ALPHA10 adds `ep0` at 0x300 IRQ10):**
- fdc0 0x3F0/6/2;
- wdc0 0x1F0/14 and wdc1 0x170/15;
- atkbdc 0x60 and psm0 IRQ12;
- sio0 0x3F8/4, sio1 0x2F8/3, sio2 0x3E8/5 and sio3 0x2E8/9;
- ppc0 IRQ7;
- npx0;
- **dolphin0 maddr 0xD0000 IRQ5**.

**PCI drivers:**
- OEM: de, fxp, vga, **rag**, **est**, sio_pci, ide_pci.
- ALPHA10 adds: ax, mx, pn, rl, tl, tx, vr, vx, wb, xl, uhci/usb, **rot**, **pcidol**, **iet**.

---

## 5. The protection: Dolphin + Abyss

### 5.1 Hardware interface (from `dolphin.c`, `olib.c`, `coinmgr.c`, `io.c`, `diag.c`)

**ISA Dolphin register window** (byte offsets from 0xD0000, accessed via `/dev/mem` mmap or `/dev/dolphin0` mmap):

| Offset | Dir | Meaning |
|---|---|---|
| `0x20 + 2n` (n=0..7) | R/W | On-board UART (16550-style) registers |
| `0x2E` | R/W | UART-related |
| `0x50` (word) | R | **Board ID / FPGA rev**: the high byte **must be 0x01**, the low byte **must be ≥ 0x02**. Otherwise you get *"Dolphin I/O card not found!"* / *"…needs newer FPGA"* (hard lock) |
| `0x58` | R/W | **Atmel bit-bang port**. Write: bit0 SDA, bit1 SCL, bit2 RST, bit3 select **chip 0 (Dolphin/U9)**, bits 4/5 select **chip 1 (Abyss)**, bit6 drive enable. Read bit0 = SDA in |
| `0x60` | R | DIP switches, active-low. **bit7 = DIP 8 "Emergency Restore"** (0 = ON → `/rw` wipe, and menu waits for it to be turned off); bit0 = touch-invert |
| `0x62`, `0x64` | R | Coin/door/TEST switch inputs (inverted) |
| `0x66` | R/W | Outputs: meters, coin/bill lockouts |
| `0x70` | R | Interrupt cause (bit1 = UART) |
| `0x74` (word) | R/W | Control: bit1 toggled every frame by `dl` (heartbeat/watchdog?), bit2 touch LED, bit4 UART reset, bit10 timer IRQ enable, bit0 LED blink |
| `0x76` (word) | W | Timer config (`0x8010` ≈ 215 Hz; init `0xFF10`) |

**PCI Dolphin (3.x):** registers are words at:
- `0x00` (IRQ status: bit2 timer, bits 4–7 UARTs);
- `0x10` (control);
- `0x14` (timer);
- `0x18`;
- `0x20` (ID);
- `0x4E` (`0x3330` self-test);
- `0x50` (chip 0 bit-bang) and `0x54` (chip 1 bit-bang);
- `0x60` (DIP);
- `0x64`/`0x68` (switches);
- `0x6C` (outputs);
- `0x70` (7-segment LED);
- `0x100 + 0x20·n` (4 UARTs).

**Kernel driver behaviour that matters:**
- `dolphin_probe` (ISA) **does no presence check**. It only prints, so `/dev/dolphin0` always opens.
- `dolphin_read()` sleeps on the IRQ with a **60-tick (0.6 s) timeout**. Without an IRQ, `coinmgr` keeps running at about 1.7 Hz instead of 215 Hz.
- `dolphin_mmap` maps 64 KB from `maddr`.
- `dolphin_open` allows a single opener (`coinmgr`).

### 5.2 Chip protocol (AT88SC153-style, 256 bytes = 4 × 64-byte zones)
- **Commands:**
  - `0xB0|zone<<2` write;
  - `0xB1|zone<<2` read;
  - `0xB3` verify write-password 0;
  - `0xB7` verify secure code / write-password 1;
  - `0xBA` write fuses;
  - `0xBE` read fuses.
- **Framing:** I²C-style start/stop, MSB first, ACK/NAK.
- **Config zone (0xC0–0xFF), cleartext:**
  - `0xC0` must not be 0x00 or 0xFF (otherwise error −2, "no chip");
  - `0xC8–0xC9` **fab code must be `AE 60`** (otherwise error −5, "not our chip");
  - `0xCC–0xCE` access registers;
  - `0xF0`/`0xF8` password attempt counters, which **must read `0xFF`** after a password verify;
  - `0xF1–0xFF` passwords.
- **XOR obfuscation:** data at addresses < 0xC0 is XORed in software with the 64-byte `dloffset` table, which starts with `7F 45 4C 46` (the ELF magic, to look like junk).

**Dolphin (internal, U9) layout, written by `dBetty`:**
- 0x00–0x0D: ASCII serial XOR `42 31 54 2A FE 91 EB 24 99 4D`;
- 0x0E–0x11: manufacture `time_t` XOR `0x1B47A122`;
- 0x12–0x15: checksum `(s + (s<<16)) ^ 0xB2F43749`;
- 0x16–0x17: country;
- 0x18–0x19: **magic `AE C0`** (programmed flag);
- 0x1A–0x1D: random "MAC";
- 0x40–0x43: country, distributor and check digit;
- 0xBF: layout = 1.

Passwords set by `dBetty`: W0 `EC3A4D`, R0 `3CFFE0`, W1 `DCAB17`, R1 `45A3CD`. Fuses CMA and PER are blown.

**Abyss (external key) layout, written by `dChris`/`dGloria`:**
- 0x00–0x07: 64-bit serial (**must equal the Dolphin serial**, else −6 *"serial number on the configuration card … does not match"*);
- address scrambling via the `GetMasterPalEntry` LUT;
- a per-card XOR table generated from FreeBSD `random()` seeded with `(serial & 0xffffffff) + hash`, where the 16-bit hash is stored at 0xBE–0xBF;
- 0x10 = `0x0B`;
- 0x38 = layout `0x02` (< 2 → −7 "early serialization tools");
- 0x40–0x43: version (major<<16 | minor; new cards get **3.0**);
- 0x44–0x4F: checksums of version and country (`^0xDA4B`, `^0xA41301B4`, `^0xC582`);
- 0x78 = `0x01`;
- 0xBC–0xBD: **magic `50 AA`** (programmed flag).

Passwords set by `dChris`: W0 `C6D45E`, R0 `3CE973`, W1 `D2004B`, R1 `724132`. A code comment admits the checksum at 0x7C–0x7F is never checked.

### 5.3 Decision logic: `menu::CheckHardwareOK()` (identical strings in the 2.03 binary)

```
mmap /dev/mem @0xD0000
ID word @0x50: hi != 0x01                 → "Dolphin I/O card not found!"        HARD LOCK
               lo  < 0x02                 → "Dolphin I/O card needs newer FPGA"  HARD LOCK
dDana (Dolphin chip):
   0  → store serial + mfg date in aa.dat
  -1  (unprogrammed) → LOCKFREEPLAY=1, run "/t/diag/diag init" (factory "Enter Serial Number"
                        screen, "Do Later" allowed) → dBetty programs U9
  <-1 → "System Security Failure (%d) - Call for Service"                         HARD LOCK
serial == 0 (e.g. "Do Later")  → lock free play, skip remaining checks, continue
dEve (Abyss key):
   0  → LOCKFREEPLAY=0 (coin play allowed)
  -1  (blank card) → ProgramAbyss(): dChris(serial, defcountry, 3, 0) → factory restore
  -2  (no card) → "Configuration security board not found (Check cables) Free Play only",
                  lock free play, continue on touch
  -6  serial mismatch → HARD LOCK;   -7 early card → HARD LOCK;   other <-1 → HARD LOCK
country from Abyss != aa.dat country → run "diag factoryrestore"
(version-authorisation check is compiled out: "#if 0  // Ed said to take this out on 10/25/99")
```

- **`mgl`** calls `dDana`/`dEve` to read the Abyss version, but in this source the per-version game gating is effectively disabled.
- **`diag`** displays the "AV:" (Abyss version), the serial and the manufacture date. It also offers a country-code change (`dGloria`), which rewrites both chips.
- **The security code (`dolphin.o`) is statically linked into four binaries**, confirmed by constant scans in both images: `menu`, `coinmgr`, `diag` and `system/mgl`.

### 5.4 Things that look like protection but are not gates
- **`tm.cksum` / `master.cksum` / `/t/signature`** ("TouchMaster Checksum V1": `md5`, then `cksum size name` per file). These are verified **only** when the operator runs the diag "file test" screen, which displays errors. **Nothing checks them at boot**, so patched files will only show up in that screen. `signature` is the sum of the cksums (OEM: `110bbc80e75b`).
- **`secfail` in `dl.cc`:** a silent-sabotage switch (random object flags, mismatched deletes). It is **never set** anywhere in the 3.0x source.
  - *Open item:* confirm it is also inert in the 2.03 `dl.r2c` binary.
- **`DL_SECURITY_*` flags:** these are display-list object ownership flags, not anti-piracy.
- **Upgrade media:** `upgrade.c` copies `/mnt/t` → `/t` with no signature or Dolphin check.
- **Diag "touch keys":** hidden touch-sequence easter eggs and service menus, not a gate.

---

## 6. Paths to "keyless on 86Box"

**The boring explanation, checked first.** The simplest reading would have been "the game checks a dongle and refuses to run". The source disproves part of that and confirms the rest:
- a missing **key** only forces free play;
- a missing **board** is fatal;
- blank chips get programmed by the game itself.

So no exotic crypto or online check is involved, and there are no time bombs in the security path. MPN is a dial-up tournament/audit network and is not needed to boot.

**A. Emulate the ISA Dolphin in 86Box (recommended; zero patches)**

The device needs:
- **a memory mapping at 0xD0000 (64 KB)** with:
  - ID `0x0102` at `0x50`;
  - DIPs at `0x60` all OFF (`0xFF`, bit7 = 1);
  - switches at `0x62`/`0x64` reading `0xFF` (nothing pressed), with a TEST button mapped for operator menus;
  - outputs at `0x66`;
  - a 215 Hz timer raising **IRQ 5** under `0x74` bit10 / `0x76`;
  - `0x70` status;
- **two AT88SC153 state machines** behind the `0x58` bit-bang port, each 256 bytes and persisted in NVR. Each one:
  - presents config `0xC0` ≠ 0/FF and fab `AE 60`;
  - returns `0xFF` at `0xF0`/`0xF8`;
  - accepts all passwords (or enforces them; the passwords are known);
- **optionally**, the `0x20` UART.

Pre-load either:
- **blank chips**: the game provisions itself. You type any 9-digit serial in the `diag init` screen, then `ProgramAbyss` writes the key with version 3.0 and the default country; or
- **pre-built images**: a small Python generator implementing `dBetty`/`dChris` (this needs FreeBSD 3.x `random()` and the matching LUT, see risks).

A missing Abyss is also acceptable (free play only), so a **Dolphin-only** device is the minimum viable step.

**B. Patch the binaries (fallback)**
- In `menu`, NOP the ID/FPGA checks and force `dDana`/`dEve` to return 0 with a fixed serial.
- `coinmgr`/`io`/`dl` need **nothing for the ISA path**. Their `/dev/mem`/`/dev/dolphin0` maps read `0xFF` with no board, and read 0xFF means "DIP 8 off" and "no switches pressed". The one cost is that `coinmgr` drops from 215 Hz to its 0.6 s sleep timeout.
- `diag`/`mgl` only display values.
- Every patch would be a reproducible `analysis/pN/sh/apply-*.py` with SHA-256 values. This route still leaves coin, TEST and DIP hardware non-functional.

**C. Video: required either way, and the hardest part**
1. **Best fidelity:** add a Rage IIC personality to 86Box's Mach64 GT (Rage II+) emulation. That means:
   - PCI ID `1002:4756`;
   - verifying `SCALE_3D_CNTL` scaled/alpha blits, `TEX_CNTL` and `GUI_TRAJ_CNTL`;
   - CRTC_INT_CNTL **VLINE** interrupts via PCI INTA.

   The exact register sequences are in `t/video/r2c/r2cinit.c` and `r2cblit.c`.
2. **Port-address problem:** the kernel hard-codes **0xD800** (Rage I/O) and the kernel plus `sound` hard-code **0xEF00** (ES1371). Ways around it, in order of preference:
   - pick an 86Box machine/BIOS whose PCI allocator yields exactly these values;
   - have the 86Box devices default or lock those BARs;
   - binary-patch the immediate operands in `/kernel` (`rag_read`/`rag_intr`: `mov edx,0xd818`; `est_*`: `0xef0c/04/2a/38/3e`) and in `/t/sound/sound`.

   The original board was very likely a 440BX-class Award BIOS board that produced those addresses.
3. **Alternative:** compile `dl.r128` from the ALPHA10 sources for the Rage 128, which 86Box emulates, using the ALPHA10 kernel with its `rot` driver. However, neither image contains a compiler, so this needs a FreeBSD 3.2 build VM. The OEM 2.03 game binaries would have to be checked for ABI compatibility with a 3.0x `dl`.

**D. Other emulator settings**
- Use a P6-class CPU with 64 MB+ RAM.
- Attach the MicroTouch on COM1 (which must answer the `Z/PN81/OI/R/FT/SE1/FN03/MS` handshake, or `io` hangs and the menu shows `ABORT (IO)`).
- Use the ES1371 at IRQ ≠ 5.
- Keep the 0xD0000–0xDFFFF region free of option ROMs and shadow RAM, and reserve IRQ 5 for ISA in BIOS setup.

---

## 7. Risks, blind spots and unknowns

| Item | Why it matters | Owner phase |
|---|---|---|
| 2.03 vs 3.0x differences in `dolphin.o`/`GetMasterPalEntry` (an `OLD_BUGGY` LUT exists) | Pre-built Abyss images must match the reading build. Self-provisioning sidesteps this | P2 |
| `secfail` in the 2.03 `dl.r2c` | Possible silent corruption if it is set by something absent from the 3.0x source | P2 (disassemble 2.03 `dl.r2c`) |
| 86Box Rage II+ 3D-scaler + VLINE IRQ completeness | `dl` blocks forever on `read(/dev/rag0)` without VLINE | P3 |
| BIOS PCI BAR placement (0xD800 / 0xEF00) | Hard-coded in kernel + `sound` | P3 |
| Dolphin FPGA "unlock" (`TestBoard`, "actually unlocks the FPGA") | Real HW may gate switches/UART until fuses are read; emulation can ignore it | P1 |
| `0x74` bit1 toggled per frame | Could be a hardware watchdog on real boards; harmless in emulation | P1 |
| `/rw/aa/aa.dat` (audits/adjustments, has a consistency check) | Stores serial, country, LOCKFREEPLAY and dolphintype. A country mismatch triggers a factory restore | P1 |
| Core dumps in `/rw/crash` | No security data found in them (only release-date strings) | done |
| MPN credentials in `/rw/mpn/config` (OEM) | Live-looking server/user/password. **Redacted here; do not publish** | — |

Blind-spot checklist status:
- **Dead vs live code:** dolphin.o is in 4 binaries, and the 2.03 strings confirm the live gate in `menu`. Call-site cadence has not yet been proven in 2.03 by disassembly.
- **Runs once vs every boot:** `CheckHardwareOK` runs on every `menu` start, and `menu` is restarted after every diag exit.
- **Runtime revalidation:** none seen.
- **Conditionally dispatched code:** ISA vs PCI paths.
- **Network/removable code:** the upgrade scan of wd1–3, wfd0 and acd0 at every boot.
- **Packing/anti-debug:** none.
- **Time/counter bombs:** none in the security path. `ADJ_NUMPOWERON` is only a counter.

---

## 8. Tooling produced

| Script | Purpose |
|---|---|
| `scripts/p0-disklabel.py` | Parses the FreeBSD disklabel from sector 1 |
| `scripts/ufs1.py` | Read-only UFS1 reader (`info`, `list`, `extract`) |
| `scripts/elfsym.py` | ELF32 symbols, vaddr→offset, capstone disassembly |
| `scripts/p0-kconf.py` | Decodes FreeBSD 3.x `isa_devtab_*` and `pcidevice_set` from a kernel |
| `scripts/strs.py` | `strings` replacement (no binutils on this host) |

---

## 9. Recommended next phases (detail in `Docs/00-plan.md`)
1. ~~**P1, Dolphin device spec**~~ **Done, see `Docs/01-dolphin.md`.** A C board/chip model passes the *original* `dolphin.c` (0 failures). `scripts/p1-mkchips.py` generates key images byte-identical to Midway's own programming code. Phase 1 corrected two items: the board interrupt is acked by userland (it must be edge-pulsed on IRQ 5), and 0x62 bit6 is the Calibrate switch.
2. ~~**P2, 2.03 binary confirmation**~~ **Done, see `Docs/02-oem-binaries.md`.** 2.03 links `dolphin.o.good`, which is instruction-identical to the source except for ISA-only `dout`/`din`. The menu gate is the same. 2.03 programs keys as v1.0, and its only version gate (`/t/system/mgl`) is never executed. `secfail` is inert, and no date bombs were found.
3. **P3, 86Box platform: done (first pass), see `Docs/03-platform.md`.** The OEM kernel boots in 86Box on an ABIT BF6 (Pentium II 350), driven by an automation build of the user's 86Box-Next2.
   - **Ports:** none of the 16 BIOSes that booted puts the Rage at 0xD800 or the ES1371 at 0xEF00.
   - **Video:** the OEM `rag` driver accepts only `1002:4756` and `1002:4742`, so on 86Box's Rage II+ (`4755`) `dl` cannot start, and `menu`'s Dolphin check is never reached.
   - **Corrections:** `rag_read` has a 2.86 s timeout (it doesn't wait forever), and the extra Rage Pro IDs are ALPHA10-only.
   - **P3b, done:** with a Rage IIC identity, pinned I/O BARs and an ES137x unaligned-word bug fix (branch `touchmaster` of the 86Box fork), the **unmodified** OEM image boots to `menu`'s "Dolphin I/O card not found!" screen. Next: P4.
   - The original P3 plan was: P6 machine, ES1371, MicroTouch; find a BIOS giving 0xD800/0xEF00 or patch the constants; boot to "Dolphin I/O card not found!". ~~"find a BIOS"~~ is ruled out, and ~~the milestone without video~~ is impossible (reclassified in P3).
4. ~~**P4, Dolphin in 86Box**~~ **Done, see `Docs/04-dolphin-device.md`.** The `dolphin_io` ISA board (Phase 1 model, unchanged) gets the unmodified 2.03 image through the security gate:
   - **blank chips:** the game programs them itself, and Midway's original code accepts the images;
   - **pre-built Canada key:** the machine boots straight to the menus, keeping the operator settings.
   - **TouchMaster II is keyless in 86Box.**
5. ~~**P5, Rage IIC video**~~ **Done, see `Docs/05-video.md`.** 86Box already emulates the GT-B scaler. Sprites were missing only because its 3D side read the horizontal scissor as 13 bits, so `dl`'s `SC_RIGHT = 0x1FFF` became −1. With 14 bits, as in 86Box's 2D engine, the menus and games render like Midway's own screen dumps. **P5b:** the scaler now applies `ALPHA_START` fades and `TEX_AMASK` masking, and the card runs a **genuine Rage IIC PCI BIOS** (ATI 113-61801-101, from the user's dumps) instead of a patched Rage II+ ROM.

6. ~~**P6, chip documents**~~ **Done (side session), see `Docs/06-chip-info.md`.** ATI's register guides confirm the scaler alpha-mask rule. FIFO_STAT and the scaler increment width were fixed on branch `touchmaster-chipinfo` (not merged).
7. ~~**P7, coins and sound**~~ **Done, see `Docs/07-coins-sound.md`.**
   - **Coins:** a paid game was played with coins through the board's electronic coin inputs, and the credit was deducted.
   - **Sound:** it plays, and is now at the correct level after fixing 86Box's AC'97 gain steps (2 dB → 1.5 dB).
8. ~~**P8, ALPHA10 (3.0x)**~~ **Done, see `Docs/08-alpha10.md`.** The 3.0x image runs on the same emulation once the Rage IIC has its real **8 MB** (3.0x caches images above 4 MB). It self-provisions an AV 3.0 key, which the original code accepts, and reaches its menus and attract loop.
