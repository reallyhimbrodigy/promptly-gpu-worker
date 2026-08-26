# PROMPT V2 A/B — PRE-REGISTRATION

**Written BEFORE the run.** The thresholds below are fixed here so they cannot
be chosen after seeing the result. This project has a standing habit of
explaining an outcome once it exists; pre-registration is the only defence.

---

## The comparison

| | arm A (control) | arm B (v2) |
|---|---|---|
| doctrine | current ~2,000-line prompt | `prompt_v2_editor.MASTER_EDITOR_DOCTRINE` (111 lines) |
| schema | component-major arrays | **beat-major**, flattened by `prompt_v2_schema.flatten_beats` |
| exemplars | none | REF-1 + REF-2 as beat lists (`PLAN_ONLY` first) |
| props | untyped `Dict[str, Any]` | per-component contract, missing ⇒ dropped |
| model | gemini-3.7-flash | gemini-3.7-flash |
| thinking | 2048 (production canonical) | 2048 |
| execution | **SERIAL** | **SERIAL** |

**Serial is not optional.** The concurrency confound is measured: 24-way
`cell.map` produced a 41.7% safe-edit fallback rate that a serial control
refuted at 0/5. Any A/B run concurrently measures the harness.

**Corpus:** the trigger-annotated component corpus (13 sources, brand_copy 7 /
scenes 10 / payoff 5), because a component with no trigger in the source is a
CORRECT decline and scoring it as a defect manufactures a signal. The frozen
goldens are closed as a component instrument.

---

## What is measured, and from where

| metric | source | why not the obvious one |
|---|---|---|
| components **requested** | `component_ledger.requested` | rendered counts cannot tell a decline from our own drop — every such finding this campaign resolved into something WE did |
| components **dropped by us** | `component_ledger.dropped_by_us` + reasons | this is the number that made "0/779 scenes" unreadable for weeks |
| motion density | `prompt_v2_schema.density_of` | placements/sec against the 3.5 target |
| stillness violations | consecutive empty beats > 3.5s | the target that is easiest to pass by accident |
| wall clock | per-cell `wall_s` | the 120s law |
| tokens | request + response | doctrine went 2,000 → 111 lines; the saving must be real |
| `beats[].read` | verbatim | the first look at what the model actually saw |

---

## PRE-REGISTERED THRESHOLDS

### What counts as a WIN
- **Requested placements per source ≥ 2× arm A**, on trigger-bearing sources.
  The measured baseline is `scenes 0/11`, `brand_copy inconclusive`, `payoff
  10/11`. A doctrine change that does not at least double what the planner ASKS
  FOR has not addressed the decline.
- **AND `dropped_by_us` does not rise faster than requested.** Doubling requests
  while doubling our own drops is not a win; it is a louder version of the same
  defect.
- **AND at least one component class comes off zero** — `generated_scenes` is
  the one this campaign was built around.

### What a wall-clock regression may cost
- **Up to +30% p50 wall is acceptable** if the win condition is met. The
  measured editorial p50 is 28.0s (3.7-flash, serial, 2048), so the ceiling is
  **≈36s**. Beyond that the 120s end-to-end law is at risk and the trade must be
  re-argued rather than assumed.
- **A token INCREASE is a red flag, not a cost.** The doctrine shrank by ~95%;
  if arm B costs more input tokens than arm A, the exemplars are the reason and
  `PLAN_ONLY` is already the cheapest mode — that would mean the approach is
  more expensive per call forever, and it should be reported as such.

### What a WORSE result would mean — stated now, because it is easy to explain away
If arm B requests FEWER components than arm A, the honest readings are, in order
of likelihood:

1. **Beat-major is harder for the model than component-major.** Walking a
   timeline and deciding at each step is a different task from filling four
   lists, and it may simply be harder. This is a real finding and would mean the
   schema change, not the doctrine, is at fault — separable by running v2
   doctrine on the OLD schema.
2. **The exemplars anchored it low.** REF-1 shows 6 placements in 40s. If arm B
   lands near 6 regardless of source, the exemplar became a template — the exact
   failure REF-2's retirement as a test input was about.
3. **The doctrine is worse.** Possible, and the least likely given arm A's
   doctrine measurably produced the declines.

**I will not re-run with a different corpus to get a better number.** If the
result is worse, it is reported worse, with which of the three above the
evidence supports.

### Sample size, honestly
13 sources per arm. That is enough to see a 2× effect and **not** enough to
resolve a 20% one. Any delta under ~30% will be reported as **inconclusive at
this n**, not as a direction.

---

## Cost, priced in advance

26 cells (13 sources × 2 arms), plan-only, serial, at the ledgered $0.20/cell:
**≈$5.20.** No render — a render cannot change what the PLANNER emits.
