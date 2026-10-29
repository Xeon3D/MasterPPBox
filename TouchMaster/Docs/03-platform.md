# 03: 86Box platform bring-up (Phase 3)

**Question:** On which 86Box machine does the unmodified OEM 2.03 image boot, how far does it get, and how do we satisfy the PCI I/O addresses that the kernel and `sound` hard-code (Rage 0xD800, ES1371 0xEF00)?

> **Update, P3b (same day): milestone reached.** On branch `touchmaster` of the user's 86Box fork, the unmodified OEM image boots to `menu`'s own **"Dolphin I/O card not found!"** lock screen in about 60 s. See §10.

**Answer (short, first pass):**
- The OEM kernel **boots on a Pentium II (440BX) machine** in 86Box (ABIT BF6, Award 6.00PG) from a trimmed copy of the disk. It runs `/etc/rc`, and `dl mount` mounts `/rw`.
- **No emulated BIOS (20 tried) puts the Rage at 0xD800 and the ES1371 at 0xEF00.** The addresses therefore have to come from a patch: the guest (tool ready: 10 kernel + 77 `sound` sites) or 86Box (BAR pinning). See §6.
- **The "Dolphin I/O card not found" milestone is behind video, not behind I/O addresses.**
  - `menu` reaches its security check only after `dl` (display server), `io` (touch) and `sound` are up.
  - `dl` needs `/dev/rag0`, and the OEM `rag` driver accepts only **`1002:4756` (Rage IIC) or `1002:4742` (Rage Pro AGP)**. 86Box's Rage II+ is `4755`, so `rag` does not attach and `dl` dies in `initvideo()`.
  - A Rage IIC *identity* (Rage II+ with ID 4756) is the minimum 86Box change to get past this. 86Box's Mach64 already emulates the VLINE interrupt the driver uses; the 3D scaler (P5) is the rest.

---

## 1. Working media (`scripts/p3-mkdisk.py`)

The OEM dump is 20.0 GB, but its BSD label covers 16 841 664 sectors (8.62 GB = 16708 C × 16 H × 63 S). The script copies exactly that and verifies that the dropped tail is all zero.

| | SHA256 |
|---|---|
| `HDD Images/OEM/TOUCHMASTEROEM.bin` bytes [0, 8 622 931 968) | `a7fb42f8…0b0865` |
| `analysis/p3/vm/tm-oem.img` (working copy) | identical (MATCH); tail: 11.4 GB, 0 non-zero chunks |

Evidence: `analysis/p3/raw/mkdisk-oem.txt`.

**Note:** the working copy is *not* immutable. Booting it writes `/rw` (wd0b). Regenerate it with the script whenever a pristine state is needed.

## 2. Emulator: automation build of the user's 86Box-Next2 (`scripts/p3-build86box.sh`)

- **Source and build:** out-of-tree build of `F:/Claude/86Box-Next2` at HEAD `b93755bd2` (clean tree), into `analysis/p3/build86/`.
- **Options:** same as the user's `build-static`, plus `AUTOMATION=ON` and `GDBSTUB=ON`; `LATEST_VERSIONS` and `DISCORD` off.
- **Output:** exe SHA256 `334d568c…8946f` (build 222).
- **Source tree untouched:** `.build-number` was saved and restored (still 221), and `git status` is clean.

The automation socket (`doc/specifications/automation.md`) lets every boot below be scripted and repeatable:
- the machine is held between requests;
- text-screen waits, key input, screenshots and `memr` are all available.

The GDB stub starts with the CPU stopped; the scripts send one RSP `c` to release it.

Tools:
- `scripts/p3-auto.py`: client (`textdump`, `type …` helpers).
- `scripts/p3-msgbuf.py`: pulls the FreeBSD kernel message buffer (dmesg) out of guest RAM. It finds `struct msgbuf` by its magic 0x063062 at the top of RAM and unrolls the ring. This works even after `rc.local` mutes the console (`kern.consmute=1`).
- `scripts/p3-probe-bars.py`: per-machine probe (§5).

## 3. VM definition (`analysis/p3/vm/86box.cfg`)

| Item | Value | Why |
|---|---|---|
| Machine | `bf6`: ABIT AB-BF6, i440BX, Award 6.00PG, has ISA slots | P6 + ISA (for the Dolphin in P4) |
| CPU | Pentium II Deschutes 350 MHz (dynarec) | the OEM kernel is I686_CPU-only |
| RAM | 64 MB | as the period hardware; kernel reports 61 276 KB available |
| Video | `mach64_rage2p` (Rage II+, `4755`) | closest existing device; **does not attach to `rag`** (§4) |
| Sound | `es1371` (`1274:1371` rev 2) | `est0` attaches: "Ensoniq AudioPCI 1373", IRQ 10 |
| Touch | `microtouch_touchpen` on COM1 | `sio0` 16550A at 0x3F8 IRQ 4 = `/dev/cuaa0` |
| Disk | `tm-oem.img`, IDE 0:0, CHS 16708/16/63 | `wd0: 8223MB … 16708 cyls, 16 heads, 63 S/T` |

