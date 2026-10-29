# 04: Dolphin I/O board in 86Box (Phase 4)

**Question:** Does an emulated Dolphin ISA board, built from the Phase 1 model, get the unmodified OEM 2.03 image through its security gate, both by the game's own self-provisioning and with pre-built keys?

**Answer: yes, both ways. TouchMaster II 2.03 is keyless in 86Box.**
- **Blank chips:** the game runs Midway's factory flow, programs both chips itself, and goes to attract mode. Midway's own `dDana`/`dEve` accept the images it wrote (coin play allowed).
- **Pre-built Canada key** (`p1-mkchips.py --serial 100922889 --country 24 --version 1.0`, from Phase 2): the machine boots straight to the language and game-select menus. It skips the factory screens and doesn't reset the operator settings, and it never writes the chips.
- **Graphics are incomplete:** some sprites and labels are missing (3D scaler: Phase 5).

---

## 1. The device (branch `touchmaster`, 86Box fork)

**Board:** "Midway Dolphin I/O Board (TouchMaster II)" (`dolphin_io`). It is one of the fork's arcade I/O boards: *Settings > Other peripherals > I/O board*, or in `86box.cfg`, `[Other peripherals] io_board = dolphin_io`.

| File | What |
|---|---|
| `src/device/at88sc153.c`, `include/86box/at88sc153.h` | the Phase 1 chip model, **unchanged** apart from its header and include path. It is the code that passed Midway's own `dolphin.c` harness (0 failures) |
| `src/device/dolphin_io.c`, `include/86box/dolphin_io.h` | board glue (detailed below) |
| `device/io_board.c`, `io_board.h`, `device/CMakeLists.txt` | registration (`IO_BOARD_DOLPHIN`) |
| `qt/qt_ioboard_controls.cpp`, `qt_settingsotherperipherals.cpp` | I/O Board menu and toolbar: Coin 1–3, TEST, Calibrate; settings description |

