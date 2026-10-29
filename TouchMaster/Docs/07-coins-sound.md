# 07: Coin play and sound (Phase 7)

**Question:** With the key accepted (P4) and the graphics correct (P5), does the machine take coins, charge for games and make sound the way the hardware did? What has to change in the emulation for that?

**Answer: yes, after three emulator changes. One of them is a general AC'97 fix.**
- **Coin play works end to end.** The operator switched Free Play off in `diag`, coins were dropped through the board's electronic coin inputs, a paid Pyramid 13 was started and played, and the credit was deducted (7 → 6). The score went into the high-score table.
- **"Free Play" was the operator's own setting**, not a key problem. The field machine was set to free play.
- **Sound works.** The ES1371's DAC2 plays the game's samples (coin drop, touch clicks, game sounds). It was about 10 dB too quiet because 86Box's AC'97 volume table stepped 2 dB instead of the standard 1.5 dB. That is fixed.

---

## 1. Free play vs. coin play (`menu.cpp`, `diag`)

- Free play is on when the three `aa.dat` adjustments `ADJ_FREEPLAY_C0..C2` hold the pattern 0, 1, 2.
- `menu` writes that pattern itself when the U9 chip has no serial or no Abyss key is fitted, and sets `ADJ_LOCKFREEPLAY`. A valid key clears only `ADJ_LOCKFREEPLAY` (`menu.cpp` 3340–3473), so the setting stays until changed in `diag`.
- The OEM disk's `aa.dat` had **Free Play = Yes** (Operator menu → Game/Coinage Setup).
- Coinage preset in force: **Canada, preset 1, "$.25 = ½ CR, $1 = 3 CR, $2 = 6 CR"**, max credits 30.

Driven entirely through the automation socket:
1. TEST (`ioboard pulse 4`) opens the operator Main Menu, which shows "Credits: 0".
2. Game/Coinage Setup: Free Play? set Yes → **No**.
3. Return, then Exit. The menu bar now reads "Insert Coins" and the pricing.

Shots: `analysis/p7/test-*.png`, `coinage.png`, `coin-canada.png`.

## 2. How `coinmgr` takes coins (and why the first coins vanished)

`coinmgr` samples the board on every IRQ 5 tick: 210 passes/s measured, from `0x74` bit 0, which it flips every 21 passes. It counts how many passes each input is held, and credits the coin on release only if the length fits:

| Input (register, bit) | 3.0x source (`coinmgr.c`) | 2.03 binary (`analysis/p7/oem-coinmgr-switches.txt`) |
|---|---|---|
| Coin 1 (62h b0) | 6–30 passes, then lockout 30 | 6–90 (`len-6 ≤ 0x54`), lockout 6 |
| Coin 2 (62h b1) | 6–90 | 6–90 |
| DBV (62h b2) | 2–90 | 2–90 (`len-2 ≤ 0x58`) |
| Electronic A–F (64h b1–b6) | 2–90 | 2–90 |

