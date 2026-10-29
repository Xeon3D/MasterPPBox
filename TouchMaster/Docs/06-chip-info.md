# Phase 6 — ATI chip documents vs. 86Box's Mach64 (GT-B / Rage IIC)

**Question:** Do ATI's own documents (in `Chip Info/`) confirm or correct the Mach64 GT-B front-end scaler as
86Box emulates it? In particular, the Phase 5b alpha rule was inferred from Midway's register usage (`Docs/05-video.md` §6.1).
Where a document clearly disagrees with the code, fix it on a new branch.

**Answer:** The alpha rule is **confirmed where the 1996 register guide states it**:
- the `TEX_AMASK_AEN` / `TEX_AMASK_MODE` mask semantics (verbatim);
- `TEX_AMASK_AEN` being ignored without `TEX_MAP_AEN`;
- the mask being the alpha LSB.

The `ALPHA_START` default (no `TEX_MAP_AEN` → interpolated alpha) is **supported by the guide but not stated in one sentence**.
The guide also says that `TEX_MAP_AEN` without `TEX_AMASK_AEN` is **not supported for scale sources** on the 3D RAGE (GT). Midway uses exactly that (`402c0840`) on the IIC, so the GT-B evidently goes beyond the 1996 guide there.

Two clear discrepancies were fixed on branch `touchmaster-chipinfo` of `F:/Claude/86Box-Next2` (worktree `F:/Claude/86Box-Next2-chipinfo`):
- **FIFO_STAT on the 3D RAGE:** the code set one bit per entry from the first; the guide says one bit per entry past the first 16.
- **Scaler increments:** the code gave the integer part 5 bits; the Rage Pro guide gives 8.

Everything else checked either matches or is a documented conflict between ATI's own books (left as is, listed below).

## 1. Sources

All page numbers are **printed** page numbers, with the PDF page in brackets.

| Short name | File | Covers |
|---|---|---|
| RRG-G02700 | `RRG-G02700_mach64_Register_Reference_Guide_ATI-264VT_and_3D_RAGE_1996.pdf` (Rev. 0.10) | VT and 3D RAGE (GT) registers; ch. 6 = scaler and 3D |
| RAGE PRO PG | `prg-215r3-00-10_rage_pro_and_derivatives_programmers_guide_mar00.pdf` | Rage Pro and derivatives; §8.9 front-end scaler "3D RAGE II/II+/IIC and 3D RAGE PRO" |
| RRG-S00700 | `RRG-S00700-05_mach64_Register_Reference_Guide_1999410.pdf` | GX/CX/CT register guide (1993/94) |
| SDK | `mach64sdk.zip` → `m64sdkr3.zip/CHAP8/FESCALER/FESCALER.C` | ATI's front-end scaler sample (Rage Pro) |

The two `prg-215r3…` PDFs are byte-identical (SHA256 `f26cd438…6902`).

Text extracts with page markers:
- `analysis/p6/raw/pdftext/*.pg` (`pdftotext -layout`, then `scripts/p6-pgnum.py`);
- the SDK is unpacked under `analysis/p6/raw/sdk/`.

The 1996 guide's bit diagrams are shaded drawings that do not survive text extraction. Bit positions below come from the field letter order, which matches 86Box's defines, not from the diagrams.

## 2. Front-end scaler and alpha path (what Midway's `dl.r2c` drives)