Run it:

```
analysis/p3/build86/src/86Box-Next2.exe -P analysis/p3/vm -R 86box/roms --automation tcp:7777 --automation-hold
```

On first start the BIOS needs F1 (fresh CMOS).

## 4. What the boot shows (BF6; dmesg `analysis/p3/raw/dmesg-bf6-v1.txt`)

1. Award POST lists PCI devices: PIIX4 IDE, USB, Rage II+ (IRQ 11), ES1371 (IRQ 10).
2. Boot chain: `boot1`/BTX loader, then `loader` 0.7 ("devel@kevin1.touchmaster, 23 Jul 1999"), then `/kernel` and `splash_bmp.ko`.
3. **The kernel boots on the Pentium II.** The I686-only kernel is fine on a P6 core.
4. PCI attach results:
   - **`rag`** prints "got probed" for every device. It **matches only `47561002`/`47421002`**, so Rage II+ `47551002` is rejected.
   - **`est0` attaches**, and its 4 KB DMA page is allocated.
   - **`dolphin0` attaches with no board present.** It reads "Status register 2: ffff" and attaches anyway at 0xD0000, IRQ 5. So the kernel never gates on the board; only userland does.
5. `/etc/rc` runs.
   - **Expected errors:** the errors about `/var/run` and `/tmp` are normal. Both are symlinks into `/rw`, which is `noauto` in `fstab` and mounted later by `dl mount`.
   - `rc.local` sets `kern.consmute=1`, so the console goes quiet. `dl mount` then fsck's and mounts `/rw`, spawns `syslogd` and calls `initvideo()`.
   - In `initvideo()`, `open("/dev/rag0")` fails ("rag0: started to open", then ENXIO, because the unit never attached). So the 8 MB `mmap` fails and `ResetRageEngine()` faults.
   - **Consequence:** `dl` never reaches the code that spawns `sound`, `io`, `coinmgr` and `midas`.

### Why the gate needs video (from `menu.cpp` main, ALPHA10; same order in 2.03)

`menu` reaches `CheckHardwareOK()` only after these, in order:
1. `/rw/aa/aa.dat` exists;
2. `/tmp/io/touch` exists (created by `io`, which itself draws through `dl` and needs the MicroTouch handshake);
3. `/tmp/sound/fifo.0` exists (created by `sound`);
4. `OSConnect()` to `dl`'s display list.

If any of these is missing, `menu` shows `ABORT (…)` *through `dl`* and aborts. The Phase 0 milestone "boot reaches *Dolphin I/O card not found!*" therefore **implies a working `dl`**.

## 5. Where BIOSes put the I/O BARs (`scripts/p3-probe-bars.py`)

**Method:** for each machine:
1. Same devices, same disk.
2. Press F1 at the BIOS prompt.
3. At the loader, `boot -sv` (verbose, single-user, so `/rw` is never mounted and nothing is written).
4. Read dmesg from RAM and record the `map[]` lines.

Full output: `analysis/p3/raw/probe-bars.txt`, per-machine `analysis/p3/probe/<m>/dmesg.txt`.

| Machine (86Box) | BIOS | Rage II+ I/O BAR | ES1371 I/O BAR |
|---|---|---|---|
| bf6, bx6, 686bx, ms6119, lx6, p6i440e2 | Award (bottom-up from 0xE000) | 0xE400 | 0xE800 |
| atc6310bxii | Award | 0xE000 | 0xE400 |
| p2bls, p3bf | ASUS Award (top-down) | 0xD000 | 0xB800 |
| in440ex | Award | 0xD000 | 0xD400 |
| kn97 | ASUS Award | 0xE000 | **0xD800** (wrong device) |
| ax6bc | AOpen Award | 0x9400 | 0x9800 |
| se440bx2, al440lx | Intel/Phoenix (bottom-up from 0x1000) | 0x1000 | 0x1400 |
| em440 | — | 0x1400 | 0x1080 |
| p6sba, s1846, vs440fx, ap440fx, bl440zx | AMI / Intel | not probed: on a fresh CMOS the scripted F1/space keys land in BIOS Setup | — |

**Result: 0 of 16 BIOSes give Rage = 0xD800 and ES1371 = 0xEF00.**
- **The allocators differ:** bottom-up from 0xE000 (Award), top-down below the PIIX4 IDE (ASUS), or bottom-up from 0x1000 (Intel). Within a machine the result is deterministic.
- **The real board is unknown.** Its BIOS produced Rage = 0xD800 and ES = 0xEF00. That pattern implies more PCI I/O consumers than 86Box has, or a different slot order. Finding a matching BIOS is not a practical route; the address must be made to match by a patch (§6).
- **Unprobed boards:** the 5 AMI/Intel boards are unlikely to differ in kind; adapt the key script if needed.

