# TouchMaster II → Windows: port feasibility (side study, 2026-10-28)

**Question:** Using the ALPHA10 source tree, can the TouchMaster II game stack be rebuilt as a native Windows application instead of being run under 86Box?
**Inputs:** `analysis/fs/ALPHA10/root/t` (source), `analysis/fs/OEM/root/t` (2.03 binaries and media), and the manifests `analysis/p0/raw/*-root.tsv`. Every count below was produced by grep or Python over those trees. Nothing was modified.

---

## 0. Verdict

**Feasible. Medium difficulty. No fundamental blocker.** The estimate for a playable native build is roughly **3–5 person-months** for an experienced C/C++ developer. A first milestone (menu plus one game on screen, with sound and mouse touch) is about **5–7 weeks**.

Why it is easier than it looks:
1. **The games are almost OS-free.** The ~60 games (≈248 k lines including tourngames) include only `gamedef.h`, `gfx.h`, the MPN headers and libc. None of them uses fork, mmap, `/dev`, select, signals or OpenGL. They draw, play sound and read touch only through **`libolib`, an 89-function API**.
2. **The hardware is already behind a small HAL that has been ported three times.** `dl` (the display server) calls about 10 backend functions (`initvideo`, `MgxBlit`, `swap`, `swapnow`, `waitforvsynchigh/low`, `setdac`, `DrawLine`, `ImageDecompress`, …). Implementations already exist for the **Rage IIC** (`r2c/`), the **Rage 128** (`r128/`) and the **Cyrix MediaGX** (`cyrixmgx/`). A fourth one (software or SDL/D3D) is the same exercise again, about 1–1.5 k lines.
3. **Sound already mixes in software.** `sound.c` mixes into a 16-bit `mixedbuff[1024]` and copies it to the ES1371 DMA page. It has also been ported to ICH AC'97. On Windows the hardware path becomes an SDL or WASAPI callback.
4. **The assets are plain zlib/bzip2.** `.tm2`/`.tmz` frames are decoded with `uncompress()` / `bzBuffToBuffDecompress()` on the CPU, so no GPU-specific formats are involved.
5. **There is almost no inline asm.** The only asm is `NOP16` delay macros in 4 hardware files.
6. **Source and binaries match.** In 75 of 79 ALPHA10 directories the binary is newer than every source file, so the tree reflects what was built.

What makes it real work, not a recompile: the **multi-process POSIX architecture** (SysV shm, msg queues, FIFOs, fork/exec, select), a **missing header (`aa/aa.h`)**, **gcc 2.7-era C++**, and the fact that the source is **3.0x dev, not the 2.03 release**.

---

## 1. Source inventory (ALPHA10 `/t`)

| Area | Files | Lines | Port role |
|---|---|---|---|
| `games/` | 232 | 210,634 | Recompile only |
| `tourngames/` | 34 | 37,417 | Recompile only (MPN tournament hooks can be stubbed) |
| `mpn/` (dial-up tournament network) | 364 | 56,263 | **Drop or stub**, since it is not needed for play |
| `video/` (dl, olib, 3 HW backends, Mesa/TinyGL copies) | 70 | 36,740 | **Core of the port** |
| `diag/` (operator menus) | 20 | 33,481 | Recompile, and stub the mount/newfs/reboot actions |
| `menu/` | 11 | 16,419 | Recompile; adapt game launching |
| `hiscore/` | 13 | 13,088 | Recompile |
| `system/` (gamedef, mgl, iclub, syscoins) | 11 | 8,804 | Recompile |
| `myad/` | 4 | 4,798 | Recompile |
| `coinmgr/` (Dolphin, coins, UART) | 6 | 3,848 | **Replace the hardware layer** |
| `upgrade/` | 4 | 2,121 | Drop (it copies `/mnt/t` from CD or HDD) |
| `sound/` | 4 | 2,018 | **Replace the hardware output** |
| `midas/` (serial peripheral protocol) | 2 | 1,433 | Drop or stub |
| `io/` (MicroTouch serial) | 2 | 638 | **Replace** with mouse/touch input |
| **Total** | ~777 | **≈ 427 k** | ~370 k without MPN |

