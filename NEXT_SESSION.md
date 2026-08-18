# NEXT SESSION — the queue, in order

**LIVE NOW**
- worker **v557 = `fafe171`** (Modal-verified) — the mask's twin fixed
- server **`1e4b59f`** — verified at `promptly-ae0u.onrender.com/api/health`,
  gate receipt 41/41 @ 15:07:53Z. `markJobFailed` routes through the invariant.
- worker HEAD **`dd15778`** — the v2 build, committed, gate 399 green, **dark
  and unwired**. Not deployed; it selects nothing until step 2.

---

## 1. `invariant_heal` on a real denominator — a READ, first

The guard went live **2026-08-18T15:07:53Z**. Snapshot at handoff:

```
jobs since guard live : 5
invariant_heal fires  : 0
rows failed WITH video: 0
```

**5 is not a denominator.** Do not report 0 as proven until a few hours of
traffic have passed (the rate has been ~180 jobs/day).

- **non-zero** ⇒ post-fix exceptions are still reaching that path; the TypeError
  was one trigger among several and the guard is doing real work.
- **zero on a real denominator** ⇒ v557 closed the trigger and the guard is
  insurance rather than a running repair.

One query: `completion_delivery=eq.invariant_heal & updated_at >= 15:07:53Z`.

## 2. The v2 wiring — the only thing between the build and the A/B

`prompt_v2_*.py` are built and verified; **nothing selects them.** Wire into
`generate_edit_gemini`:

- when `prompt_v2_editor.v2_enabled(input_data)`, assemble the system
  instruction from `build_v2_system_instruction(catalog_block, exemplar_block(mode))`
  — the catalog is PASSED IN, not rewritten, so the A/B measures doctrine and
  not a rebuilt pipeline;
- select `BeatMajorPlan` as the response schema instead of the component-major one;
- on return, `flatten_beats(plan, ledger=(_ledger_requested, _ledger_dropped))`
  **before** anything counts `motion_graphics` — that ordering is what keeps
  `handler.py:28540`'s equality true by construction.

Flag default OFF. Production must stay byte-identical with it unset.

## 3. The A/B — per `PROMPT_V2_AB_PREREGISTRATION.md`

Serial (the concurrency confound is measured and real), trigger corpus,
3.7-flash, thinking=2048, ~$5.20 for 26 cells, plan-only.

**Capture `read` from EVERY cell, verbatim** — that is the first look at what
the model actually saw, and it is the deliverable even if the numbers disappoint.

Report **requested vs dropped-by-us from the component ledger**, never rendered
counts. Thresholds are already fixed in the pre-registration; do not re-choose
them after seeing the result, and do not re-run on a different corpus to get a
better number.

## 4. `dispatch-to-modal.js:751` — the misattribution

All 55 had `worker_started_at` AND `modal_call_id` set. **Zero** were pre-spawn
throws. 39 users were told "We had trouble reaching the render service" about a
service we reached, whose worker ran. Class name AND user copy.

Predicate: `worker_started_at ∧ modal_call_id` ⇒ a worker death whose completion
never arrived, not an unreachable dispatcher. (Class is stale — 0 since Aug 16
11:40Z — so this is a copy/labelling fix, not an outage.)

## 5. The multimodal boundary — start with one line

`CHAT_ARCHITECTURE_SPEC.md` (content-studio). **First: re-scope
`empty_ai_reply`** — today `!reply.trim()` 502s an image-only reply, so every
other part of §1 ships broken without it. Then media in, then §3's pacer, then
non-text out, then §2 tool calling.

---

## Open filings

- `FILING_EMPHASIS_OUTSIDE_VIDEO.md` — Step-C precondition. `emphasis_moments[4]
  derived t=73.217s is outside video` on a **74.8s** source. Cheap first move:
  make the message name the bound it compared against.
- `held/echo_outro/BLOCKER.md` — built, mirror test 14/14, blocked on an owner
  call about render-only types across three gates.
- `FILING_CANON_MIRROR_CONSOLIDATION.md` — four surfaces, low priority.
- `FILING_TYPED_MG_PROPS.md` — superseded in part by `prompt_v2_schema.py`.

## Corrections carried forward — do NOT re-derive

- **"props empty 210/210" — WITHDRAWN.** It read the render-side projected shape
  out of `edit_recipe`, not the model's plan. Historical rate is UNMEASURED.
- **"41.7% fallback rate" — WITHDRAWN.** That was `cell.map` concurrency,
  refuted by a serial control (0/5).
- **"terminal-invariant was never deployed" — WITHDRAWN.** It WAS on origin/main;
  my checkout was 19 commits stale. The real defect was narrower: deployed but
  `markJobFailed` never called it. Fixed in `1e4b59f`.
- **§4's 3.5/sec is NOT placement density.** It counts every motion kind; REF-2
  is 0.14 placements/sec. Do not put them in the same table.
- Step A's real numbers, serial at production's canonical thinking=2048:
  3.7-flash **2.50×** faster at p50 (70.1s → 28.0s), **cut count identical 5/5**,
  marginally less decorative.

## The lesson that cost the most this session

**Three separate cohorts read as live defects purely because the measurement
window straddled a fix.** What resolved all three was not a better diagnosis —
it was cutting each cohort at its deploy boundary before believing any of it.
