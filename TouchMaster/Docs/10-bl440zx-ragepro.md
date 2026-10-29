# Phase 10 — Intel BL440ZX + ATI 3D Rage Pro Turbo AGP

**Outcome:** the TouchMaster II now runs on its real hardware platform in 86Box: an **Intel BL440ZX** board with its **on-board ATI Rage Pro Turbo AGP (1002:4742, 8 MB SDRAM)**, a Celeron 366 and the on-board ES1373. Both images reach their menus:

- `diag`'s Motherboard Test passes every line: Celeron 366 MHz, 62 MB, **Video Chip Model 4742 PASS** (it failed on the Rage IIC, Docs/09 §4.2), **8MB SDRAM PASS**.
- The unmodified Intel BIOS assigns the ES1373 to **EF00h** and the Rage Pro to **D800h**. These are exactly the two I/O bases Midway's kernel hard-codes, and none of the 16 BIOSes tried in P3 produced them.

So the BL440ZX is, by strong evidence, the TouchMaster II motherboard, and on it the `fixed_io` pinning is unnecessary.

## 1. Sources (user-supplied, `Info/`)

| File | What it is | Use |
|---|---|---|
| `Motherboard Info/bl440zx-72609201-*.pdf` | BL440ZX Technical Product Spec (TPS) | Platform facts: Socket 370 Celeron 300A/333/366 at 66 MHz; 82443ZX + PIIX4E; FDC37M807; ES1373 + CS4297; 82559 LAN; **"ATI RAGE PRO TURBO 2X AGP … 8 MB SDRAM"** (§1.7); PCI map (Table 30: video on bus 1 dev 0); **ISA segment on the NLX card edge** (Table 16) |
| `Motherboard Info/bl-npc-ds-*.pdf` | BL440ZX Net PC datasheet | Same chip set; confirms "ATI Rage Pro Turbo 2X, 8 MB SDRAM" |
| `Motherboard Info/blap05bi.zip` | BIOS P05 (`4B4LZ0XA.86A.0012.P05`, 11/10/99) | Byte-identical to 86Box's existing `roms/machines/bl440zx/P05-0012.*` |
| `Motherboard Info/bl440zx-04.zip` | BIOS P04 + flash tools | Not used (86Box loads P05) |
| `Rage Pro/*.bin, *.dmp, 109-49800-11.zip` | Four Rage Pro VBIOS dumps (all PCIR 1002:4742) | Card BIOS choices, §3 |
| `Rage Pro/ati-rage-pro-…pdf` | = `Chip Info/prg-215r3-00-10…` (byte-identical) | PLL/DSP appendices J/K; no Rage Pro register reference |

The system BIOS modules are compressed, so the embedded video BIOS can't be pulled out statically. §4 recovers it at run time instead.

## 2. What already existed, what was added (branch `touchmaster` of the fork, commit `343675359`, local, not pushed)

86Box already had the machine, `[i440ZX] Intel BL440ZX`. Its entry noted *"internal video: ATI Rage Pro Turbo AGP (not yet implemented)"* and declared the board ISA-less.