**Game coverage:** every game that has a binary in OEM 2.03 has source in ALPHA10. `findit`, `kickchamp` and `spotlight` are menu placeholders with no binary in either image. **`golf` has a binary but no source** (ALPHA10 only). `updown`, `vectorace` and `vectormaze` have source but no binary, which may mean they are unfinished. Four games have source edited after their last build (`pbviewfinder`, `cannon`, `prs`, `shootinggallery`), so they may not build cleanly.

**Media:** ALPHA10 `/t` is 2.82 GB and OEM `/t` is 2.12 GB. Of 8,043 OEM media files, 5,129 are byte-size identical in ALPHA10, 273 differ, and 2,641 are OEM-only. The OEM-only files are mostly `viewfinder` frames (22.7 MB), `tourngames/million` and `tournament/tm2s` (258 MB). A port should **merge media from both images**. Note that the Phase 0 extraction skipped files over 4 MB, so a full re-extract is needed before any build.

---

## 2. Architecture and where it is cut

```
              ┌───────────── one process each, FreeBSD ─────────────┐
 game / menu / diag ──libolib──┬─ SysV shm (display-list prequeue, image regions)
                               ├─ FIFOs /tmp/dl/fifo.N, /tmp/sound/fifo.N
                               ├─ SysV msg queues (sound)
                               ├─ /tmp/vsync, /tmp/io/touch (shm id), /rw/aa/aa.dat (mmap)
                               └─ UNIX sockets /rw/tmp/comm/* (UART multiplex)
 dl (display server + supervisor: fsck/mount /rw, forks sound, io, coinmgr, midas)
   └─ HAL: r2c | r128 | cyrixmgx  ──► /dev/mem, /dev/rag0 (VLINE IRQ), port 0xD818
 sound ─► /dev/est0 mmap + in/out @0xEF00          io ─► /dev/cuaa0 MicroTouch
 coinmgr ─► /dev/dolphin0 | /dev/dolpci0 | /dev/mem @0xD0000 (+ Atmel chips)
```

There are three clean seams:
- **Seam A, the hardware HAL under `dl`, `sound`, `io` and `coinmgr`.** It must be replaced regardless of strategy.
- **Seam B, the POSIX IPC between olib and the daemons.** It is either emulated or collapsed.
- **Seam C, the `libolib` API itself (89 functions).** A radical port could re-implement olib in-process and skip seam B entirely.

---

## 3. OS and hardware coupling, measured

Counts exclude MPN and the bundled Mesa/TinyGL.