| Item | Document | Code (`vid_ati_mach64_3d.c`) | Verdict |
|---|---|---|---|
| `SCALE_3D_CNTL` fields, a..x = bits 0..31 (`SCALE_PIX_EXPAND` … `SRC_3D_SEL`) | RRG-G02700 6-4..6-6 [178–180] | defines at the top of the file, same order | **match** |
| `SCALE_3D_FCN` 0 none / 1 scale / 2 texture / 3 shade | 6-4 | `FCN_*` | match |
| `TEX_AMASK_AEN`: "use only the LSB of the alpha value … only used when `TEX_MAP_AEN` is set" | 6-6 [180] | `mach64_3d_texture_alpha`: mask = `a & 1`, only under `TEX_MAP_AEN` | **confirmed**. The 1555/4444/8888 unpackers keep the alpha LSB (1555 → 00/FF, 4444 ×17, 8888 raw) |
| `TEX_AMASK_MODE` 0: "mask 0 → texel not drawn; mask 1 → drawn using the alpha interpolator value" | 6-6 [180] | mode 0: drop / `alpha` | **confirmed** |
| `TEX_AMASK_MODE` 1: "mask 0 → alpha interpolator value; mask 1 → alpha 0xFF" | 6-6 [180] | `mask ? 255 : alpha` | **confirmed** |
| `TEX_MAP_AEN` 0: "No alpha in the texture map" | 6-6 [180] | interpolated alpha (`ALPHA_START` + increments) | **supported, not verbatim**: see §2.1 |
| `TEX_MAP_AEN` on a scale source: "supported only in conjunction with `TEX_AMASK_AEN`" | 6-6 [180] | full source alpha | **document says unsupported** on the GT; Midway's `402c0840` (4444/8888, blend As/1−As) relies on it on the IIC → kept (§2.2) |
| `ALPHA_BLND_SRC/DST` 0..5 = 0, 1, other colour, 1−other, As, 1−As | 6-5 [179] | `mach64_3d_blend_factor` | match |
| `ALPHA_FOG_EN` 1 blend / 2 fog via `DP_FRGD_CLR` | 6-4 [178] | scaler: blend only; fog only in the 3D path | open (§4) |
| `TEX_LIGHT_FCN` in scaling | 6-5: defined for texture mapping; 6-1 [175]: the colour interpolators are reused as scaler accumulators | not applied in the scaler | **consistent**: Midway's `50ac0840` sets `TEX_LIGHT_FCN` 2, which can have no colour to light with |
| `NEAREST_TEX_VIS` during scaling: "selects whether chroma keying is done on all 4 source pixels" | 6-4 [178] | clear = any of 4, set = nearest | match (polarity as for texels) |
| `DP_SCALE_PIX_WIDTH` 2,3,4,6,7,8,11,14,15 (15 = aRGB 4444) | 4-93 [121] | `mach64_3d_bytes_per_pixel`, unpackers | match |
| Scaler conversion table (RGB 12 → RGB 8,15,32 only) | 4-94 [122] | destination 2,3,4,6,7,8,15 accepted | code is more permissive; harmless |
| `SCALE_Y_OFF` bits 2:0 must be 0; `SCALE_Y_PITCH` in pixels, qword aligned | 6-1, 6-2 [175–176] | `& ~7`, pitch in pixels | match |
| `SCALE_VACC` "incremented during the scale … must be reloaded for every scale" | 6-3 [177] | VACC advanced by the lines drawn | match |
| Accumulators "8.12 unsigned"; HACC/VACC "sign, 12 frac, 4 int" | 6-1, 6-3, 6-7 | 21-bit signed (alias S.8.12) | match / superset |
| **`SCALE_X_INC`/`Y_INC`/`XUV_INC` integer width** | RRG-G02700 6-2 [176]: "12 bits fractional, 4 bits unsigned integer". RAGE PRO PG 8-14 [150]: "12 bit fractional, 8 bits unsigned integer". Aliases `RED/GREEN/BLUE_X_INC` are S.8.12 (6-12, 6-13) | `& 0x001ffff0` = **5** integer bits (matches neither) | **FIXED** → `0x00fffff0` (8 bits, the later book, which names the II/II+/IIC, and the alias format) |
| Filter: "2-tap 5-bit coefficient … high 5 fractional bits" | RRG-G02700 6-1 [175] vs RAGE PRO PG 8-13 [149] "2 tap, 4 bit co-efficient" | 4-bit (comment says why) | **ATI books disagree**; left at 4 |
| Scissors `SC_LEFT`/`SC_RIGHT` | RRG-G02700 4-82, 4-83 [110–111] and RRG-S00700 [99,101]: "signed 13-bit" | 14 bits on GT-B (P5; the 2D engine cites RRG-G03300 5-40 for the LT Pro) | **document (VT/GT) says 13**; Midway's `SC_RIGHT = 1FFFh` would then be −1 and clip everything, yet the IIC draws → GT-B is 14; kept |
| `CLR_CMP_SRC` 0 dst / 1 2D source / 2 texel-scaler source; key compared "against the expanded (24 bit) source", CI8 on the low 8 bits | 4-98, 4-100 [126, 128] | as stated (`mach64_scaler_source_key_inhibits`) | match |
| `CLR_CMP_FCN` 0 false / 1 true / 4 ≠ / 5 =; true keeps the destination | 4-100 [128] | `mach64_3d_color_compare_inhibits` | match |
| `DP_SRC` source 5 = "Scaler/3D data (3D RAGE)" | 4-97 [125] | scaler starts on `DP_FRGD_SRC` 5 with `SRC_3D_SEL` 0 | match |
| `DP_WRITE_MSK` must be FFFFFFFF and `DP_MIX` must not use the destination while alpha blending | 4-90, 4-95 [118, 123] | the code honours both anyway | programming rule only |

