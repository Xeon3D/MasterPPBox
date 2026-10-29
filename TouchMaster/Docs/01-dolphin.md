# 01: Dolphin I/O board and security chips (Phase 1)

**Question:** What must an emulated Dolphin board do so that the unmodified TouchMaster II software boots past its security gate? Can we make valid key data without a real key?

**Answer:**
- The full behaviour is specified below and implemented as a portable C model (`analysis/p1/src/`).
- The model is proven against **the original, unmodified Midway protection code** (`t/coinmgr/dolphin.c`, compiled on the host). Selftest: 0 failures.
- A standalone generator (`scripts/p1-mkchips.py`) produces programmed Dolphin + Abyss chip images. They are **byte-identical** to what the original code writes, and the original `dDana`/`dEve` and menu logic accept them.

**Keyless is solved at the data level.** Phase 4 only has to wrap this model as an 86Box device.

---

## 1. Board register map (ISA variant: memory 0xD0000–0xDFFFF, IRQ 5)

Sources: `dolphin.c`, `olib.c` (`OpenDolphin`, UART), `coinmgr.c`, `io.c`, `diag.c`, `dl.cc`, `menu.cpp`. "Who" = which process touches it.

| Off | Width | R/W | Function | Who | Model value |
|---|---|---|---|---|---|
| 0x20+2n, n=0..7 | 8 | R/W | 16550-style UART (EZ95/EZKEYII keypads, bill validators, SSCP) | `uart`, `midas`, olib | stub; LSR (n=5) = 0x60 |
| 0x50 | 16 | R | **ID**: hi byte must be 0x01 (board), lo byte = FPGA rev, must be ≥ 2. `io` also treats byte 0x50 == 0xFF as "no board" | `menu`, `io`, `coinmgr` (displays it) | **0x0102** |
| 0x58 | 8 | R/W | **Atmel bit-bang** (§2) | dolphin.o in `menu`/`coinmgr`/`diag`/`mgl` | modelled |
| 0x60 | 8 | R | DIP switches, active low. **bit7 = DIP 8 "Emergency Restore"** (0 → `dl` wipes `/rw`, menu waits for it to clear). bit0 = touch-invert (with ID present: bit0=0 → invert Y) | `dl`, `menu`, `io`, `diag` | 0xFF (all off) |
| 0x62 | 8 | R | Switches, active low: bit0/1/2 = coin 1/2/3, **bit6 = Calibrate** (→ `diag Calibrate`), **bit7 = TEST** (→ `diag`) | `coinmgr`, `diag` | 0xFF |
| 0x64 | 8 | R | Extra inputs, active low: bit0 unused, bits1–6 = escrow inputs 3–8 (bills/extra coins) | `coinmgr` | 0xFF |
| 0x66 | 8 | R/W | Outputs: bit5 = mechanical meter pulse, bit7 = bill acceptor enable, bit6 / bit3 = coin enable / coin lockout | `coinmgr`, `diag` | latch |
| 0x70 | 8 | R | Interrupt cause: bit1 = UART | `coinmgr` | 0 |
| 0x74 | 16 | R/W | Control: bit0 LED blink, **bit1 toggled by `dl` every frame** (watchdog/heartbeat?), bit2 touch LED, bit4 UART reset, **bit10 timer interrupt enable** | `dl`, `io`, `coinmgr`, `midas` | latch |
| 0x76 | 16 | W | Timer config: init `0xFF10`, run `0x8010` ≈ 215 Hz | `coinmgr` | latch |

**Interrupt contract** (kernel `dolphin0` driver, OEM `/kernel`):
- The ISR (`spigintr`) only sets a flag and calls `wakeup()`. It never touches the board.
- `coinmgr` loops as follows:
  1. set `0x74` bit10;
  2. `read(/dev/dolphin0)`, which sleeps until the IRQ or a **60-tick (0.6 s) timeout**;
  3. clear bit10;
  4. read `0x70`.
- An emulated device should therefore **pulse IRQ 5 once per timer period while bit10 is set** (ISA edge-triggered). With no IRQ at all, `coinmgr` still runs, but at about 1.7 Hz, so coin timing and the TEST/Calibrate response are slow.
- `dolphin_probe` does **no** presence detection, so `/dev/dolphin0` always opens. `dolphin_open` allows one opener (`coinmgr`).

**PCI variant** (Xilinx `10EE:0001`, `/dev/dolpci0`, ALPHA10 kernel only):
- Word registers:
  - `0x00` IRQ status (bit2 timer, bits4–7 UART 0–3);
  - `0x10` control (bit10 timer, bit1 frame);
  - `0x14` timer (`0x2001`);
  - `0x18` (`0x0403`, bit0 UART reset);
  - `0x20` ID;
  - `0x4E` self-test (`0x3330`);
  - `0x50` / `0x54` chip 0 / 1 bit-bang;
  - `0x60` DIP;
  - `0x64` / `0x68` switches (+0x100/0x200 PCB TEST/Calibrate);
  - `0x6C` outputs;
  - `0x70` 7-segment LED;
  - `0x100 + 0x20·n` UARTs.