| Dependency | Hits / files | Where | Windows replacement |
|---|---|---|---|
| `fork()` | 47 / 15 | dl, menu, attract, diag, coinmgr, gamedef, upgrade | `CreateProcess` (spawn). Fork-without-exec sites need individual review |
| `exec*` | 48 / 13 | same | `CreateProcess` |
| `system("…")` | 113 / 13 | `/bin/cp` ×18, `/sbin/mount` ×17, rm, mkdir, reboot, newfs, chown | Mostly upgrade/diag/maintenance. Stub, or use `std::filesystem` |
| SysV shm (`shmget/shmat`) | 13 / 4 | olib, dl, io | `CreateFileMapping` named `tm_shm_<key>` |
| SysV msg (`msgget/snd/rcv`) | 20 / 3 | olib ↔ sound | Shared-memory ring plus named event |
| `mkfifo` + FIFO I/O | 9 / 5 | olib ↔ dl, sound | Named pipes, or the same ring |
| `select()` | 30 / 6 | dl, sound, coinmgr, uart | `WaitForMultipleObjects` on the shim handles |
| `mmap()` | 26 / 13 | `.tm2` files (read-only), aa.dat, hardware | File mapping for files. Hardware maps disappear |
| `signal/sigaction`, `kill`, `waitpid` | 31 / 56 / 51 | process supervision, `OlibSIGEXIT` | Job objects, `TerminateProcess`, named events |
| Port I/O `in*/out*` | 100 / 4 | sound, r128, gx, r2c only | Gone with the HAL |
| `"/dev/…"` literals | 33 / 14 | HAL, serial | Gone, or `COMn` for a real MicroTouch |
| `sysctl` | 12 / 3 | olib, dl | Stub |
| `random()/srandom` | 1,244 / 100 | games everywhere | Add the FreeBSD `random()` (BSD licence, ~100 lines) **for identical RNG behaviour** |
| `usleep`, `gettimeofday` | 111 / 24 | timing | Trivial shims (`timeBeginPeriod(1)`) |
| `opendir/readdir` | 87 / 13 | menus, diag | dirent shim (MinGW provides one) |
| `flock/lockf` | 22 / 9 | aa.dat, hiscores | `LockFileEx` |
| `bcopy/bzero`, `caddr_t`, `u_int`… | 103 / 21 | everywhere | Macro shim header |
| Absolute paths `/t/…`, `/rw/…` | **4,678** | everywhere | **No edits needed.** On Windows `"/t/x"` resolves against the current drive root, so the tree can sit at `T:\t`, `T:\rw`, `T:\tmp` (use `subst T:` or a VHD). `/dev/*` and the FreeBSD symlinks (`/tmp`→`/rw/tmp`) are handled by the shim |
| Inline asm | 5 / 4 | `NOP16` delay macros in HW files | Gone with the HAL |

**Hardware HAL replacements:**

| Daemon | Today | Windows |
|---|---|---|
| `dl` video | Rage IIC GUI engine + 3D scaler, VLINE IRQ, 640×480 15/16 bpp | **A software blitter into a 640×480 RGB565 buffer, presented by SDL2/D3D11 with vsync.** `MgxBlit` must honour `SCALE`, `ALPHAOVERRIDE`, `FACTOR`, `POLYGON`, `LINE`, crop/flip and palette (`setdac`), plus the midres/lowres/svga rescale paths already present. A modern CPU easily software-blits the scenes a 2000-era Rage IIC handled. Vsync comes from the swap chain, which removes the whole VLINE IRQ and `0xD818` problem |
| `sound` | ES1371 DMA page @0xEF00 or ICH AC'97 | SDL/WASAPI callback that pulls the existing `coremix` output |
| `io` | MicroTouch Format-Tablet on COM1 | SDL mouse/touch → the same shm touch record. **Optional:** keep the serial code via `CreateFile("COM1")` for a real cabinet touchscreen |
| `coinmgr` | Dolphin ISA/PCI board + Atmel chips, 215 Hz IRQ | Emulated register block in memory: keyboard → coin/TEST/door, DIPs at 0xFF. Either run `dolphin.c` unchanged against the P1 AT88SC153 model, or short-circuit `CheckHardwareOK` (this is our own build, so that is a source edit, not a binary patch) |
| `midas`, MPN, `upgrade`, LED sign | serial / modem / removable media | Stub (return "not present") |

---

## 4. Gaps and traps (ranked)

1. **`/t/aa/aa.h` is missing from the image.** It is included by 25 files, it defines the **342 `GID_*`, `REGION_*`, `ADJ_*` and `AUD_*` symbols** and, under `NEED_AA_STRUCTS`, the layout of `/rw/aa/aa.dat` (audits and adjustments). Nothing in the manifests matches `aa.h`/`aa.c`. **It must be reconstructed** from:
   - immediates in the compiled binaries (the ALPHA10 binaries match the source, so every `aa_getdata(GID, REGION, ADJ, …)` call site gives an operand-to-name mapping);
   - `libolib.so.1.0` (`aa_getoffset`, `aa_sanity` are exported dynamic symbols);
   - the real `aa.dat` files (ALPHA10 278,656 B, plus the OEM copy) for layout and defaults.

   This is the **single largest unknown**: about 1–3 weeks, and it is also on the critical path for the 86Box route's P1 (`aa.dat` consistency check).