### 2.1 Why the `ALPHA_START` default is supported

- `TEX_MAP_AEN` = 0 means the source has **no** alpha (6-6).
- The only other alpha the pipeline has is the alpha interpolator: `ALPHA_START`, "Initial value of alpha", S.8.12 (6-14 [188]). `TEX_AMASK_MODE` names it as the alpha a drawn masked texel gets.
- The alias table (6-1 [175], 6-12..6-13) reuses the RED/GREEN/BLUE interpolators as scaler accumulators, but **not** ALPHA. The alpha interpolator is therefore still free in scaling mode, and `TEX_MAP_AEN` explicitly covers "scale sources".

Gap: no sentence says "without `TEX_MAP_AEN`, As is the interpolator". The rule is the consistent reading, not a quotation.

### 2.2 Midway vs. the 1996 guide

| Midway value | Fields | Guide |
|---|---|---|
| `402c0840` (4444, 8888) | FCN 1, `ALPHA_FOG_EN` 1, SRC As / DST 1−As, `TEX_MAP_AEN` | `TEX_MAP_AEN` alone on a scale source is "not supported" (GT, 1996) |
| `50ac0840` (1555 + `ALPHA_START` fade) | as above + `TEX_AMASK_AEN`, `TEX_LIGHT_FCN` 2 | supported; mask mode 0 → interpolator alpha. **Confirmed** |
| `50000040` (1555 glyphs) | FCN 1, `TEX_MAP_AEN` + `TEX_AMASK_AEN`, no blend | supported; mask 0 drops the pixel. **Confirmed** |

Midway sets `ALPHA_START = FF0000h` exactly where it expects the texel's own alpha. That only makes sense if the chip uses the texel alpha there, so the IIC (GT-B) supports `TEX_MAP_AEN` alone on scale sources. The emulation does this, and it cannot be checked against a document.

Midway also writes `ALPHA_START`/`ALPHA_X_INC`/`ALPHA_Y_INC` as **magnitude plus a sign at bit 28** (`r2cblit.c` 658–660). The guide says only "S.8.12", and the code reads two's complement in bits 24:4. A negative increment from Midway would read as positive. The guide does not settle the encoding. → open (§4).

## 3. Engine status, interrupts

| Item | Document | Code | Verdict |
|---|---|---|---|
| **`FIFO_STAT` on the 3D RAGE** | 4-101 [129]: "indicates the number of full command FIFO entries in the top half … if there are 23 full entries, then bits 6:0 will be set. The number of free entries … is available in the GUI_STAT register." | `vid_ati_mach64_3d.c`, GT-B read: a bit per used entry from the first, as on the GX | **FIXED** → bits = used − 16 (clamped to 16 bits). Polling as the docs and Midway do (`(FIFO_STAT & 0xffff) > (0x8000 >> n)`) still guarantees n free entries, since FIFO_STAT bit (16−n) is clear only while ≥ 32 entries are free |
| `GUI_STAT` `FIFO_CNT` "≤ 32 in the current version"; FIFO "expanded to 48" | 4-106 [134] | 48-entry count (the Windows 95 HAL waits for > 32) | conflicting statements in the guide; code follows software; kept |
| `GUI_STAT` `GUI_ACTIVE` on the 3D RAGE = GUI or 3D busy, FIFO not empty, or context load | 4-106 [134] | busy if modelled FIFO used, blitter or 3D busy | match |
| `CRTC_INT_CNTL` a..g = VBLANK, VBLANK_INT_EN, VBLANK_INT/AK, VLINE_INT_EN, VLINE_INT/AK, VLINE_SYNC (odd line), FRAME (odd frame) | 4-26 [54] | bits 0..6 the same, write-1-to-ack | match |

## 4. Not fixed: unclear or not stated by a document

