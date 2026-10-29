# METHOD.md — reverse-engineering / preservation constitution

Cross-project, system-agnostic. Read **once** at Phase 0; it rarely changes between
projects. Distilled from a completed 13-phase kiosk RE effort — including its mistakes,
which are designed out below. Pair with the lean `CLAUDE.md` template (per-session
orientation + project state slots).

## How to start a new project

1. Copy `CLAUDE.md`, `METHOD.md`, `Docs/`, and `scripts/` into the new workspace root.
   Set `<SYSTEM NAME>` and the bucket paths in `CLAUDE.md`.
2. Create `analysis/`. Snapshot + checksum the extracted image *before touching it*.
3. Run **§ Bootstrap Protocol** below. Its output is `Docs/00-plan.md` plus every filled
   slot in `CLAUDE.md`.
4. Proceed phase by phase using **§ Phase template**. Update `CLAUDE.md` at the end of
   every phase that moves a slot.

Systems differ wildly in layout, OS, era, and protection scheme. **Nothing here names a
specific mechanism.** The method is the constant; the findings are the variable.

---

## The guardrails (and the failure each one prevents)

1. **Originals are immutable.** Checksum the image; work only on copies under `analysis/`.
   Extracted snapshots are forensic — changes there do not propagate and corrupt your
   ground truth.

2. **Shell first, Claude last.** Bulk file work (`file`, `find`, `strings -a`, `grep -ria`,
   `rabin2`, `readelf`, `objdump`, `binwalk`, entropy scans, small Python over raw bytes)
   is zero-cost and produces the evidence Claude actually reasons over. Claude time is
   the scarce resource. Burning context on data a `grep` answers is a failure mode.

3. **One canonical deliverable per phase** (`Docs/NN-*.md`) is the only thing Claude reads
   end-to-end. `analysis/pN/raw/` and `/json/` are grep targets, never full reads. Keep
   `CLAUDE.md` lean for the same reason — it is reloaded every session.

4. **Every mutation is a reproducible script.** Patches/transforms live in
   `analysis/pN/sh/apply-*.py`, take the original as input, and **print input + output
   SHA256**. Never hand-edit a binary. A 12-byte patch you can't regenerate from a script
   is technical debt the moment you write it.

5. **Falsify your own framing and record why the wrong turn was wrong.** Expect early
   claims to be corrected by later evidence. When they are, fix `CLAUDE.md` and the plan
   *in place* with a visible "reclassified Phase N because …" — do not silently overwrite.
   A future session that re-walks a hidden dead path is a process failure.

6. **Parsimony before elaboration.** Before a deliverable asserts a baroque mechanism
   (custom crypto oracle, hardware co-signing, multi-stage challenge), it must contain
   one paragraph: *"the boring explanation is X; the cheap experiment that rules X out
   is Y"* — and Y must have been run. The elaborate theory is usually the expensive way
   to be wrong. **This applies to tooling and methodology too**, not only findings.

7. **The adversarial-miss audit is an EARLY gate.** Before you trust any dependency graph
   or declare a surface understood, explicitly enumerate what the cheap scan **cannot
   structurally see** (see § Standard blind-spot checklist). On the prior project, three
   hard surfaces were found *after* the analysis was declared complete because this
   audit ran too late.

8. **Don't over-promise an analysis-only structure.** A plan that says "read-only until
   phase N, then patch" will meet a system whose hard problems only surface during
   execution. Structure the plan so that *new surfaces discovered mid-execution are
   expected*, not a process violation.

---

## Standard blind-spot checklist

What the cheap scan cannot structurally see. Apply at Bootstrap 0.5 (assign each item an
owning phase) and as the adversarial check (guardrail 7) of every phase:

- linked-but-dead code vs. *live* code (needs `.text` xref, not symbol presence);
- runs-once vs. runs-every-boot vs. runtime-revalidated (needs call-site cadence);
- conditionally-dispatched paths only reachable with certain inputs/hardware;
- code/data loaded over network or from removable media at runtime;
- packed/encrypted regions, self-modifying code, delay-loaded imports;
- anti-debug / anti-VM / integrity self-checks;
- time bombs / counter bombs / hardware-state bombs.

Generalize per system. The list is template-level; the owning phases are per-project.

---

## Bootstrap Protocol (Phase 0) — first contact with an extracted image

Goal: from a cold image, produce `Docs/00-plan.md` and fill `CLAUDE.md`'s slots, **cheaply**
(shell, not Claude reads). Each step is a question to answer with tools — adapt the
commands, keep the questions.

**0.0 Freeze ground truth.** `find <image> -type f | wc -l`; record a manifest with sizes
and hashes (`find … -printf … | sort`, or a hash manifest). Snapshot any live instance.
Everything after this is on copies.

**0.1 Identify the system.** `file` on boot blocks / kernels / a sample of binaries;
`rabin2 -I` / `readelf -h` for arch/endianness/OS; look for version banners
(`strings | grep -Ei 'v[0-9]|build|copyright|20[0-9][0-9]'`). Fill *System identity*.