## 6. The fixed I/O addresses: options

Hard-coded uses in the OEM software (`scripts/p3-ioimm.py`, which checks every instruction immediate; all ELF files under `/t`, `/sbin`, `/bin` and `/usr/sbin` were scanned):

| File | Sites | Form |
|---|---|---|
| `/kernel` `rag_intr`, `rag_read` | 2 | `mov edx,0xD818` (CRTC_INT_CNTL: VLINE ack/enable) |
| `/kernel` `est_intr`, `est_open` | 8 | `mov edx,0xEF04/0C/21/2A/38/3E` |
| `/t/sound/sound` | 77 | `push 0xEFxx` (arguments to its in/out wrappers; `sounddef.h IOPORT 0xef00`) |
| everything else | 0 | — (`dl` uses MMIO through `/dev/rag0`; the `tulip` hits in the kernel are a different NIC driver) |

**Changed by 3.0x:** the ALPHA10 kernel's `rag` reads its I/O base with `pci_conf_read`. Midway fixed the Rage dependency after 2.03, but `est` and the new `rot` (Rage 128) still hard-code `0xEFxx` and `0xD818`.

Three ways forward. They are not exclusive. The address only has to agree between the device and the 87 sites.

| Option | What changes | Pros | Cons |
|---|---|---|---|
| **A. Guest patch** (`scripts/p3-patchio.py`, dry-run verified) | rewrites the 87 immediates in the *working copy* to the machine's BIOS addresses (BF6: 0xE400/0xE800) | no emulator change; deterministic; reversible (regenerate the copy) | modifies Midway binaries (`diag`'s file test would flag `sound`; informational only); tied to one machine's BIOS layout |
| **B. 86Box BAR pinning** | a per-device option in the user's 86Box fork (Mach64, AudioPCI): "fixed I/O base". The BAR still answers the BIOS's sizing probe, but keeps decoding and reporting 0xD800 / 0xEF00 | guest stays byte-pristine (preservation-grade); works on any machine | emulator source change; must make sure the BIOS didn't give another device that window (on BF6 nothing is near 0xD800/0xEF00) |
| C. Find the original motherboard | — | exact | unknown model; no dump; not needed |

**Recommendation: B.** P5 needs an 86Box change anyway (the Rage IIC identity `4756`), so pinning adds little cost and keeps the OEM image untouched. A remains the fallback, and it is a handy cross-check: if it is ever used, both must agree.

## 7. Corrections to earlier phases (guardrail 5)

| Earlier claim | Correction (P3 evidence) |
|---|---|
| P0 §4: "`rag` also accepts Rage Pro 4744/4749/4750/4751" | Only the **ALPHA10** kernel does. The **OEM** `rag_probe` accepts only `47421002` and `47561002` (`analysis/p3/raw/oem-kernel-rag.txt`). |
| P0 §4: "`rag_read()` … *no timeout*" | `rag_read` does `tsleep(…, "vsync", 0x11E)`, a **2.86 s timeout**, then returns EWOULDBLOCK. `dl` won't hang forever, but it runs at about 0.35 Hz without the VLINE IRQ. |
| P0 plan milestone "reaches *Dolphin I/O card not found!*" without video | Not reachable: `menu`'s check sits behind `dl`, `io` and `sound` (§4). |

## 8. New hazards found (for P4/P5)

- **`dl` wipes `/rw` on the emergency-restore DIP.** If a Dolphin is present (`dolphintype != NONE`) and `dolphin[0x60] & 0x80 == 0`, it runs `rm -rf /rw/{aa,var/log,crash,tmp,games,…}`. **The P4 device must read 0x60 bit 7 = 1 by default.** This was already in the P1 register map as "DIP bit 7 = emergency restore"; it is now confirmed destructive.
- **`dl mount` runs `newfs /dev/rwd0b` if `fsck -py /rw` fails**, which reformats the operator data. In emulation this means: never hard-kill the VM mid-write unless the working copy is disposable (it is, by design).
- `rag_open` programs a variable-range **MTRR** (8 MB write-combining over BAR0). 86Box's P6 core accepts MTRR writes, so this is not an issue.

## 9. Blind spots