1. **Scaler filter precision:** 5-bit (1996) vs 4-bit (2000) coefficients. The code uses 4.
2. **Fog (`ALPHA_FOG_EN` 2) in scaling mode:** the field is in `SCALE_3D_CNTL`, but no text says the scaler fogs. Not added.
3. **`SIGNED_DST_CLAMP` (bit 15):** "assume the destination is signed and clamp" (6-5), for MPEG motion compensation. Not implemented; the clamp ranges are not given.
4. **YUV 422 scaler source alpha:** the code always gives YUV sources alpha FFh. By the §2.1 reading, a source without alpha should take the interpolator when blending. Same strength of evidence as §2.1, so not changed; a candidate if a YUV + blend user shows up.
5. **`ALPHA_*` encoding:** Midway's sign-at-bit-28 magnitude form vs two's complement (§2.2).
6. **`TEX_MAP_AEN` alone on a scale source:** unsupported per the 1996 GT guide, used by Midway on the IIC; emulated as full source alpha.
7. **`DP_MIX` 17h (`(DST+SRC)/2`):** the extracted table seems to mark it "Reserved in 3D RAGE" (4-95 [123]), but the column extraction is garbled. Not acted on.

## 5. Scope not covered

- **2D engine and CRTC/VGA against PRG888GX0, VGA-S00700, the BIOS kits and the 1999 RRG-S00700:** only spot checks (scissors, `DP_PIX_WIDTH`, `CLR_CMP`, `DP_SRC`, `CRTC_INT_CNTL`). The existing 86Box code already cites RRG pages throughout, and no clear deviation turned up.
- **mach32 (REG688000-15, `vid_ati_mach8.c`):** not reviewed.

## 6. Changes (branch `touchmaster-chipinfo`, commit eab533273, local, not pushed)

| File | Change | Citation |
|---|---|---|
| `src/video/vid_ati_mach64_3d.c` `mach64_3d_read` | GT-B `FIFO_STAT` = bits for entries past 16 | RRG-G02700 4-101 |
| `src/video/vid_ati_mach64_3d.c` `mach64_scaler_draw` | `SCALE_X_INC`/`SCALE_Y_INC`/`SCALE_XUV_INC` masked to 8.12 (`0x00fffff0`) | RAGE PRO PG 8-14; RRG-G02700 6-12 |

> **Merged** into `touchmaster` as `be5573921` (2026-10-29). OEM 2.03 and ALPHA10 3.0x both boot to their menus on the merged build (`analysis/p8/raw/merge-sheet.png`).

## 7. Regression test

Setup:
- **Build:** `scripts/p3-build86box.sh` → `analysis/p6/build86chip/src/86Box-Next2.exe`; SHA256 `db292ab4…99e4bd` (log `analysis/p6/raw/build86chip.log`).
- **VM:** a copy in `analysis/p6/vm`:
  - cfg and nvr copied from `analysis/p3/vm`, plus `gdbstub_port = 12346` in `[General]`, because the main VM held 12345 at the time;
  - disk from `p3-mkdisk.py`, output SHA256 `a7fb42f8…0865` MATCH (`analysis/p6/raw/mkdisk-p6.txt`).
- **Run:** `p3-boot.py … p6chip --port 7790 --secs 120 --every 15 --quit` (`analysis/p6/raw/boot-p6chip.txt`); shots in `analysis/p3/shots/p6chip-*.png`.

Comparison:
- Contact sheet, p5f vs p6chip in pairs by time: `analysis/p6/shots/p6-vs-p5f.png` (`p5-contact.py … 4 2`).
- Byte diff: `scripts/p6-pngdiff.py`.

| t | vs p5f (known good) | Note |
|---|---|---|
| 15, 30 s | identical | boot text, copyright |
| 45 s | differs | attract demo shows a different game (Artifact vs Times Square), both rendered correctly: sprites, glyphs, score text |
| 60, 75 s | differs (1–6 % of bytes) | Playboy attract screen, same images, animation phase |
| 90, 105, 120 s | **identical** | category menu ("Make a Selection"), Free Play |

The menu frames are byte-identical to p5f, which matched Midway's own dumps (`analysis/p5/ref/`) in P5. The attract differences are timing: the attract cycle depends on emulated timing, which the `FIFO_STAT` change can shift. They are not rendering differences. **No regression** in menus, sprites, fades or glyphs.