**0.2 Map the tree cheaply.** Largest files, most-recently-modified files, directory
shape (`du`, `find -printf '%T@ %s %p'`). Separate **third-party redistributables**
(runtimes, codecs, DB engines, OCXs — out of scope, name and drop them) from **bespoke
code** (the actual target). The bespoke set is usually small.

**0.3 Detect anti-analysis up front.** Entropy scan every bespoke binary with a
deterministic tool (`ent`, `binwalk -E`, or a small Python Shannon-entropy script;
high uniform entropy ⇒ packed/encrypted). Grep for
packer/anti-debug/anti-VM/checksum-of-self markers. `binwalk` firmware blobs. **This
decides whether static-only is viable** — record it before planning anything.

**0.4 Trace the boot → app chain and the lockdown layer.** Find the autostart mechanism
(init scripts, services, shell-replacement, registry Run keys, `autoexec`-equivalents).
Identify what *launches* the application vs. the application itself. Note any intentional
**lockdown/strip step** (deletes recovery tools, swaps shells) so "missing tool" is never
later misread as corruption.

**0.5 Enumerate protection surfaces AND blind spots.** List candidate lock/binding
surfaces (hardware bindings, dongles/keys, license files, server checks, signature
verification, time/feature gates). Then — same pass, equal weight — walk the
§ Standard blind-spot checklist and assign each item an owning phase. **This is
guardrail 7 made concrete.**

**0.6 Write the plan.** `Docs/00-plan.md`: goal, the surface table, phases easiest→hardest,
the blind-spot owners from 0.5, what the user must supply, and an explicit "new surfaces
found during execution are expected and get appended" clause. Fill all `CLAUDE.md` slots.

---

## Phase template

Each phase is depth-first on one surface/question, easiest→hardest. Shape:

1. **Scope** — the one question. If a prior phase reframed the surface, restate it.
2. **Evidence** — shell/scripts → `analysis/pN/raw/` then `/json/`. Reusable scripts under
   `scripts/` named `pN-<step>.{sh,py}`; reuse a prior phase's scanner unchanged when the
   shape fits. Batch independent shell calls in parallel.
3. **Adversarial check** — apply guardrail 7 (and § Standard blind-spot checklist) to
   *this* surface; apply guardrail 6 if the conclusion is elaborate.
4. **Deliverable** — `Docs/NN-<surface>.md`, canonical, the only file read end-to-end.
   State falsified prior framing explicitly.
5. **Reproducible artifact** (if it produces a fix) — `analysis/pN/sh/apply-*.py` with
   SHA256s; originals untouched.
6. **Maintain** — update `CLAUDE.md` slots, phase ledger, abandoned-branches index.

A phase that merely confirms prior framing still gets a one-line ledger entry; check
explicitly rather than skipping the update.

---

## Anti-pattern checklist (the prior project's actual mistakes — do not repeat)

Items roll off as their guardrail proves itself in the field. Keep the list short.

- ❌ Deep "what did we miss" audit run *after* sign-off → 3 hard surfaces found late.
  ✅ Run it at Bootstrap 0.5 and as step 3 of every phase (guardrail 7).
- ❌ An elaborate protection theory written up canonically, then demolished by the
  boring explanation a phase later. ✅ Guardrail 6 paragraph is mandatory before
  write-up.
- ❌ A whole phase + scripts produced nothing and sat unlabeled in `analysis/`.
  ✅ Maintain the abandoned-branches index; dead trees are self-labeling.
- ❌ Orientation doc grew to ~37 KB, reloaded every session, fighting its own token
  discipline. ✅ Lean `CLAUDE.md`; detail in read-once `METHOD.md` + per-phase `Docs/`.
- ❌ "Read-only until phase 5" framing; 6 of 8 hard surfaces lived in later phases.
  ✅ Guardrail 8 — plan for mid-execution discovery as the norm.
- ❌ *(2026-05)* A helper tool's own design grew toward ~5000 LOC of modes, batching,
  stats, bench, citation engine, splice, selftest, and RAG — a guardrail-6 violation in
  the tooling itself. ✅ A tool should own only what's irreversible after the fact (e.g.
  context isolation, attribution, fail-loud). Cross-project lesson: parsimony before
  elaboration applies to the tooling as much as to the analysis.

---

## Maintenance

Update `CLAUDE.md` at the end of every phase whose findings move a slot (system identity,
buckets, surface table, ledger, abandoned branches, tooling). The per-phase `Docs/`
deliverable is canonical detail; `CLAUDE.md` is the index that must never drift behind
it. If a phase reframes a surface, the reframing (with "reclassified Phase N because …")
belongs in `CLAUDE.md` in summary form with a pointer to the deliverable. `METHOD.md`
itself changes only when a *cross-project* lesson is learned — append it as a new
guardrail + anti-pattern, dated.