What `dolphin_io.c` provides:
- **Memory window:** 64 KB at 0xD0000, mapped as `MEM_MAPPING_EXTERNAL`. Registers as in `Docs/01-dolphin.md` §1: ID 0x0102, bit-bang port 0x58, DIP 0x60, switches 0x62/0x64, outputs 0x66, control 0x74, timer 0x76, and a stub UART.
- **IRQ 5:** a 215 Hz board tick gives IRQ 5 an edge (`picintc` then `picint`) while control bit 10 is set. Clearing bit 10 (`coinmgr`'s acknowledgement) lowers the line. A 16-bit write to 0x74 is applied as a single update.
- **Switch presses:** they last 150 ms, counted in board ticks, so they use emulated time and automated runs are deterministic.
- **Chips:** `nvr/dolphin_u9.nvr` and `nvr/dolphin_abyss.nvr` in the same format as `p1-mkchips.py` output (256 bytes + 1 fuse byte).
  - Missing file: the chip starts blank, as shipped by Atmel (fab `AE 60`, transport code `D5 FE 7E`).
  - Saving: whenever the game changes a chip, at the next tick, and again at close.
- **Config:**
  - `abyss`: key fitted, default on. Off means free play only (`dEve` −2).
  - `dip`: default 0xFF. **Bit 7 = 0 is Emergency Restore, which wipes `/rw`** (surface K). The default keeps it off.

**Commit:** `7e1e15e1e` on `touchmaster` (local, not pushed).

**Build:** `scripts/p3-build86box.sh /f/Claude/86Box-Next2-touchmaster analysis/p3/build86tm`, giving exe SHA256 `47911222…e0af` (clean, no warnings from the new files).

## 2. Run A: blank chips (self-provisioning)

Setup: fresh working disk (SHA as in `analysis/p3/raw/mkdisk-oem.txt`), and no `dolphin_*.nvr`.

Run: `scripts/p3-boot.py … p4a`; shots `analysis/p3/shots/p4a-*.png`.

1. The kernel attaches `dolphin0` at 0xD0000, IRQ 5 (as before; it never checks for the board).
2. `menu`, `CheckHardwareOK()`: ID word OK, FPGA rev 2. `dDana` returns −1 (blank), so it runs **`diag init`**: the "Enter Serial Number" keypad (t+60 s).
3. A serial was entered on the touchscreen keypad, then OK.
   - **Caveat:** some of these touches came from the 86Box window during the scripted run (the user's). The final serial was 60068100468.
4. "Set Date & Time": OK touched through the automation `tablet` command.
5. **`dBetty` programs U9**, and `dolphin_u9.nvr` appears.
6. `dEve` returns −1 (blank key), so **`ProgramAbyss`** writes the key: `dolphin_abyss.nvr`, version 1.0, default country 22.
7. "Personalizing the TouchMaster for your country": this is `diag factoryrestore`, because the key's country 22 ≠ the disk's `aa.dat` (Canada 24).
8. Boot info screen: **"Version 2.03c NJ · Serial 60068100468 · Country 22 Switzerland · Hardware Manufacture Date Oct 29 2026"**. Then the attract loop (Pyramid 13, Triple Elevens).

**Independent check:**
- Images: `analysis/p4/keys/dolphin_{u9,abyss}.nvr`, SHA256 `0115f2b9…e001` / `85320fa6…34d9`.
- The Phase 1 harness, running Midway's **original** `dolphin.c` (`analysis/p1/build/harness verify`), reports:
  `OK: coin play allowed (serial 60068100468, country 22, AV 1.0)` (`analysis/p4/keys/verify-game-written.txt`).
- This confirms the P2 finding that 2.03's `ProgramAbyss` writes AV 1.0. It also confirms that the 86Box device, running the guest's real bit-bang code, produces chips the original code accepts.

## 3. Run B: pre-built OEM key (Canada)

Setup: `analysis/p2/keys/oem_{u9,abyss}.nvr` (SHA256 `1348a9f0…41ef` / `d228979c…133a`) copied into `nvr/` as `dolphin_*.nvr`, on a fresh disk.

Run: `p3-boot.py … p4b`; shots `analysis/p3/shots/p4b-*.png`.

- No serial screen and **no factory restore**: the key's country matches `aa.dat`, so the field machine's operator settings and audits are kept.
- t+45 s: the language menu ("Make a Selection": English / Deutsch / Italiano).
- t+120 s: the game-select menu (Triple Elevens, 1P/2P buttons).
- **The chip images are byte-identical after the boot.** `dDana`/`dEve` only read them; password verifies leave PAC = FF.

## 4. What is still missing (owners)

| Item | Status | Owner |
|---|---|---|
| Many sprites and labels missing (menu buttons, game boards) | consistent with `dl`'s scaled and alpha blits going through the Mach64 **3D scaler**, which is not emulated (no `SCALE_3D_CNTL`) | **P5** |
| Coin and TEST/Calibrate behaviour in a running game | menu controls exist; coin crediting not yet exercised | P4b / P6 |
| Coin-play vs free-play display | the harness says coin play is allowed; not checked on screen | P4b |
| UART (bill validators, EZ keypads) | stub only (LSR 0x60) | later, only if needed |
| Sound output | `est0` opens; audio not listened to or recorded (the automation `audio start` can do it) | P5/P6 |
| ISA DMA / other board features | none used by the software (P1 audit) | — |

## 5. Reproduce

```
# build (see Docs/03 §10 for the worktree)
sh scripts/p3-build86box.sh /f/Claude/86Box-Next2-touchmaster analysis/p3/build86tm     # in MSYS2 UCRT64
# fresh disk
python -I scripts/p3-mkdisk.py "HDD Images/OEM/TOUCHMASTEROEM.bin" analysis/p3/vm/tm-oem.img 16841664
# run A: no nvr/dolphin_*.nvr; run B: copy analysis/p2/keys/oem_*.nvr to analysis/p3/vm/nvr/dolphin_*.nvr
python -I scripts/p3-boot.py analysis/p3/build86tm/src/86Box-Next2.exe analysis/p3/vm <tag> --secs 120 --every 15
# check chips with the original code
wsl -e analysis/p1/build/harness verify <u9.nvr> <abyss.nvr>
```