2. **The source is 3.0x dev (ALPHA10), not the 2.03 release.** A port gives *3.0x-dev behaviour*, plus newer games and newer bugs. Exact 2.03 fidelity remains the job of the 86Box route. Golf would be lost (binary only), and a few games may be unfinished (§1).
3. **Do not use a 64-bit LP64 runtime (Cygwin/MSYS2).** Structs that go over shm/FIFOs and into files hold `unsigned long` (assumed 32-bit), `ino_t` and **raw pointers** (`dlflags.h`: `mmappointer`, `next/previous`, `eventhandler`, `shmemptr`). Cygwin is **64-bit-only** (32-bit was dropped in 3.4) and **LP64**, so it silently changes `long`. A **32-bit Windows (i686) target** is ILP32 and keeps every layout as it was on FreeBSD/i386, including `aa.dat` and the `.tm2` headers. A later x64 build is possible because Windows is LLP64 and `long` stays 32-bit, but the pointers in shared structs then have to become offsets.
4. **gcc 2.7.2 C++ dialect.** All C is compiled `-xc++`. Expect pre-standard C++ issues: `for`-scope leakage, implicit `int`, string literal → `char*`, `goto`/`longjmp` across initialisations (`blitjmpbuffer`), and `#pragma pack` (4 sites). Mechanical work: start with `-fpermissive -m32` on MinGW-w64 i686 gcc and fix forward. MSVC x86 is possible but would mean more edits.
5. **Process model inside `dl`.** `dl mount` does `umount/fsck/newfs` on `/rw`, wipes on DIP 8, then forks the daemons and supervises them. On Windows this becomes a small launcher; the filesystem steps are dropped.
6. **Timing.** Gameplay pacing assumes 60 Hz VLINE (`WaitForVsync` via `/tmp/vsync`) and `kern.quantum=5000`. Locking presentation to 60 Hz (and not the monitor's 144 Hz) is needed, or animations will run fast. Handle this in the backend `swap()`.
7. **Security code.** For a source port, Dolphin/Abyss is not a gate, because the code can be edited. If the build should still *behave* like a keyed machine (coin play, serial number shown in diag), reuse the P1 chip model. Note that the Abyss XOR table needs FreeBSD `random()` bit-exactly (see §3).
8. **Licensing (non-technical).** The code is Midway proprietary (IP now held by Warner Bros. Games). A private preservation build fits this workspace's charter; **distributing binaries or source does not**. The workspace already redacts MPN credentials, and the same care applies to any port tree.

---

## 5. Strategy options

| | A. Cygwin / MSYS2 POSIX layer | **B. Native i686 + thin compat shim (recommended)** | C. Native monolith (olib in-process) |
|---|---|---|---|
| Idea | Keep fork, SysV and FIFOs; Cygwin emulates them (cygserver for SysV) | Keep the multi-process design. Write `tmcompat` (~2–3 k lines) for only the POSIX calls in §3, and swap the HAL | Re-implement the 89 olib calls as direct calls into an in-process dl, sound and input. Games become DLLs or stay as child processes on a much simpler IPC |
| Code churn in games | none | none | none if games stay separate exe's; large if games become DLLs (globals, `exit()`, static state) |
| Struct/ABI risk | **High (LP64)** | None (ILP32) | Low |
| Effort | lowest on paper, but the LP64 audit eats the saving | medium | highest |
| Result | Depends on a Cygwin DLL; fork is slow and odd | Self-contained exe set; closest to the original structure, so easiest to diff against the FreeBSD behaviour | One clean exe; best long-term |
| Verdict | reject | **do this first** | possible later evolution from B |

Under B, the narrowest implementation of each piece is:
- **shm:** `shmget(key)` → `CreateFileMapping("Local\\tm_shm_%x")`; `shmat` → `MapViewOfFile`.
- **msg queues:** a fixed-record ring in a named mapping, plus a named semaphore.
- **FIFOs:** `/tmp/dl/fifo.N` → a named pipe `\\.\pipe\tm_dl_N`, with the shim mapping `open(path)` to it. `select()` over the shim's fds → `WaitForMultipleObjects` on overlapped events.
- **fork+exec** → `CreateProcess`. Each fork-without-exec site (the dl daemons, coinmgr/diag) is rewritten as spawn-with-argument.
- **kill/signal** → a per-pid named event that a shim thread turns into the signal handler call. `SIGKILL` → `TerminateProcess`.

---

## 6. Effort and milestones (estimates for one experienced C/C++ dev)

| # | Milestone | Content | Estimate |
|---|---|---|---|
| M0 | Full media and source extraction | Re-extract the files over 4 MB; merge the OEM and ALPHA10 media into one `T:\t` tree; script it with SHA-256 per guardrail 4 | 2–3 days |
| M1 | `aa.h` reconstruction | Recover the symbols from binary call-site immediates and `libolib` exports; derive the layout from `aa.dat`; round-trip-test by reading the real `aa.dat` | 1–3 wk |
| M2 | Toolchain bring-up | MinGW-w64 i686 + zlib + bzip2 (bundled); `tmcompat.h` macros; compile olib, dl and one game with `-fpermissive` | 1–2 wk |
| M3 | Display backend | `win/swblit.c` implementing the HAL, with SDL2 present + 60 Hz pacing; `dl` up and drawing the menu attract loop | 2–3 wk |
| M4 | IPC shim + process launcher | shm, msg, FIFO, select, spawn and kill; dl supervisor → launcher; menu → game → menu round trip | 2–3 wk |
| M5 | sound + input + coin stub | SDL audio output, mouse/touch → touch shm, keyboard coin/TEST, emulated Dolphin block | 1–2 wk |
| — | **Milestone "first game playable"** | M0–M5 critical path ≈ **5–7 wk** if M1 goes well | |
| M6 | Mass game build-out | All ~60 games and tourngames compile and are smoke-tested; fix dialect and RNG issues | 3–5 wk |
| M7 | diag, hiscore, mgl, menu.ini, audits | Operator menus work; maintenance actions are stubbed | 1–2 wk |
| — | **Total, fully playable** | | **≈ 3–5 person-months** |

The variance mostly comes from M1 (aa.h) and M6 (how much of the dev snapshot is actually broken).

---

## 7. Port vs the planned 86Box route

| | Windows port | 86Box (current plan P1–P5) |
|---|---|---|
| Fidelity to shipped **2.03** | ✗ (3.0x dev behaviour) | ✓ exact binaries |
| Hardest problem | multi-process shim + aa.h | **Rage IIC 3D scaler + VLINE IRQ emulation**, BAR addresses 0xD800/0xEF00 |
| Keyless | trivial (it is our source) | Dolphin device + chip model |
| Runs on modern PCs | natively, resizable, modern touch | inside an emulator, which needs host CPU headroom |
| Shared work | P1 chip model (optional), aa.dat analysis, media extraction | same |

The two routes **share the aa.dat work and the Dolphin knowledge**, so neither is wasted. Recommendation: keep 86Box as the fidelity and preservation route, and treat the port as the "playable anywhere" route. If only one is chosen, the port has **lower technical risk** than emulating the Rage IIC 3D path. The 86Box Rage IIC work (P5) is the most open-ended item in either plan.

---

## 8. Recommended next steps (if pursued)

1. Do **M1 first**, because it de-risks the port and also feeds P1 of the 86Box route: reconstruct `aa.h` from ALPHA10 call sites plus `aa.dat`.
2. Prototype the **display backend in isolation**: a tiny host that loads one `.tm2` and blits it through a ported `MgxBlit` and `ImageDecompress`. This proves the asset path and effects before touching IPC.
3. Then build the shim and launcher (M4). Do not start M6 until menu → game → menu works.