| Change | Files | Basis |
|---|---|---|
| **`MACH64_FLAG_RAGEPRO`**: the GT-B core (2D engine, 3D engine, front-end scaler, PLL with alternate post-dividers) under PCI ID **4742h**, `CONFIG_CHIP_ID` 5C004742h, `CFG_MEM_TYPE` 4 (SDRAM; 5 for the SGRAM BIOS) | `vid_ati_mach64.[ch]` | `dl.r2c`'s `-DRAGEPROAGP` path differs from `-DRAGE2C` only in mode-set constants (DSP_CONFIG/ON_OFF, PLL 11, MEM_CNTL), not in drawing (`r2cinit.c` 117–188) |
| AGP device: `pci_add_card(PCI_ADD_AGP)`, status bits 4/5 (capability list, 66 MHz), **AGP capability at 50h** (rev 1.0; status 1x+2x+SBA; command register kept with a write mask), AGP video timings | `vid_ati_mach64.c` | TPS §1.7 ("2X … sideband"); AGP spec 1.0 |
| **Card** `mach64_ragepro` "ATI 3D Rage Pro AGP" (AGP list): 4 BIOSes, 2/4/8 MB (default 8), render threads, `fixed_io` | `vid_ati_mach64.c`, `vid_table.c`, `video.h` | §3 |
| **On-board** `mach64_ragepro_onboard`: no ROM BAR (the system BIOS supplies it), 8 MB | same | TPS §1.7 |
| BL440ZX: `vid_device` = on-board Rage Pro, `MACHINE_VIDEO`, device added in init | `machine_table.c`, `m_at_socket370.c` | TPS Table 30 |
| BL440ZX: bus flags `MACHINE_PS2_NOISA` → **`MACHINE_PS2_AGP`** (ISA allowed) | `machine_table.c` | TPS Table 16: the NLX edge carries ISA (SD/SA/IRQ), so a riser can have ISA slots; the Dolphin board is ISA |

**Not emulated:** Rage Pro-only 3D features (triangle setup engine, its extra texture/fog registers) and the PM capability. TouchMaster draws with the 2D engine and the front-end scaler only (same code for both chips), so none of these is exercised. **Unverified values:** revision 5Ch (no document; nothing we have checks it) and AGP RQ depth 8.

## 3. ROMs (`scripts/p10-roms.py`, hashes in `analysis/p10/raw/roms-sha256.txt`)

| Output (`86box/roms/video/mach64/`) | Source | ID |
|---|---|---|
| `ragepro_agp_turbo_3.091.bin` (**default**) | `rage-pro-turbo-at27c512r-dip28.bin` lower 32K | SDRAM BIOS 3.091, 2000/08/14, BK3.9.4, `MACH64GBPCIMTSDU` |
| `ragepro_agp_113-49801-101_2000.bin` | `109-49800-11.zip:109-49800-11.ROM` | 113-49801-101, 2000/05/04 |
| `ragepro_agp_113-49801-101_1998.bin` | `d003vid.dmp` | 113-49801-101, 1998/05/25 (44 bytes differ from 2000: dates/tables) |
| `ragepro_agp_113-40212-103.bin` | `rage2pr-bga-40212-103-mx27c512.bin` lower 32K | 113-40212-103, 1998/09/29, **SGRAM** (`…SGU`) |

Each is checked: 55AA, 32K, zero checksum, PCIR 1002:4742. No revision checks were found in their code.

## 4. Runs (exe `analysis/p3/build86tm/src/86Box-Next2.exe` SHA256 `49b25b72…c8b0a0`)

| VM | Result |
|---|---|
| `analysis/p10/vm-card` (BF6 + Rage Pro **card**, Turbo BIOS) | Award POST lists `1 0 0 1002 4742 0300 Display Controller IRQ 11`; the shadowed BIOS differs from the image by 19 bytes (self-patching) |
| `analysis/p10/vm-bl` (BL440ZX, no disk) | Intel POST on screen through the on-board chip. **C0000 holds the BL440ZX's own embedded Rage Pro BIOS**, decompressed by the system BIOS: "ATI MACH64 SDRAM BIOS 3.086", 1998/05/10, BK3.9.2, `MACH64GBPCIMTSDU`, PCIR 1002:4742. It is none of the four card dumps. Saved as `analysis/p10/raw/bl-c0000.bin` (shadow image, SHA256 `4032a974…4439`) |
| `analysis/p10/vm` (BL440ZX, Celeron 366, 64 MB, on-board video/sound, OEM disk `p3-mkdisk.py` → `analysis/p10/raw/mkdisk-oem.txt`, Dolphin + chips from P3, **no `fixed_io`**) | dmesg (`analysis/p3/raw/dmesg-p10-bl.txt`): `est0 … map[0] base 0000ef00 … irq 9`; `rag0: <Rage Pro Turbo AGP> rev 0x5c int a irq 11 on pci1.0.0`, `map[1] base 0000d800`; `dolphin0 at irq 5 maddr 0xd0000`. Attract, diag Hardware Test, Pyramid 13 played (by the user too). Coin on electronic A → "Credits: 2"; coin sound −36 dBFS peak |
| `analysis/p10/vm-a10` (same hardware, ALPHA10 disk of P8 + its chips) | `rag0: <Rage Pro Turbo AGP 2X BGA> … iobase: d800`, est0 at EF00, menus ("Make a Selection") |

