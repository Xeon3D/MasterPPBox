# 02: 2.03 (OEM) binary confirmation (Phase 2)

**Question:** The Phase 1 model was proven against the 3.0x *source*. Does the shipped **2.03** software (OEM image) contain the same protection logic, and are there gates or sabotage the source does not show?

**Answer: yes, with one documented difference that doesn't matter.**
- 2.03 links an older object file, `dolphin.o.good`. It is preserved in ALPHA10 (`t/coinmgr/dolphin.o.good`, 29 Sep 2000 12:09).
- That object is **instruction-identical** to the current source in 20 of 22 functions. The other two (`dout`/`din`) are exactly the source's ISA branch.
- The menu gate has the same decision tree.
- The only Abyss-version check that exists in 2.03 is in a binary nothing runs.
- `secfail` is provably inert.
- No date bombs were found in the time-handling code.

The Phase 1 model and the generated keys therefore apply to 2.03 unchanged.

---

## 1. Which security object is in which build (`scripts/p2-objmatch.py`)

**Method:**
1. Take every function of a relocatable `.o`, with its relocated 4-byte fields wildcarded.
2. Search the linked executable for a **unique** match.
3. Follow each absolute relocation into the executable and compare the referenced data (password/XOR tables) byte for byte.

| Object | OEM 2.03 `menu` | `coinmgr` | `diag` | `system/mgl` | ALPHA10 3.0x `menu` |
|---|---|---|---|---|---|
| `dolphin.o` (source, 29 Sep 21:39) | 14/22 fns missing | same | same | same | **all 22 + data identical** |
| `dolphin.o.good` (29 Sep 12:09) | **all 22 + data identical** | **identical** | **identical** | **identical** | 14/22 missing |

Evidence: `analysis/p2/raw/objmatch-dolphin.o*.txt`. The "missing" functions differ only by shifted call displacements, explained next.

## 2. What differs between `.good` (2.03) and the source (`scripts/p2-objdiff.py`)

The comparison normalises the disassembly: call targets become `function+offset`, and relocated operands become symbol names.

- **20 of 22 functions are SAME:** `dBetty`, `dChris`, `dDana`, `dEve`, `dGloria`, `dFred`, `dAndy`, `TestBoard`, `ResetAtmel`, `Read/WriteFuses`, the read/write EEPROM routines and every bus primitive.
- **`dout`, `din` differ.** 2.03 has *only* the ISA path: the same bit encodings (`0x08|0x40` chip 0, `0x50`/`0x20` chip 1, `din` `0x08`/`0x20`), no PCI branch and no `NOP16` delays. In other words, PCI Dolphin support was added after 2.03. (`analysis/p2/raw/objdiff-*.txt`)