- **Note:** 3.0x `menu::CheckHardwareOK()` *always* reads the ID through `/dev/mem` at 0xD0000. A PCI-only board would hit "Dolphin I/O card not found!" unless it also decodes that window. **The ISA board is the target.**

## 2. Atmel bit-bang port (ISA 0x58)

| Bit | Write | Read |
|---|---|---|
| 0 | SDA out (only when bit6 set) | **SDA in** (wired-AND of host and selected chip) |
| 1 | SCL | echo |
| 2 | RST (high = reset the chip's protocol state) | echo |
| 3 | select **chip 0 = U9 "Dolphin"** (on the board) | echo |
| 4, 5 | select **chip 1 = "Abyss"** configuration card / key (software uses 0x10 when driving, 0x20 when reading) | echo |
| 6 | host drives SDA (clear = released → pulled up) | echo |

The software performs exactly one register write per bus transition.

**Edge rules used by the model** (they reproduce the software's timing exactly):
- If SCL changes in a write, it is a clock edge, and any SDA change in the same write counts as happening while SCL is low.
- SDA changing while SCL stays high is START (high→low) or STOP (low→high).

PCI: `0x50`/`0x54` bit0 SDA, bit1 SCL, bit2 RST, bit3 host drives SDA.

## 3. Chip model (AT88SC153-class, `at88sc153.c`)

**Memory:** 256 bytes. Zones 0–2 are user data (0x00–0xBF); zone 3 is config (0xC0–0xFF).

**Bus protocol:** MSB first, START/STOP, ACK on the 9th clock, sequential reads within a zone.

**Commands** (`0xB0 | sel<<2 | op`):

| Cmd | Operation |
|---|---|
| `B0/B4/B8/BC` | write zone 0–3: + address byte + ≤8 data bytes, committed at STOP |
| `B1/B5/B9/BD` | read zone 0–3: + address byte, then the chip transmits |
| `B3` / `B7` | verify write-password set 0 / set 1 ("secure code"): + 3 bytes |
| `BA` / `BE` | write fuses (+1 byte, bits cleared = blown) / read fuses |

**Password behaviour:**
- A correct password sets its PAC (password attempt counter) to 0xFF.
- A wrong one shifts the PAC left (one attempt consumed). PAC 0 locks the set.
- The software checks `PAC == 0xFF` after every verify.

**Config zone of a blank chip** (what the software requires):

| Addr | Blank value | Requirement in code |
|---|---|---|
| 0xC0–0xC7 | ATR `3B B2 11 00 10 80 00 01` | 0xC0 ≠ 0x00/0xFF, else −2 "no chip" |
| 0xC8–0xC9 | fab code **`AE 60`** | else −5 "not our chip" (Midway-specific) |
| 0xCC–0xCE | access registers | written 7D/7F/77 at programming |
| 0xF0 / 0xF4 / 0xF8 / 0xFC | PAC W0/R0/W1/R1 = FF | must read FF after a verify |
| 0xF9–0xFB | **transport secure code `D5 FE 7E`** | `dBetty`/`dChris` verify it before programming, else −5 |
| user zones | FF | magic bytes absent → "not programmed" (−1) |

**Not modelled** (the software never depends on them): access-register write protection and read-password gating. The ATR content is a plausible AT88SC153 value; only "≠ 00/FF" is checked.

## 4. Data layouts (confirmed by round-trip)

**Software XOR:** every byte below 0xC0 is stored XORed with `dloffset[addr & 0x3F]`. That table starts `7F 45 4C 46`, the ELF magic.

**U9 / "Dolphin" chip**, written by `dBetty` (`diag init`), read by `dDana`:

| Addr | Contents |
|---|---|
| 0x00–0x0D | ASCII serial (`%qd`) XOR `42 31 54 2A FE 91 EB 24 99 4D` |
| 0x0E–0x11 | manufacture `time_t` XOR `0x1B47A122` |
| 0x12–0x15 | `(s + (s<<16)) ^ 0xB2F43749`, where s = byte sum of the plain serial + time |
| 0x16–0x17 | country |
| 0x18–0x19 | magic **AE C0** |
| 0x1A–0x1D | random "MAC" (31 bits) |
| 0x40–0x43 | country, distributor, check digit |
| 0xBF | layout = 1 |

Passwords: W0 `EC3A4D`, R0 `3CFFE0`, W1 `DCAB17`, R1 `45A3CD`. Fuses CMA+PER are blown (fuse byte 0x07 → 0x01).

**Abyss / key**, written by `dChris` (`ProgramAbyss`), read by `dEve`, rewritten by `dGloria` (country change):
- 0x00–0x07: the 64-bit system serial in clear.
- Other user bytes sit at `GetMasterPalEntry(i)` (a zone-local permutation; table in `analysis/p1/raw/masterpal_lut.bin`). They are XORed with a per-card table `(random() & 0xFF) ^ 0xB5`, generated after `srandom((serial & 0xFFFFFFFF) + hash)` using FreeBSD 3.2's `random()`.
- The 16-bit `hash` is stored in clear at 0xBE–0xBF. Also in clear:
  - 0x38 = layout 2;
  - 0x78 = 1;
  - 0x7A–0x7B = random;
  - 0xBC–0xBD = magic **50 AA**.
- Logical 0x40–0x4F holds the version (major<<16|minor; programming writes **3.0**), the country, and three cross-checks:
  - `country ^ 0xDA4B`;
  - `version ^ 0xA41301B4`;
  - `(those two XORed) ^ 0xC582`.

Passwords: W0 `C6D45E`, R0 `3CE973`, W1 `D2004B`, R1 `724132`.

**`dEve` deliberately skips** the 0x7C–0x7F checksum (comment: "running out of time … Fix this later! XXX") and the zone-0 checksum at 0x3C–0x3F.

## 5. Verified facts and findings

| # | Finding | Evidence |
|---|---|---|
| F1 | 2.03 and 3.0x ship the **same** (non-`OLD_BUGGY`) `GetMasterPalEntry` LUT | full 192-byte match in both `libolib.so.1.0` (OEM @0x1cabd, ALPHA10 @0x1d2ef) |
| F2 | FreeBSD 3.2 `random()` = TYPE_3 additive, Park–Miller seeding (`x<=0 → +0x7fffffff`), 10·deg warm-up | OEM `/usr/lib/libc.so.3` `srandom`/`random` disassembly |
| F3 | **`dChris()` has no `return`.** In the 2.03 binary it returns `usleep()`'s value (`menu` 0x1e667: `call usleep; leave; ret`). `ProgramAbyss` reports failure if that is non-zero, which would happen if a signal interrupts the last 100 ms sleep | disassembly; modelled as `return usleep(100000);` in the harness |
| F4 | **`dAndy()` is broken**: it reads its magic from address 19 decimal (0x13) instead of 0x19, so it is never 1 on a programmed chip. It has **no callers** | harness `[INFO]` line; source grep |
| F5 | `OpenDolphin()` contains `else if (dolphintype = DOLPHIN_ISA)` (assignment) | `olib.c:3209` |
| F6 | The checksums assume a 32-bit `long`; a 64-bit host build gives −3 errors | first harness run; fixed with `-m32` |
| F7 | `menu` (3.0x) reads the board ID only via `/dev/mem` 0xD0000, so PCI-only boards fail the ID check | `menu.cpp:3284` |
| F8 | The interrupt is acked by userland (`0x74` bit10 off), not by the ISR | `spigintr` disassembly |

## 6. Reproduce

All the following run inside WSL Ubuntu with gcc multilib:

```
sh analysis/p1/build.sh        # derives build/dolphin_orig.cc from the ORIGINAL dolphin.c (SHA256 printed), builds -m32
analysis/p1/build/harness selftest           # -> analysis/p1/raw/selftest.txt   (SELFTEST OK, 0 failures)
sh analysis/p1/crosscheck.sh                 # -> analysis/p1/raw/crosscheck.txt (CROSSCHECK OK)
```

**Derived source:** `scripts/p1-mkharness.py` makes 4 changes to `dolphin.c` and nothing else:
- the include;
- the two mmap pointer declarations;
- the `dChris` tail (F3).

Input SHA256 `c19792fd…0982` → output `db3ed170…75dc`.

**Generate keys for the emulator:**

```
python -I scripts/p1-mkchips.py --serial 100123456 --country 1 --out-u9 u9.nvr --out-abyss abyss.nvr
```

`.nvr` = 256 bytes of chip memory + 1 fuse byte. Alternatively, ship **blank** chips and let the game provision itself: `diag init` asks for a 9-digit serial, then `ProgramAbyss` writes the key (version 3.0 in 3.0x builds).

## 7. Adversarial check (guardrail 7)
- **2.03 vs 3.0x source drift:**
  - the LUT is identical (F1);
  - the `dolphin.o` constants are present in all four 2.03 binaries;
  - the security strings match.
- **Still unproven:** that the 2.03 `dDana`/`dEve` bodies are byte-for-byte the same logic. **Owner: P2** (disassembly diff of the 2.03 `menu` dolphin.o against the ALPHA10 `dolphin.o`).
- **Version number:** 2.03's `ProgramAbyss` may write a version other than 3.0. That is harmless, because the version gate is compiled out (`#if 0 // Ed said…`) and `mgl` treats every version as valid.
- **Not modelled:** UARTs, meters/lockouts and the frame bit (0x74 bit1). Free play needs none of them, but if real hardware used bit1 as a watchdog, the emulation can ignore it.
- **Parsimony (guardrail 6):** the boring explanation is "a dongle with an obfuscated EEPROM". It holds: no challenge-response and no crypto beyond fixed passwords and XOR. The cheap experiment that rules out a hidden extra check is that the original code accepts generator-made images. It does.
