# 08: The ALPHA10 (3.0x) image under the same emulation (Phase 8)

**Question:** Does the second disk, the ALPHA10 3.0x development build with its newer kernel, `dl` and `diag`, run on the emulation built for 2.03? Whatever breaks shows emulation gaps that 2.03 happened not to hit.

**Answer: yes, after one discovery. The TouchMaster's Rage IIC had 8 MB.**
- 3.0x keeps its glyph and image cache above 4 MB. With the default 4 MB its text and keypad digits came out as noise.
- With 8 MB everything renders, and the image self-provisions blank chips through its own factory flow to a valid **AV 3.0** key. Midway's original code accepts it.
- It reaches its game menu in coin play ("Insert Coins") and runs its attract loop.
- 2.03 runs the same with 8 MB. The Rage IIC device now defaults to 8 MB.

---

## 1. Setup

| Item | Value |
|---|---|
| Disk | `HDD Images/TOUCHMASTERALPHA10/TOUCHMASTERALPHA10.img` → `analysis/p8/vm/tm-alpha10.img` (first 16 841 664 sectors, the same label as OEM). SHA256 `ff0aaa01…4443b` MATCH; tail 1.38 GB all zero (`analysis/p8/raw/mkdisk-alpha10.txt`) |
| VM | `analysis/p8/vm/86box.cfg`: as the OEM VM (BF6, Rage IIC with D800h pinned, ES1371 with EF00h, Dolphin board, MicroTouch COM1), plus `memory = 8`. **No** `dolphin_*.nvr`, so the chips start blank |
| Build | `analysis/p3/build86tm` (branch `touchmaster`), final clean exe SHA256 `f9996c99…9b32` |

## 2. What 3.0x does differently at boot (dmesg `analysis/p3/raw/dmesg-a1.txt`)

- **Drivers:** the kernel adds `iet` and `rot` (Rage 128). `ep0` (ISA NIC at 0x300) is not found, which is harmless.
- **`rag0`:** "Rage IIC PCI PQFP … **iobase: d800**". 3.0x reads the I/O base from PCI config, so it would work without pinning. Its `est` still hard-codes EF00h.
- **`dolphin0`:** attaches at D0000h, IRQ 5, as in 2.03.

## 3. The 4 MB finding

**Symptom (`analysis/p3/shots/a1-060s.png`):** on the factory "Enter Serial Number" keypad:
- the digits were green noise;
- the title read "aster Infinity".

**Evidence:**
- **Scaler trace:** only 150 draws, all 1555 panels. So 3.0x draws text differently from 2.03.
- **2D blit trace:** `mach64_start_fill`, temporary and environment-gated, now removed (`analysis/p8/raw/a3-86box.log`, `a4-serial-trace.txt`). 3.0x draws glyphs and images with colour-keyed 2D blits from a **linear** source (`SRC_CNTL = 4`; `r2cblit.c` line 639; `CLR_CMP 01000005`, key 0).
- **Glyph sources:** they sit in two regions, around offset 0x38xxxx and around **0x41F9C0–0x4C3900**, the second **above 4 MB**. With 4 MB of VRAM those reads wrap to the bottom of memory.
- **VRAM dump:** the glyphs under 4 MB are intact.

**Conclusions:**
- The real TouchMaster's Rage IIC had **8 MB** (Rage IIC boards came with 2, 4 or 8 MB).
- 2.03 stays under 4 MB, which is why P3–P7 never saw this.

**Fix:**
- `memory = 8` in both VMs.
- The `mach64_rage2c` default is now 8 MB, committed on `touchmaster` as `92ed542d7`.

**With 8 MB (`a6-075s.png`):** red keypad digits and the full title, identical in style to 2.03's keypad.

## 4. Factory flow on blank chips (3.0x `diag init`, all through the automation socket)

| Step | 3.0x behaviour | Notes |
|---|---|---|
| Enter Serial Number | **must start with 6 or 9**; a 9-digit entry X… becomes "X00…" (11 digits), anything else flashes "Invalid Serial Number" (`diag.c` 7910ff) | `300100123` was rejected; **`600922889` → 60000922889** (the field machine's MPN serial 922889) |
| Enter Country Code | 2 digits (2.03 had no such screen) | **29 = USA (DBV Installed)**, as this machine's own `/rw/menu/menu.ini` says (`video/config.h`) |
| Confirm | "The Serial Number can never be changed…" → CORRECT | |
| Set Date & Time | slider design (2.03: arrows) | OK |
| U9 and key written | `dolphin_u9.nvr`, `dolphin_abyss.nvr` | `ProgramAbyss` writes **AV 3.0** |
| "Personalizing the TouchMaster…" | factory restore (`ProgramAbyss` always jumps to it) | |
| Menu | "Make a Selection", English/Español, **"Insert Coins"** | coin play: a valid key |

**Independent check:** the original `dolphin.c` (P1 harness) on the written images (`analysis/p8/keys/`, SHA256 `c816d7c9…f8e9` / `1b980660…ac4a`):
`OK: coin play allowed (serial 60000922889, country 29, AV 3.0)` (`verify-alpha10.txt`). This matches P2's finding that 3.0x programs keys as 3.0.

The keypad tool `scripts/p8-keypad.py` types digits on this keypad.

## 5. Rendering check

60 s of attract (`analysis/p8/raw/a6-attract.png`):
- the category menu with fades;
- high-score tables (Vector, Box Swap, Times Square);
- glyphs throughout;
- no artefacts.

**Final clean build (`final-sheet.png`):**
- ALPHA10 (a7) boots to its menu and attract.
- OEM 2.03 (o9) boots to its menu ("$.25=½CR…", credits kept), also at 8 MB (`o8-sheet.png`).

## 5b. A paid 3.0x game

Shots: `analysis/p8/raw/a8-*.png`.
1. **Bill:** one bill on the DBV line (`ioboard pulse 2`) gives **Credits: 4**: a $1 bill under "USA (DBV Installed)". This machine takes money on the DBV line; the OEM machine uses the electronic coin inputs.
2. **Choosing the game:** Action → **Vector** (preview with Midway's own "WORK IN PROGRESS" overlay) → 1 player.
3. **Help screen:** "How to play VECTOR". The vector lines (wire polyhedron, arrows) and text all render.
4. **Gameplay:** it matches Midway's own Vector screen dump (`analysis/p5/ref/scrdmp_0008.png`): the HUD frame, level banner, side counters, Auto-Off button, the control pad, crosshair, stickmen and the ship.
5. **Controls:** a touch-drag on the pad flies the ship across the playfield, and the pad draws the green direction vector. Touch control works in 3.0x games.

## 6. Tooling fix found on the way

The boot script now waits until no `86Box-Next2.exe` is running before it starts one.

The failure it prevents: a closing 86Box still held the disk image, so the next instance couldn't open it. That instance dropped the `[Hard disks]` section from the VM config on exit, and the following boot ended in "DISK BOOT FAILURE". The section was restored.

## 7. Not covered

- Playing a 3.0x game for credits, and the 3.0x-only features (MPN tournaments, the PCI Dolphin variant `/dev/dolpci0`, the Rage 128 `dl.r128`, which has no binary on the disk).
- The 3.0x "Make a Selection" panel has no frame box, where 2.03's does. It is probably a layout change in 3.0x; there is no 3.0x menu reference dump to confirm it.