| Item | Status | Owner |
|---|---|---|
| Actual real-HW motherboard/BIOS | unknown; irrelevant once B or A is applied | — |
| 5 AMI/Intel BIOSes not probed | key-script limitation | low |
| `sound`, `io`, `coinmgr`, `midas` behaviour | not observed: they are spawned only after `dl`'s `initvideo()` succeeds | P3b after Rage IIC identity |
| MicroTouch handshake | 86Box answers every command `io` sends (`Z`, `PN81`, `OI`, `R`, `FT`, `SE1`, `FN03`, `MS`; unknown ones get `<SOH>0<CR>`), so `checktsack` is satisfied. Not yet observed live | P3b |
| `dl.r2c` on emulated Mach64 GT: GUI engine and 3D scaler | not emulated: no `SCALE_3D_CNTL` in `vid_ati_mach64.c` | P5 |
| ISA window 0xD0000 and IRQ 5 | free on BF6: no option ROM there, and `dolphin0` claims IRQ 5 without conflict | P4 confirms |

## 10. P3b: Rage IIC identity, pinned I/O, and an ES1371 fix (branch `touchmaster`)

**Where the work is:**
- Branch: `touchmaster` in a worktree at `F:/Claude/86Box-Next2-touchmaster`, based on `b93755bd2`; committed as `c242204a1` (local only, not pushed).
- The `isp-server` submodule was initialised from the local clone.
- Build: `scripts/p3-build86box.sh /f/Claude/86Box-Next2-touchmaster analysis/p3/build86tm`, giving exe SHA256 `96e84357…f1cf`.

| Change | Files | Why |
|---|---|---|
| **Rage IIC device** `mach64_rage2c`, "ATI 3D Rage IIC". It is the GT-B (Rage II+) emulation with PCI ID `4756` and CONFIG_CHIP_ID `9a004756`. ARS2D's PCIR device ID is rewritten to 4756 in memory, with the checksum kept at 0 (there is no IIC ROM dump) | `vid_ati_mach64.[ch]`, `vid_table.c`, `video.h` | the OEM `rag` driver attaches only to 4756 or 4742 |
| **Fixed I/O base option** (`fixed_io`): on the Rage IIC, block I/O (BAR1), "D800h"; on the ES1371, BAR0, "EF00h". The BAR register keeps whatever was written, so sizing probes read back the true mask. Any *assigned* address decodes and reads back as the fixed base | `vid_ati_mach64.c`, `snd_audiopci.c` | hard-coded 0xD818 (kernel) and 0xEFxx (kernel and `sound`). The OS and BIOS see a consistent BAR with the right size (`size 8` and `size 6` in dmesg) |
| **ES137x unaligned word I/O** is now handled as the two bytes it covers (in and out) | `snd_audiopci.c` | **This is an emulator bug, not a TouchMaster hack.** `est_intr` acks DAC2 with `outw(0xEF21)`, toggling P2_INTR_EN. 86Box ignored it (`port & 0x3f` = 0x21 hits `default`), so INTR never cleared and the ISR spun forever: 100 % of CPU time in `est_intr` (EIP sampling, `scripts/p3-sample.py`) |

**VM** (`analysis/p3/vm/86box.cfg`): `gfxcard = mach64_rage2c` with `[ATI 3D Rage IIC] fixed_io = D800`, and `[Ensoniq AudioPCI (ES1371)] fixed_io = EF00`.

**Result** (fresh working copy, `scripts/p3-boot.py … tm3`; dmesg `analysis/p3/raw/dmesg-tm3.txt`; shots `analysis/p3/shots/tm3-*.png`):

1. `rag0: <Rage IIC PCI PQFP> rev 0x9a int a irq 11`, block I/O 0xD800. ES1371 at 0xEF00, `est0` attached.
2. `dl`: `rag0` opened, 8 MB MTRR added, VLINE interrupts arrive (`dstatus 00000038`). `dl` draws through the emulated Mach64 in 640×480.
3. `sound` opens `est0` (its version banner is the first thing `dl` draws); `io`, `coinmgr` and `midas` start.
4. **`menu` passes its four preconditions and shows "Dolphin I/O card not found!" (dark red, Midway font) by t+60 s.** This is exactly `CheckHardwareOK()` step 2. The board-ID word at 0xD0050 reads 0xFFFF on an empty ISA bus.
5. The guest is then idle (EIP sampling: mostly the kernel idle loop).

**What this proves:**
- The OEM image needs **no guest modification** to reach the protection gate.
- The remaining gates are Dolphin (P4) and video fidelity (P5: the 3D scaler is not yet exercised and was not verified on this screen).

**Corrections to §0 and §6:**
- ~~"menu's Dolphin check is unreachable until a Rage IIC identity"~~ That part is done.
- ~~Option A (guest patch)~~ is not needed. `scripts/p3-patchio.py` stays as an unused fallback.

**Open in P3b:**
- the branch is committed locally (`c242204a1`) but not pushed;
- the 3D scaler and VLINE timing fidelity are untested;
- the MicroTouch handshake was passed implicitly (`io` created `/tmp/io/touch`, otherwise `menu` would have shown `ABORT (IO)`), but not traced;
- no sound output was checked.