**Consequences:**
- the Phase 1 C model (ISA path) is exact for 2.03;
- F3 (`dChris` returning `usleep()`'s value) and F4 (`dAndy` broken) apply to 2.03 too;
- the 2.03 security code can only drive an **ISA** Dolphin.

## 3. Application call sites in 2.03 (`scripts/p2-callers.py`)

| Binary | Caller | Calls |
|---|---|---|
| `menu` | `CheckHardwareOK` @0x08061738 | `dFred`, `dDana` (×2), `dEve` (×2) |
| `menu` | `ProgramAbyss` @0x08061424 | `dDana`, **`dChris(serial, country, 1, 0)`** |
| `coinmgr` | `main` | `TestBoard` only |
| `diag` | `initserialnumber` / `SetCountryCode` | `dBetty` / `dGloria` |
| `mgl` | `CreateMenuIniFile` @0x08048b80 | `dFred`, `dDana`, `dEve` |

All other hits are `dGloria`'s own internal calls. Unlike 3.0x, 2.03 `diag` has no "AV:" system-info screen.

## 4. `menu::CheckHardwareOK()` in 2.03 (annotated: `analysis/p2/raw/oem-menu-CheckHardwareOK.txt`)

The sequence and constants are identical to the 3.0x source:
1. `mmap(/dev/mem, 0xD0000, 0xFFFF)`.
2. ID word: `(w & 0xFF00) == 0x0100`, else "Dolphin I/O card not found!" (hard lock).
3. `(w & 0xFF) > 1`, else "…needs newer FPGA" (hard lock).
4. `dFred`, then `dDana`:
   - 0 → store serial/mfg date;
   - −1 → "PD called", `diag init`, `dDana` again;
   - < −1 → "System Security Failure" (hard lock).
5. Serial = 0 → lock free play and skip.
6. `dEve`:
   - 0 → clear LOCKFREEPLAY;
   - −1 → `ProgramAbyss`;
   - −7 / −6 / < −1 → hard locks;
   - −2 → "Configuration security board not found … Free Play only" (continue).
7. Country ≠ `aa.dat` country → `diag factoryrestore`.

**No version check:** the string "not authorized for this version" is absent from 2.03 `menu`.

**Difference from 3.0x:** 2.03 `ProgramAbyss` programs new keys as **version 1.0**; 3.0x uses 3.0. Section 5 explains why this doesn't matter.

## 5. The only key-version gate in 2.03 is dead code

`t/system/mgl` (2.03) **does** gate games on the Abyss major version, unlike the 3.0x source, where `in_this_version` defaults to 1. In 2.03:
- game ids ≤ 0x26 are always allowed;
- ids ≤ 0x28 need major ≥ 3;
- anything higher is never allowed.

The 2.03 game table, read from `mgl`'s data (`analysis/p2/raw/oem-mgl-gamelist.txt`), gives:
- only **Buzztime.com Trivia (gid 40)** needs major ≥ 3;
- gids 1000–1002 (New Game, Triple Elevens, Kick Champion) are never allowed.

**But nothing runs `/t/system/mgl` in 2.03:**
- No binary, script or `rc` file references `/t/system/mgl`. The only other hit is an assert filename, `mgl.h`, inside `libolib`.
- `menu`, `diag`, `midas` and `myad` import `CreateMenuIniFile()` from **`libolib.so`**. That copy calls no Dolphin functions and has no version gate.
- **Field proof:** the OEM machine's own `/rw/menu/menu.ini` (written 5 Jul 2004, country Canada, 37 games) contains **Triple Elevens, gid 1001**. The gated `mgl` would have excluded it.

**Conclusion:** the Abyss version number has no effect in 2.03. Generated keys may carry 1.0 (faithful to 2.03) or 3.0 (faithful to 3.0x); both pass.

## 6. Field-machine parameters (for keys that won't trigger a factory restore)

- **Country:** `menu.ini` says **Canada (country code 24)**, as derived from `aa.dat`. A key with a different country makes `menu` run `diag factoryrestore`, which **resets the operator settings in `aa.dat`**. To keep the machine's settings, generate the key with `--country 24`. (`aa.dat` keeps audits/settings, but its exact layout is unknown because `/t/aa/aa.h` is on neither disk.)
- **Serial:** not found in `aa.dat` under any plain encoding (64-bit LE, 32-bit, ASCII, `X00YYYYYY` pattern). `/rw/mpn/config` holds `serialNumber=922889`, but that is the factory MPN config dated 2000-10-05, not necessarily the chip serial. Any serial works: `menu` overwrites `aa.dat`'s copy from the chip. 922889 is the most plausible value if fidelity matters.

**Recommended key for the OEM image:**

```
python -I scripts/p1-mkchips.py --serial 100922889 --country 24 --version 1.0 --out-u9 u9.nvr --out-abyss abyss.nvr
```

(The 9-digit `X00YYYYYY` form is what `diag init` would produce from 922889.)

## 7. Sabotage and time-bomb audit

- **`secfail` (`dl.r2c`, both builds):** the symbol is present and the global sits at 0x080698EA (OEM). It has 5 code references: **one store, of 0, at init** and 4 tests (the `%100`/`%500` corruption sites). Its address appears nowhere else except `.symtab`, so it can't be set through a pointer. **Inert.** (`analysis/p2/raw/oem-dl-secfail.txt`)
- **Date bombs (`scripts/p2-timeuse.py`):** I resolved the PLT stubs of `time`/`gettimeofday`/`localtime`/`mktime`/`difftime` in 12 core 2.03 binaries (`menu`, `coinmgr`, `uart`, `dl.r2c`, `io`, `sound`, `diag`, `midas`, `mgl`, `myad`, `upgrade`, `hiscore`). Of 194 call sites, only one is followed by an immediate compare: `menu` 0x08051F8E, `cmp eax, 0x1517F` (= 86 399 s, a midnight rollover). **No date constants.** A naive whole-binary epoch-constant sweep was discarded: it is dominated by float constants and ASCII decoded as code (kept in `analysis/p2/raw/` for transparency).

## 8. Blind spots remaining (guardrail 7)

| Item | Status | Owner |
|---|---|---|
| `libolib.so` time use | not covered (PIC PLT not resolved by `p2-timeuse.py`); 3.0x source `olib.c` shows no date logic | low, P3 if symptoms |
| Games (`/t/games/*`) | not audited individually; they call only `CallMeFirst` (no security) | low |
| `aa.dat` layout | unknown; only affects settings preservation | P3/P4 if needed |
| Runtime revalidation | none: security runs only at `menu` start; `coinmgr` only calls `TestBoard` | done |
| Dolphin FPGA behaviour on real HW (`TestBoard` "unlocks the FPGA") | emulation-irrelevant; the software never checks the result | done |

**Parsimony (guardrail 6):** the boring hypothesis, "2.03 = the same dolphin.c, slightly older", is confirmed by an exact binary match, not by inference.

## 9. Reproduce

```
python scripts/p2-objmatch.py analysis/fs/ALPHA10/root/t/coinmgr/dolphin.o.good analysis/fs/OEM/root/t/{menu/menu,coinmgr/coinmgr,diag/diag,system/mgl}
python scripts/p2-objdiff.py  analysis/fs/ALPHA10/root/t/coinmgr/dolphin.o.good analysis/fs/ALPHA10/root/t/coinmgr/dolphin.o [dout__Fv din__Fv]
python scripts/p2-callers.py  <exe> name=0xaddr ...
python scripts/p2-annot.py    <exe> <start> <end> [name=0xaddr ...] [--brief]
python scripts/p2-timeuse.py  <elf> ...
```

These need capstone from the user site-packages, so run them without `-I`. They read only extracted copies.