Two things were wrong or missing on the emulated side:
1. **Pulse length.** The board's switch press was 150 ms, about 32 passes, which is past the 3.0x coin-1 limit. Coin presses are now **80 ms (about 17 passes)**, inside every window in both versions. TEST and Calibrate stay at 150 ms.
2. **The electronic coin inputs** (64h bits 1–6, shown in `diag`'s Switch Test as "Electronic Coin Inputs CFE A–F") could not be pressed. **This machine's coins arrive there.** Measured one coin per input in the menu (`analysis/p7/map/strip.png`):

| Input | Worth (Canada preset 1) |
|---|---|
| mech 1, mech 2, DBV | nothing (0 units configured) |
| electronic A, B | ½ credit each ($0.25) |
| electronic C | 3 credits ($1) |
| electronic D | 6 credits ($2) |
| electronic E, F | nothing |

`coinmgr` does not sample the switches at all while `diag` is running (`if (diagpid) … else {read switches}`). Coins dropped in the operator menu are therefore ignored, as on the real machine.

Board-side check: `memr 0xd0062` reads FDh for the 80 ms press, then FFh.

## 3. Paid game

Shots: `analysis/p7/g*.png`, `bar*-sheet.png`.
1. Credits: 7 → Cards → Pyramid 13 (1 cr) → 1-player.
2. "Round 1", then the deal.
3. Touch a 12, then the deck's 1: the pair is removed and the score goes 0 → 500.
4. EXIT → "Quit the Game?" → exit game.
5. High-score entry (#5, 750) → OK.
6. Menu: **"Credits: 6"**, and the table shows the score as "Today".

## 4. Sound

**The chain** (the `sound` daemon writes, traced with a temporary environment-gated `audiopci_log`; trace since removed):
- AC'97 reset;
- PCM-out 0808h (0 dB), master 0000h, then **1414h** from the operator volume of 46;
- SRC RAM: unity volumes, 22050 Hz;
- DAC2 frame at 0x36C000 (`est0`'s 4 KB DMA page), `SERIAL_CONTROL` 48h (P2 16-bit mono), `INT_CTRL` DAC2_EN;
- DAC2 interrupts acknowledged through the unaligned word at 21h, about 72/s, after the P3 fix.

**Measured:**
- The guest's DAC2 buffer reaches full scale (32767) on a coin sound.
- The output peaked at only 57/32768 (−55 dBFS).
- An in-emulator probe showed the AC'97 master gain for 14h was **327/32767 = −40 dB**.

**The fix** (`snd_ac97_codec.c`):
- The AC'97 standard steps master volume and the 5-bit gains by **1.5 dB**: master 0 to −94.5 dB; PCM/CD/line +12 to −34.5 dB with 08h = 0 dB.
- 86Box's `codec_attn` table stepped **2 dB**, the AK4531's step: the ES1370's codec, whose own tables sit next to it in `snd_audiopci.c`.
- The table is regenerated as 32767·10^((n−63)·1.5/20). Index 63 = 0 dB as before, so callers are unchanged.
- **Result:** the same coin sound now peaks at 189 (−44.8 dBFS), exactly +10 dB (−40 → −30 dB master).
- This applies to every AC'97 device in 86Box (ES1371/1373, CT5880, the VIA AC'97 controllers).

**Left as is (open):** the ES1371 mix in 86Box halves twice:
- `l >>= 1` after summing DAC1 and DAC2;
- `/ 2` when handing its buffer to the mixer.

That is −12 dB of fixed headroom. Without an ES1371 datasheet there's no evidence what the chip does when DAC1 + DAC2 overflow, so it was not changed. If the overall level matters, 86Box's sound gain covers it.

Audio captures: `analysis/p7/audio*/main.wav` (automation `audio start/stop`). The per-100 ms analysis shows a separate event per coin and per touch.

## 5. Emulator changes (branch `touchmaster`, commits `d4b7fbceb` and `8767a4342`, local, not pushed)

| File | Change |
|---|---|
| `src/device/dolphin_io.c`, `include/86box/dolphin_io.h` | coin presses 80 ms (`DOL_COIN_MS`, with the `coinmgr` windows in a comment); **electronic coin inputs A–F** on 64h bits 1–6 (`DOLPHIN_LINE_ELEC_A..F`); switch reads by register |
| `src/qt/qt_ioboard_controls.cpp` | I/O Board menu: "Coin 3 (bill validator)", Electronic coin A–F |
| `src/device/io_board.c`, `include/86box/io_board.h` | `io_board_pulse(line)`: presses a line on whichever arcade board is fitted |
| `src/automation.c`, `doc/specifications/automation.md` | **`ioboard pulse <line>`** automation command (Dolphin: 0–2 coins, 3 Calibrate, 4 TEST, 5–10 electronic A–F) |
| `src/sound/snd_ac97_codec.c` | AC'97 gain table at 1.5 dB per step |

Tools: `scripts/p7-touch.py` (touch at x,y, then run and screenshot) and `scripts/p7-barstrip.py` (stack crops of frames).

## 6. Not covered

- The Dolphin UARTs (bill validators, EZ keypads on serial) are still a stub. This machine's validator is on the parallel electronic inputs, so they aren't needed here.
- Meter and lockout outputs (66h) are latched but not shown anywhere in the UI.
- The MPN modem (`/dev/cuaa4`, tournaments) was not tried.
