# CLAUDE.md — Midway TouchMaster II preservation / reverse-engineering workspace

>  **STATUS: Phase 10 done (2026-10-29): real platform — Intel BL440ZX + on-board Rage Pro Turbo AGP (Docs/10);
> its own BIOS puts the Rage Pro at D800h and ES1373 at EF00h (Midway's hard-coded bases), diag video test PASS.
> VM `analysis/p10/vm` (OEM) / `vm-a10` (ALPHA10). Ready-to-run rigs: `Rigs/` (Docs/10 §6). Phase 8: both images run keyless in 86Box.** OEM 2.03: graphics, coin play,
> sound. ALPHA10 3.0x: self-provisioned AV 3.0 key, menus, attract (needs the Rage IIC's real 8 MB, now default).
> Branch `touchmaster` of the user's fork (worktree `F:/Claude/86Box-Next2-touchmaster`; local commits, not pushed).
> Side branch `touchmaster-chipinfo` (Docs/06) merged into `touchmaster` as be5573921 (both images re-verified). VMs: `analysis/p3/vm` (OEM), `analysis/p8/vm` (ALPHA10).
> Docs: `TouchMaster.md`, `Docs/00..08`. OEM key: `p1-mkchips.py --serial 100922889 --country 24 --version 1.0`.

## What this workspace is

This is **not a software project with a build pipeline.** There is no compile/lint/test
workflow; never look for one. It is a preservation and reverse-engineering workspace for
**Midway TouchMaster II (FreeBSD 3.2, 2000–2001; OEM 2.03 + ALPHA10 3.0x dev)**. "Work" means inspecting binaries, extracted
images, configs, and (when authorized) producing patched media or an overlay deploy tree.
Authorized preservation / interoperability / security-research context only.

## How to read this file vs. the others

- **`METHOD.md`** — immutable cross-project constitution. Read once at Phase 0. Rules,
  bootstrap protocol, phase template, the decision rules, the anti-mistake checklist.
- **`CLAUDE.md`** (this file) — per-session orientation. The *filled* slots below are the
  fast map of where the project currently stands. Update it at the end of every phase that
  changes a slot (this is a hard rule — see `METHOD.md § Maintenance`).
- **`Docs/NN-*.md`** — the canonical per-phase deliverable. **The only files Claude reads
  end-to-end.** Everything under `analysis/pN/raw|json/` is on-disk evidence Claude greps
  into, never reads in full.

## Hard guardrails (cue cards — rationale in `METHOD.md § guardrails`)

1. Originals immutable; work on copies under `analysis/`.
2. Shell first, Claude last; never read a multi-MB dump into context.
3. One canonical `Docs/NN-*.md` per phase; raw/JSON stays on disk.
4. Every mutation is a reproducible script with input + output SHA256.
5. Falsify your own framing; correct in place, never silently overwrite.
6. Parsimony before elaboration — including for tooling and methodology.
7. Adversarial-miss audit is an EARLY gate (see `METHOD.md § Standard blind-spot checklist`).
8. Plan for mid-execution discovery; surfaces appear out of phase order.

---

# PROJECT STATE (slots — filled by Phase 0/1, maintained every phase)

## System identity (Phase 0)

- OS: FreeBSD 3.2-RELEASE i386 LE, custom kernel (OEM I686-only!), 2000–2001.
- Boot: dangerously-dedicated boot1→boot2→loader→/kernel→rc→rc.local → `/t/video/dl mount &`
  (spawns sound, io, coinmgr→uart, midas) → upgrade scan → `/t/menu/menu`.
- Entry points: `dl.r2c` (display server, drives ATI Rage IIC from userland), `menu`
  (CheckHardwareOK security gate), games `/t/games/*`, `diag` (operator), `mgl` (menu.ini).
- Toolchain: gcc 2.7.2.1 / g++ (-xc++), VSS `$Header: /TouchMaster_II/...`; no packers.
- Storage: `/` UFS1 ro (wd0a 8 GB), `/rw` UFS1 (wd0b 100 MB: aa.dat audits, hiscores), swap wd0f.
  Offline; optional MPN dial-up modem (/dev/cuaa4).

## Artifact buckets (Phase 0)

Different views of the same system at different stages — do not confuse them. Typical roles
(rename/repoint per system):

| Bucket | Path | What it is | Read-only? |
|---|---|---|---|
| Original media | `HDD Images/{OEM,TOUCHMASTERALPHA10}/*` (SHA256 in `analysis/p0/raw/image-sha256.txt`) | Field disk dumps — never modified | yes |
| User docs/dumps | `Info/` — `Rage IIC DUMPS/` (was `BIOS DUMPS/`), `Chip Info/`, `Motherboard Info/` (BL440ZX TPS + BIOS P04/P05), `Rage Pro/` (4× 1002:4742 VBIOS; `p10-roms.py` → `ragepro_agp_*.bin`, SHA `analysis/p10/raw/roms-sha256.txt`) | Copied unchanged into `86box/roms/video/mach64/rage2c_pci_*.bin` (SHA in `analysis/p5/bios/rom-sha256.txt`) | yes |
| Live instance | `86box/` (86Box.exe + cfg + roms) | Emulator; cfg not yet TM-specific | careful |
| P8 VM | `analysis/p8/vm/` (ALPHA10 working copy, SHA in `analysis/p8/raw/mkdisk-alpha10.txt`; chips in `nvr/`, AV 3.0, serial 60000922889, country 29) | ALPHA10 3.0x | disposable |
| P3 VM | `analysis/p3/vm/` (86box.cfg, `tm-oem.img` = first 8.62 GB of OEM, SHA in `analysis/p3/raw/mkdisk-oem.txt`) + exe `analysis/p3/build86/src/86Box-Next2.exe` | Working copy: **booting writes /rw**; regenerate with `p3-mkdisk.py` | disposable |
| Extracted snapshot | `analysis/fs/{OEM,ALPHA10}/{root,rw}` (+ manifests `analysis/p0/raw/*.tsv`) | UFS1 extraction, files >4 MB skipped | yes (forensic) |
| Canonical deploy tree | `Rigs/` (P10): rig exe (no automation/GDB stub) + `roms/` + `TouchMaster-2.03-OEM/`, `TouchMaster-3.0x-ALPHA10/` (trimmed field images, keyed chips, initialised BL440ZX CMOS) + `Run *.cmd`; provenance in `analysis/p10/raw/rig-*` | playing writes /rw: regenerate images with `p3-mkdisk.py` | the deliverable |

## Protection / lock surface table (Phase 0 initial)

| # | Surface | Where | Type (bool-gate / value-bearing) | Cadence (once / every-boot / runtime) | Status |
|---|---|---|---|---|---|
| A | Dolphin board ID @0xD0050 | menu | bool-gate (hard lock) | every menu start | **solved P4**: `dolphin_io` device (ID 0x0102) |
| B | Dolphin chip U9 (dDana) | menu/coinmgr/diag/mgl | value-bearing | every menu start | **solved at data level P1**: C model + `scripts/p1-mkchips.py` accepted by original code |
| C | Abyss key (dEve) | same | value-bearing; absent ⇒ free play | every menu start | **solved P4**: blank → game provisions (verified by original code); pre-built OEM key boots straight to menus |
| D | ~~Rage IIC~~ Rage Pro Turbo AGP (P10) video + I/O 0xD800 + VLINE IRQ | kernel rag, dl.r2c | functional | every boot | **solved P3b+P5**: identity + pinned I/O; scaler existed but 3D-side scissors were 13-bit (fixed to 14) → sprites render. P5b: ALPHA_START fades + TEX_AMASK masking in scaler; real Rage IIC PCI BIOS 113-61801-101 (user dumps). **P10:** real chip = on-board Rage Pro (4742) of the Intel BL440ZX, emulated (GT-B core + identity + AGP); BL440ZX BIOS assigns D800h itself |
| E | ES1371 @ I/O 0xEF00 | kernel est, sound | functional | every boot | **P3b: solved** (fixed_io EF00 + fixed 86Box unaligned-word bug that caused an est_intr storm); `p3-patchio.py` unused fallback. **P10:** BL440ZX BIOS assigns the on-board ES1373 EF00h natively |
| K | Emergency-restore DIP wipe (`dl`: Dolphin present && 0x60 bit7==0 → rm -rf /rw/…) | dl | destructive side effect | every boot | added P3 because seen in dl.cc; P4 device must default bit7=1 |
| L | `dl mount`: fsck -py /rw fails → `newfs /dev/rwd0b` | dl | destructive side effect | every boot | added P3; only hurts the disposable working copy |
| H | tm.cksum / master.cksum / signature | diag file test | informational | operator | N/A as gate |
| I | `secfail` in dl | dl.r2c | latent sabotage | runtime | **falsified P2**: only store is `=0` in both builds, address never taken |
| J | Abyss version gate (2.03 `mgl`: gid 39–40 need AV≥3) | /t/system/mgl | bool-gate | — | **dead code P2**: mgl never executed; live generator is libolib (ungated) |

> Keep the original wrong guesses visible with a strikethrough + "reclassified Phase N
> because …". The history of *why a surface was misread* is as valuable as the answer.

## Phase ledger — maintained every phase

| Phase | Deliverable | Outcome |
|---|---|---|
| 0 — bootstrap & plan | `Docs/00-plan.md`, `TouchMaster.md` | Identified system, full boot chain, HW list, protection fully documented from ALPHA10 source |
| 2 — 2.03 confirmation | `Docs/02-oem-binaries.md` | 2.03 = `dolphin.o.good` (instruction-identical exc. ISA-only dout/din); same menu gate; ProgramAbyss writes v1.0; secfail inert; no date bombs |
| 1 — Dolphin spec + chip model | `Docs/01-dolphin.md` | C board/AT88SC153 model (`analysis/p1/src`) passes original dolphin.c harness (0 fails); Python key generator byte-identical; found dChris no-return, dAndy dead/broken |
| 3 — 86Box platform | `Docs/03-platform.md` | **Milestone: menu shows "Dolphin I/O card not found!"** (P3b: Rage IIC ID, BAR pinning, ES137x unaligned-word fix on branch `touchmaster`). First pass: OEM kernel boots on BF6/PII-350 (automation build of user's 86Box-Next2, out of tree); dmesg pulled from RAM; 0/16 BIOSes give 0xD800/0xEF00; gate is behind dl→needs Rage IIC ID; corrected P0 (rag IDs, rag_read 2.86 s timeout) |
| 4 — Dolphin device | `Docs/04-dolphin-device.md` | `dolphin_io` ISA board (P1 model unchanged) in 86Box: blank chips → diag init + ProgramAbyss → attract (images pass original dolphin.c); Canada key → straight to menus, no factory restore. Missing sprites = 3D scaler (P5) |
| 5 — video | `Docs/05-video.md` | Missing sprites = 86Box 3D/scaler read SC_RIGHT as 13-bit (0x1FFF → −1, everything clipped); 14-bit like the 2D engine → menus/games render like Midway's own screen dumps. Found via env-gated scaler trace + alpha histograms (removed) |
| 6 — Chip Info (side session) | `Docs/06-chip-info.md` | ATI docs confirm the scaler alpha-mask rule; fixed GT-B FIFO_STAT and 8.12 scaler increments on branch `touchmaster-chipinfo` (eab533273, not merged) |
| 7 — coins & sound | `Docs/07-coins-sound.md` | Free Play was an aa.dat setting; coins arrive on the board's electronic inputs (64h) → added lines A–F, 80 ms pulses, `ioboard pulse` automation; paid game played, credit deducted; AC'97 gain table 2 dB→1.5 dB steps (+10 dB, game sound audible) |
| 8 — ALPHA10 3.0x | `Docs/08-alpha10.md` | 3.0x keeps glyph/image cache above 4 MB → TM's Rage IIC had 8 MB (default now 8, 92ed542d7); 3.0x diag needs serial 6xx/9xx + country (29 USA DBV); self-provisioned AV 3.0 key verified by original code; boot script waits for 86Box exit (disk-lock lost an HDD entry) |
| 9b — diag findings | `Docs/09-keygen.md` §4 | AT88SC153 Answer-To-Reset added (diag Dolphin I/O test: 3455AA85; harness still 0 fails). **Correction:** diag (2.03+3.0x) passes only chip 4742 and both dl.r2c were built `-DRAGEPROAGP` → production video = **Rage Pro Turbo AGP 8 MB**, not Rage IIC |
| 9 — key generator | `Docs/09-keygen.md` | Tools → TouchMaster Key Generator (serial generate/edit, game's 54-country list, version) + `ioboard keys` automation; C port byte-identical to p1-mkchips (1080/1080); end-to-end re-key of OEM accepted by original code |
| 10 — BL440ZX + Rage Pro | `Docs/10-bl440zx-ragepro.md` | 86Box's BL440ZX gets its on-board Rage Pro Turbo AGP (`mach64_ragepro_onboard`; card `mach64_ragepro` with 4 user VBIOSes) + ISA via NLX riser; system BIOS supplies its own embedded VBIOS (3.086); **unmodified BIOS assigns D800h/EF00h** → TM II board = BL440ZX; OEM + ALPHA10 menus, diag Motherboard Test all PASS, coin + sound OK. Not emulated: Rage Pro-only 3D setup engine (unused by TM) |
| side study — Windows port | `Docs/windows-port-feasibility.md` | Feasible (~3–5 person-months, native i686 + compat shim); found `/t/aa/aa.h` missing from source (342 symbols to reconstruct) |

## Abandoned branches index — maintained as branches die

| Branch / phase | Why abandoned | Anything still live from it? |
|---|---|---|
| — | — | — |

## Tooling baseline (Phase 0)

- Static: Python 3.14 + capstone + pefile; own scripts `scripts/{ufs1,elfsym,strs,p0-*,p1-*}.py`.
  No binutils on host. WSL Ubuntu has gcc/g++ 15 + gcc-multilib (no 32-bit libstdc++ headers →
  build C++ with `-m32 -nostdinc++ -fno-exceptions -fno-rtti`, link with gcc). Call WSL from
  PowerShell, not Git Bash (path mangling).
- Emulation: 86Box build in `86box/` (has ATI 3D Rage II+, Rage 128, ES1371/1373, 3M MicroTouch).
  Needs P6 CPU for OEM kernel; Dolphin device does not exist yet. User's source: `F:/Claude/86Box-Next2`
  (fork; never PR upstream). P3 automation build: `scripts/p3-build86box.sh` (out of tree, restores
  `.build-number`). Drive VMs with `scripts/p3-auto.py` (token in VM dir; ONE client at a time — close
  the socket *file* too); GDB stub starts CPU stopped → send RSP `c` to port 12345; dmesg via
  `scripts/p3-msgbuf.py`. Use `boot -sv` at the loader for probes (never mounts /rw).
- User may supply: Dolphin/Abyss chip dumps, 86Box source tree, real-HW BIOS/PCI layout.

---

## What you cannot / must not do here

- No `make`/`npm`/`pytest` — nothing to build or test.
- Do not start/stop the live instance (`86box/`) from this session unless the user says so. The P3 VM
  (`analysis/p3/vm`, own exe) is ours to run.
- Do not copy provenance/README/checksum sidecars into a deploy tree.
- Do not treat "missing system tool" as corruption until you've checked for an
  intentional lockdown/strip step (see `METHOD.md § Bootstrap 0.4`).
