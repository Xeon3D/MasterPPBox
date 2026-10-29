# 09: TouchMaster key generator in 86Box (Phase 9)

**Request:** a Tools menu entry that generates a serial number, lets you pick a country, and writes the chips on the I/O board.

**Done** on branch `touchmaster`, commits `c2525e241` (key generator) and `b5182b370` (ATR), local, not pushed:
- **Tools → TouchMaster Key Generator…** It is shown only while the Midway Dolphin board is fitted.
- **Same generator for scripts:** the automation command `ioboard keys <serial> <country> <major.minor>`.
- **The generator** is a C port of `scripts/p1-mkchips.py` (`src/device/dolphin_keygen.c`). It is byte-identical to the Python, which was itself proven against Midway's `dolphin.c`.

## 1. What it does

| Field | Behaviour |
|---|---|
| Fitted now | decodes the current U9 (`dolphin_keygen_read_u9`) and shows its serial and country, or "blank chips". The dialog pre-fills from it, so re-keying with the same country causes no factory restore |
| Serial number | digits, up to the chip's 14. **Generate** makes a factory-style serial: `600` + 8 random digits (11 digits; the form 3.0x's keypad produces from "6YYYYYYYY"). A hint warns about serials 3.0x's keypad could not have made (the game itself accepts them) |
| Country | the game's own list from `t/video/config.h`: 54 entries, all also present in the 2.03 binaries, sorted by name and shown as "Name (code)" |
| Key version | 3.0 (3.0x; 2.03 accepts it too) or 1.0 (what 2.03 writes) |
| Write Chips | queues both images. The board's next tick loads them into the live chips, as if freshly programmed, and saves `nvr/dolphin_u9.nvr` and `dolphin_abyss.nvr`. It then offers a hard reset, because the game reads the chips at start |

**Safety:**
- A pending write is also applied when the board closes, so a reset straight after Write keeps the new chips.
- The images reach the chips on the emulation thread, never from the UI thread.
- With "Abyss key fitted" off, the key image is still saved; it just isn't presented to the game.

## 2. Verification

1. **C vs Python** (`scripts/p9-kgcheck.py`; result `analysis/p9/kgcheck.txt`):
   - parameters: 6 serials (including 1 and 99999999999999) × 5 countries × 3 versions × 2 times × 3 seeds;
   - built both 32-bit and 64-bit;
   - **1080 comparisons, 0 mismatches.**
2. **U9 decoder** (`analysis/p9/readtest.c`): correct serial and country for the generated key, the P2 Python key, and both **game-written** keys (2.03 Switzerland, 3.0x USA). A blank chip reads as blank.
3. **End to end** (OEM 2.03 VM):
   - In the menu, `ioboard keys 60012345678 24 1.0` changed both `.nvr` files.
   - `reset hard` → the menu after 120 s, with no factory screens and the operator pricing intact (`analysis/p9/k1-after-reset.png`).
   - Midway's original code on the saved chips: **`OK: coin play allowed (serial 60012345678, country 24, AV 1.0)`** (`analysis/p9/keys/verify.txt`).
4. **The Qt dialog itself was not clicked through:** the automation socket drives the guest, not host windows. It calls the same `dolphin_io_write_keys()` / `dolphin_io_read_keys()` as the tested path, and it builds without warnings.

## 3. Files (86Box branch `touchmaster`)

| File | Change |
|---|---|
| `src/device/dolphin_keygen.c`, `include/86box/dolphin_keygen.h` | generator (FreeBSD `random()`, dBetty/dChris, the `GetMasterPalEntry` LUT), country table, U9 decoder |
| `src/device/dolphin_io.c`, `include/86box/dolphin_io.h` | `dolphin_io_write_keys()` / `dolphin_io_read_keys()`; queued apply on tick and close |
| `src/qt/qt_dolphin_keydialog.cpp/.hpp` | the dialog |
| `src/qt/qt_ioboard_controls.*`, `qt_mainwindow.cpp`, `src/qt/CMakeLists.txt` | Tools menu entry, shown with the board |
| `src/automation.c`, `doc/specifications/automation.md` | `ioboard keys` |
| `src/device/CMakeLists.txt` | build |

Build: `analysis/p3/build86tm`, exe SHA256 `122fbef4…e488f`.

## 4. Found while trying it: two `diag` hardware-test failures

### 4.1 Dolphin I/O Test: "U9 (AT88SC153) FAIL ffffffff", "Abyss FAIL ffffffff"

**What the test does** (`diag.c` 4864–4925, same in 2.03):
1. Pulses RST high, with **one clock while RST is high**.
2. Drops RST and reads 32 bits (`dreadbits`: bit sampled while SCL is high, assembled MSB-first).
3. Expects **3455AA85h**.

This is the chip's **Answer-To-Reset**. The model only reset itself and left SDA released, which reads as all ones.

**Fix:** the model now gives an ATR when the part is clocked during reset:
- the first bit is on SDA when RST falls, and each falling clock edge brings the next bit;
- bytes **2C AA 55 A1**, each LSB first. That is 3455AA85h as `diag` reads it; the byte values are derived from `diag`'s expected constant.

**Unchanged security path:** `ResetAtmel()` raises RST without clocking, which gives no answer, so the security path is untouched.

**Applied to both copies:** `src/device/at88sc153.c` (86Box) and `analysis/p1/src/at88sc153.c`.

**Checks** (`analysis/p9/atrtest.txt`):
- P1 harness on Midway's original `dolphin.c`: **SELFTEST OK (0 failures)**;
- new `analysis/p1/src/atrtest.c` (replays `diag`'s exact sequence through the ISA board model): U9 and Abyss both **3455AA85 PASS**; a plain reset followed by 32 reads gives FFFFFFFF;
- the generated key still verifies.

**Confirmed in the VM** (rebuilt exe SHA256 `83c46230…85dc`, OEM 2.03): Operator menu → Diagnostics → Hardware Test → Dolphin I/O Test now shows **U7 (FPGA) PASS, U1 (UART) PASS, U9 (AT88SC153) PASS, Abyss PASS** (the user's screenshot, 2026-10-29 09:38).

### 4.2 Motherboard Test: "Video Chip Model: 4756 FAIL" — a hardware finding, not an emulation fault

- **`diag` expects a Rage Pro:** it reads `CONFIG_CHIP_ID` and passes **only 4742h** (Rage Pro Turbo AGP), in **both** 2.03 (`cmp …, 0x4742` at 0x0806A24C) and 3.0x (0x0806E340).
- **So was `dl` built for it:** both shipped `dl.r2c` binaries were built for the Rage Pro. They contain the `-DRAGEPROAGP` path's `DSP_CONFIG` 004A07F1h and not the `-DRAGE2C` path's 00360A7Ch, and the 3.0x makefile has `-DRAGE2C` commented out.
- **The kernel accepts both chips:** `rag` takes 4756h (Rage IIC) and 4742h.

**Conclusion:** the production TouchMaster II used an **ATI 3D Rage Pro Turbo AGP (1002:4742), 8 MB**. "r2c" is only the historic name of Midway's driver directory.
- **Correction to P0/P3:** the Rage IIC was the earlier or alternative board, not the one this software was built for.
- **Why it still works:** the emulated Rage IIC (a GT-B) runs both builds correctly, because `dl` only uses features both chips have, so the game works.
- **What doesn't match:** `diag`'s chip-ID check, and any Rage Pro-only behaviour, which hasn't been observed.
