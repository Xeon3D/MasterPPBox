# 00 — Bootstrap & plan (Phase 0)

Canonical findings: `../TouchMaster.md`. This file is the plan only.

## Goal
Run Midway TouchMaster II (OEM 2.03 image; ALPHA10 3.0x as reference/source) under 86Box with no
physical Dolphin board / Abyss key, coin play optional, free play acceptable as first milestone.

## Surface table (initial — expect additions)

| # | Surface | Where | Type | Cadence | Status |
|---|---|---|---|---|---|
| A | Dolphin board presence (ID word 0x0100, FPGA ≥2 @ 0xD0050) | `menu` CheckHardwareOK | bool-gate, hard lock | every menu start | open |
| B | Dolphin chip U9 (dDana: fab code, magic AEC0, checksum) | `menu`,`coinmgr`,`diag`,`mgl` (static dolphin.o) | value-bearing (serial, mfg date, country) | every menu start | open — self-provisions if blank (-1) |
| C | Abyss key (dEve: magic 50AA, serial pairing, version, country) | same | value-bearing; absence ⇒ free-play only | every menu start | open — self-provisions if blank (-1) |
| D | Rage IIC video (PCI 1002:4756, 3D scaler, VLINE IRQ, I/O 0xD800 hard-coded) | `/kernel` rag, `dl.r2c` | functional dependency | every boot | open — biggest risk; P3: ID gate confirmed (4756/4742 only), VLINE emulated, scaler not |
| E | ES1371 sound (I/O 0xEF00 hard-coded) | `/kernel` est, `sound` | functional dependency | every boot | P3: attaches; no BIOS gives 0xEF00/0xD800 → pin BARs or patch |
| F | MicroTouch on COM1 (blocking handshake) | `io` | functional dependency | every boot | P3: 86Box answers all of io's commands (static check) |
| G | CPU class (OEM kernel I686-only) | `/kernel` | boot gate | every boot | **solved P3** (PII-350 on BF6 boots) |
| K | Emergency-restore DIP wipe in `dl` | `dl` | destructive | every boot | added P3: P4 must default 0x60 bit7=1 |
| L | `dl mount` newfs on fsck failure | `dl` | destructive | every boot | added P3: working copy is disposable |
| H | tm.cksum/master.cksum/signature | `diag` file test | informational only | operator-triggered | **N/A as gate** |
| I | `secfail` sabotage in dl | `dl.r2c` | latent | runtime | falsified P2 (inert in 2.03 and 3.0x) |

## Phases (easiest → hardest)
1. **P1 Dolphin spec + chip model** — register map, AT88SC153 state machine in Python, replay
   `dBetty/dDana/dChris/dEve` against it (port from `t/coinmgr/dolphin.c`). Deliverable `Docs/01-dolphin.md`.
2. **P2 2.03 binary confirmation** — disassemble 2.03 `menu` CheckHardwareOK, `dolphin.o` copy,
   `GetMasterPalEntry` LUT, `dl.r2c` secfail sites. Deliverable `Docs/02-oem-binaries.md`.
3. **P3 86Box platform** — P6 CPU machine, trimmed 8.62 GB HDD image (copy), ES1371, MicroTouch COM1,
   find BIOS giving 0xD800/0xEF00 or script-patch the constants. Milestone: boot reaches
   "Dolphin I/O card not found!". Deliverable `Docs/03-platform.md`.
   **P3 outcome:** kernel boots; no BIOS matches; the milestone is behind `dl` (needs `/dev/rag0` → Rage IIC
   ID 4756). Revised: **P3b** = Rage IIC identity + fixed I/O (BAR pinning, rec.) in a branch of the user's
   86Box fork → `dl`/`io`/`sound` up → menu reaches the Dolphin check. Then P4, P5 as before.
   **P3b done:** "Dolphin I/O card not found!" reached with the unmodified image (Docs/03 §10).
4. **P4 Dolphin device in 86Box** — implement ISA device + NVR chips; boot through `diag init`/ProgramAbyss.
   **Done** (Docs/04): both self-provisioning and pre-built-key boots reach the game menus.
5. **P5 Rage IIC video** — extend Mach64 GT emulation per `r2c/*.c`; or alternative `dl.r128` build path.
   **Done** (Docs/05): scaler already emulated; one-field fix (3D scissor width) → correct graphics. `dl.r128` path not needed.

## Blind-spot owners (METHOD § Standard blind-spot checklist)
- linked-but-dead vs live: P2 · cadence: P2 · conditional ISA/PCI paths: P1 · removable-media
  upgrade scan: P3 · packing/anti-debug: done (none) · anti-VM/integrity: P2 (secfail) · time/counter bombs: P2.

## What the user may need to supply
- Whether a real Dolphin/Abyss dump exists (would allow exact pre-built chip images).
- Preferred 86Box source tree (this build already has Rage II+, Rage 128, ES1371/1373, MicroTouch).
- Decision: patch kernel I/O constants vs. make 86Box place BARs.

## Mid-execution discovery clause
New surfaces found during execution are expected; they get appended to the table above and to
`CLAUDE.md` with "added Phase N because …", never silently.