User's screenshot, OEM `diag` Motherboard Test: CPU Celeron PASS, 366.6676 MHz PASS, 62 MB PASS, Video Chip Model 4742 PASS, Video RAM 8MB SDRAM PASS.

## 5. Corrections to earlier phases

- **P3 "0/16 BIOSes give 0xD800/0xEF00" → solved by the right board.** The BL440ZX BIOS assigns both natively. `fixed_io` stays useful only for other boards.
- **Surface D/E:** the hardware is the Rage Pro Turbo AGP on a BL440ZX. The Rage IIC + BF6 setup (P3–P9) remains a working substitute.
- **Coin sound level** is not directly comparable with P7's −44.8 dBFS (a different codec, CS4297A on-board, and a different moment). Sound is audible and correct in kind; there is no claim on absolute level.

## 6. Ready-to-run rigs (`Rigs/`)

There is one rig per release, both on the real platform: BL440ZX, Celeron 366, 64 MB, on-board Rage Pro Turbo AGP and ES1373, Dolphin I/O board, MicroTouch touchscreen on COM1. Neither pins any I/O (the BL440ZX BIOS assigns D800h/EF00h itself).

| Path | Content |
|---|---|
| `Rigs/86Box-Next2.exe` | Rig build of `touchmaster` 343675359 **without AUTOMATION/GDBSTUB**, so it starts running (`p3-build86box.sh <src> analysis/p10/build86rig rig`), SHA256 `a8326d38…a2f4` |
| `Rigs/roms/` | Copy of `86box/roms` (737 MB) |
| `Rigs/Run TouchMaster 2.03 (OEM).cmd`, `… 3.0x (ALPHA10).cmd` | `86Box-Next2.exe -P <rig> -R roms` |
| `Rigs/TouchMaster-2.03-OEM/` | `tm-oem.img`: the OEM image trimmed to its label (16841664 sectors, `p3-mkdisk.py`; SHA256 a7fb42f8… = the original's first 8.62 GB); chips from `p1-mkchips.py --serial 100922889 --country 24 --version 1.0` |
| `Rigs/TouchMaster-3.0x-ALPHA10/` | `tm-alpha10.img`, same trim (SHA256 ff0aaa01…); chips = the 3.0x factory-programmed pair of P8 (serial 60000922889, country 29, AV 3.0) |
| `*/nvr/bl440zx.nvr/.bin` | Initialised CMOS: fresh CMOS halts the Intel POST at "CMOS Battery Low – Press F1 to Run SETUP", so Setup → F9 defaults → F10 save was run once and the result copied to both |
| `*/nvr/mtouch_A30100.nvr` | Touchscreen controller state from P3 |

Provenance (kept out of the deploy tree, per the guardrail): `analysis/p10/raw/rig-mkdisk-{oem,alpha10}.txt`, `rig-nvr-sha256.txt`.

**Verified:** both rigs boot unattended to their menus (OEM: Playboy attract and "Make a Selection" in Free Play; ALPHA10: "Make a Selection", Free Play). Free Play is each image's own field operator setting (P7). Both were tested on these images, which were then replaced with fresh trims, so they are untouched field images. The rig exe was started from the OEM launcher and runs without being held.

**Note:** the automation boot script `p3-boot.py` presses F1 when it doesn't see the loader. On the Intel BIOS, F1 enters Setup, so use `p10-post.py` (keys only when given) for BL440ZX VMs.
