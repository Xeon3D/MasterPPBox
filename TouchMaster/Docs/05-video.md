# 05: Rage IIC video fidelity (Phase 5)

**Question:** After P4, the game ran but most sprites and labels were missing. Is the 86Box Mach64 GT-B front-end scaler (which `dl.r2c` uses for every scaled or alpha-blended image) missing, or broken?

**Answer: it exists and is complete enough. One wrong field width clipped every scaled pixel.**
- **The bug:** 86Box's 3D engine and scaler read the horizontal scissor (`SC_LEFT_RIGHT`) as 13-bit signed. `dl` sets it to `0x1FFF3FFF` ("no clipping"), and as 13 bits `SC_RIGHT = 0x1FFF` is −1, so every scaled pixel was dropped.
- **Already known:** 86Box's 2D engine had already been corrected to 14 bits for the GT-B, with a comment describing this exact failure. The 3D side was not.
- **The fix:** 14 bits in the three places in `vid_ati_mach64_3d.c` (scaler, trapezoid setup, GUI_STAT scissor flags).
- **Result:** with it, the menus, sprites, fonts and game demos render like Midway's own screen dumps.

---

## 1. What `dl.r2c` asks of the chip

The register inventory was taken from `t/video/r2c/r2cblit.c` and `r2cinit.c` (ALPHA10; 2.03's `dl.r2c` is the same family).

- **2D GUI engine:**
  - registers: `DST_*`, `SRC_*`, `DP_*`, `CLR_CMP_*`, `PAT_*`, `SC_*`, `GUI_TRAJ_CNTL`, `FIFO_STAT`, `GUI_STAT`;
  - used for unscaled, opaque 1555 images (`DP_SRC = 0x300`, `SCALE_3D_CNTL = 0`), and therefore most backgrounds.
- **Front-end scaler** (`DP_SRC = 0x500`, `SCALE_3D_FCN = 1`): used for everything scaled, alpha-blended or not 1555.
  - Source: a staging buffer the CPU fills (`SCALE_OFF` 0x12C000 / 0x258000, double-buffered).
  - Destination: one of two 640×480×16 frame pages (`DST_OFF_PITCH` 0x14000000 / 0x14012C00).
  - Draws are bottom-up (`DST_CNTL = 1`, Y from the last line).
  - `SCALE_3D_CNTL` values seen (decoded with 86Box's bit names):

  | Value | Use | Meaning |
  |---|---|---|
  | `402c0840` | ARGB4444 (`DL_4444` = type 15) and 8888 sprites: buttons, icons, game art | scale, alpha blend SrcAlpha / 1−SrcAlpha, `TEX_MAP_AEN`; `ALPHA_START = 0xFF` |
  | `50ac0840` | 1555 images with `DL_FLAGS_ALPHAOVERRIDE` (fades, large panels) | as above plus `TEX_AMASK_AEN`; `ALPHA_START` = fade level (0x55, 0x82, …) |
  | `50000040` | 1555 glyphs (fonts) | scale, no blend, `TEX_AMASK_AEN` + `TEX_MAP_AEN` (alpha-bit mask) |
- **Plus:** CRTC/PLL/DSP set-up and `CRTC_INT_CNTL` VLINE (P3b; works).

All of Midway's scaler register offsets (`SCALE_OFF` 0x1C0 … `ALPHA_START` 0x3F8, `TEX_CNTL` 0x374, `ALPHA_TST_CNTL` 0x150) match those of 86Box's GT-B (`vid_ati_mach64_3d.c`, "3D Rage II+ 3D engine and front-end scaler").

## 2. How the bug was found (evidence in `analysis/p5/raw/`)

1. **Visual:** frames recorded every 3 s with the automation `record` command (`seq-sheet.png`).
   - Backgrounds, the logo and text were fine; every category button and all game-demo art was missing.
   - Reference: Midway's own screen dumps in ALPHA10 (`t/video/scrdmp_000{0,1,2,8}.tga`, converted with `scripts/p5-tga2png.py`, in `analysis/p5/ref/`). **Note:** dl writes these dumps top row first without setting the TGA origin bit.
2. **Trace:** a *temporary*, environment-gated `pclog` in the scaler start, with a histogram of each source's alpha (`p5a-86box.log`, `p5b-86box.log`; 3000 draws). It showed:
   - **every scaler start is accepted** (0 rejects) and has valid formats, sizes, staging data and destinations;
   - **the source alpha is sensible** (buttons mostly A = 0xF), so this isn't a format or alpha problem;
   - **every draw has `sc=1fff3fff/3fff7fff`**. The scaler's own clip test (`x > sc_right` with a 13-bit sign extension) therefore rejects every pixel. The backgrounds that did appear came from the 2D path, which uses 14 bits.
3. **Fix and re-test** (`seq2-sheet.png`, `p5d-sheet.png`): category buttons, the game list, the Word Search demo, high-score tables, the operator's own ad, the Playboy screen and dice-game demos all render. The trace was then removed. The committed change is only the field width.

## 3. The change (branch `touchmaster`, `src/video/vid_ati_mach64_3d.c`)

- `#define SC_X_BITS 14`, with a comment pointing at the 2D engine's identical reasoning.
- It is used for `SC_LEFT` and `SC_RIGHT` in:
  - `mach64_3d_dst_init` (trapezoids and lines);
  - `mach64_scaler_draw`;
  - the GUI_STAT scissor flags.
- 12 lines changed in total. The vertical scissors stay 15 bits, as before.
- **Build:** exe SHA256 `bb7f510d…01ef`. **Commit:** `548b3eb19` on `touchmaster` (local, not pushed).

**Who else this affects:** any GT-B guest that opens the scissor with `SC_RIGHT = 1FFFh` (ATI's own `DP_SET_GUI_ENGINE` does, per the 2D comment). It is a general emulator fix, not TouchMaster-specific.

## 4. Remaining video gaps (not fixed; owners)

| Item | Evidence | Status |
|---|---|---|
| ~~`ALPHA_START` as a constant/fade alpha in the scaler~~ | `50ac0840` draws carry fade levels in `ALPHA_START` | **Fixed in P5b (§6)** |
| ~~`TEX_AMASK_AEN` in the scaler (alpha-bit masking)~~ | `50000040` glyphs, `50ac0840` images | **Fixed in P5b (§6)** |
| `ALPHA_TST_CNTL`, `TEX_CNTL` | written as 0 and 0x00800000 | no visible effect |
| Exact filter and dither of the IIC | scaled sprites use the 86Box 2-tap filter | cosmetic |

## 5. Reproduce

```
sh scripts/p3-build86box.sh /f/Claude/86Box-Next2-touchmaster analysis/p3/build86tm     # MSYS2 UCRT64
python -I scripts/p3-boot.py analysis/p3/build86tm/src/86Box-Next2.exe analysis/p3/vm p5d --secs 120 --every 15
python -I scripts/p3-auto.py analysis/p3/vm 7777 "record start 3000 <dir>" "step 60000" "record stop"
python -I scripts/p5-contact.py <sheet.png> 5 3 <dir>/*.png
python -I scripts/p5-tga2png.py analysis/fs/ALPHA10/root/t/video/scrdmp_0002.tga out.png
```

## 6. P5b: scaler fades and masking, and the real Rage IIC BIOS

### 6.1 Alpha and mask in the scaler (`vid_ati_mach64_3d.c`, `mach64_scaler_draw`)

The rule is derived from Midway's three `SCALE_3D_CNTL` values (§1). It reuses the texel rule already in 86Box's 3D path (`mach64_3d_texture_alpha`):

| Bits set | Alpha used |
|---|---|
| no `TEX_MAP_AEN` | the interpolated alpha (`ALPHA_START` + X/Y increments) |
| `TEX_MAP_AEN` | the source pixel's own alpha |
| `TEX_MAP_AEN` + `TEX_AMASK_AEN` | the source alpha bit is a mask: 0 drops the pixel, 1 takes the interpolated alpha |

The mask is taken from the nearest source pixel, not the filtered one.

This gives what dl expects:
- **`402c0840`:** 4444/8888 sprites keep their own alpha (unchanged behaviour).
- **`50ac0840`:** 1555 images fade by `ALPHA_START`, and their transparent pixels vanish.
- **`50000040`:** 1555 glyphs and sprites are cut out.

**Verified** (`analysis/p5/raw/seq3-sheet.png`, `seq3b-sheet.png`; 2 fps over 40 s):
- the Playboy screen dims to black, and the category menu fades in with intermediate frames (they were hard cuts before);
- the Solitaire demo zooms in and out;
- the rotating 1555 bunny is cleanly masked.

**Caveat:** the semantics are inferred from 86Box's own texel rule and from Midway's register usage (it sets `ALPHA_START = 0xFF` exactly where the texel alpha should rule and a fade level where the mask applies). They have not been checked against a hardware capture.

### 6.2 Real Rage IIC PCI BIOS (user-supplied dumps, `BIOS DUMPS/`)

| Dump | PCIR | ATI P/N, date, version | Use |
|---|---|---|---|
| `rage2c-pci-61801-101-at27c512r.zip` → `RAGE2C_PCI_61801_101_AT27C512R.bin` | `1002:4756` "MACH64GVPCIMTSDU" | 113-61801-101, 2000-01-12, BK3.11a/3.097 | **default** (closest to the TM II's build year) |
| `rageiic-38816-100-at27c512r.BIN` | `1002:4756` "MACH64GVPCIMTHPU" | 113-38816-100, 1998-08-21, BK3.10.1/3.095 | selectable |
| `rage2c-agp-52805-101`, `rageiic-49301-100`, `rageiic-agp.VBI`, `gainward-rageii.bin` | `1002:475A` (Rage IIC AGP) | — | not used (wrong bus/ID for TM II) |

- **Images:** 32 KB each, at the bottom of a 27C512 dump whose upper half is FF. The checksums are 00.
- **Installed:** copied unchanged into the ROM set as `86box/roms/video/mach64/rage2c_pci_113-61801-101.bin` and `…113-38816-100.bin` (SHA256 in `analysis/p5/bios/rom-sha256.txt`). Only new files; nothing in the ROM set was changed.
- **Device:** `mach64_rage2c` now has a "BIOS Revision" (CONFIG_BIOS) selection and loads the chosen image (32 KB at C0000h, its own `mach64rage2c.nvr`). **The in-memory PCIR patch of ARS2D is removed.**
- **Verified** (`p5f`): POST and text mode, then `rag0: <Rage IIC PCI PQFP>` at I/O 0xD800, then menus and game demos (`analysis/p5/raw/p5f-sheet.png`).
- **Observation:** during this work the VM's `86box.cfg` CPU became Pentium II 300 MHz (×4.5); the edit was not made by these scripts. It boots and runs the same.

**Build:** exe SHA256 `df11cc9f…bf61`. **Commit:** `e27685183` on `touchmaster` (local, not pushed).
