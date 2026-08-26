# PROMPT V3 — BEAT-MAJOR **WITH PURPOSE** — PRE-REGISTRATION

**Written BEFORE the run, 2026-08-24.** Thresholds are fixed here so they cannot
be chosen after seeing the result. This project has a standing habit of
explaining an outcome once it exists; pre-registration is the only defence.

**Supersedes `PROMPT_V2_AB_PREREGISTRATION.md`, which is left intact.** V2 ran
and returned a real result: arm B silent on 6 of 10 sources, schema unable to
express scenes. Its thresholds are not reused — see §0.

---

## 0. Why this is a NEW arm and not a re-run

| | v2 beat | v3 beat (arcads shape) |
|---|---|---|
| identity | a **placement anchor** keyed on `word_index` | a **time-boxed unit** with an intent |
| fields | `word_index` · `read` · `place[]` | `purpose` · `t_start`/`t_end` · `treatment[]` · `read` |
| question asked of the model | "at which word does something go?" | "what is this stretch FOR, and how long is it?" |

**Different object, different failure modes**, so the v2 thresholds do not
transfer. One of them is actively dead: v2's win required `generated_scenes` to
come off zero, and that component was later shown to be **unmeasurable in that
arm**. Carrying it forward would import a dead condition into a live
pre-registration, which is worse than having no condition at all.

**The anchor law is unchanged and non-negotiable.** Every timing that reaches
the renderer derives from a word index through the timing authority
(`word_time_s` / `word_frame`). `t_start`/`t_end` are the model's *reasoning*
about duration; they are **resolved to word indices before flattening** and a
beat whose bounds cannot be resolved to words is DROPPED, counted, and reported.
A second clock has been paid for twice here and does not get a third chance.

---

## 1. The comparison

| | arm A (control) | arm B (v3) |
|---|---|---|
| doctrine | current production directive | `prompt_v2_editor` doctrine + purpose/duration beat framing |
| schema | component-major arrays | beat-major **with `purpose` + `t_start`/`t_end`** |
| exemplars | none | REF-1 + REF-2 as beat lists, `PLAN_ONLY` |
| model | gemini-3.7-flash | gemini-3.7-flash |
| thinking | 2048 | 2048 |
| execution | **SERIAL** | **SERIAL** |

**Serial is not optional.** Measured: 24-way `cell.map` produced a 41.7%
safe-edit fallback that a serial control refuted at 0/5. Any A/B run
concurrently measures the harness.

**Corpus:** the trigger-annotated component corpus, now including the `broll`
trigger added 2026-08-24. **Trigger-bearing sources only, per component scored.**
A component with no trigger in the source is a CORRECT decline.

---

## 2. What is measured, and from where

| metric | source |
|---|---|
| components **requested** | `component_ledger.requested` (nested, per kind) |
| components **dropped by us** | `component_ledger.dropped_by_us` + reasons |
| **beats emitted** | `len(plan.beats)` |
| **bare-beat rate** | beats with `treatment: []` ÷ total beats |
| **silent-source rate** | sources where the arm emitted NOTHING — v2's actual failure |
| **unresolvable beats** | beats whose `t_start`/`t_end` did not map to a word index |
| wall clock | per-cell `wall_s` |
| tokens | request + response, cache hit/miss stated |

Rendered counts are **not** the metric. They cannot distinguish a model decline
from our own drop, and every such finding this campaign resolved into something
WE did.

---

## 3. PRE-REGISTERED THRESHOLDS

### WIN — all three must hold
1. **Silent sources ≤ 1 of 13.** Arm B emits beats on at least 12 of the 13
   trigger-bearing sources. *Primary condition, aimed squarely at v2's measured
   failure: silence on 6 of 10. A shape that cannot speak cannot be judged on
   what it says.*

   **AMENDED 2026-08-24, BEFORE ANY CELL RAN** — no data existed when this was
   changed, which is the only time a pre-registration may be touched. It read
   "≤ 10%", and at n=13 that percentage HAS NO RESOLUTION: 1 silent source is
   7.7% (pass), 2 is 15.4% (fail). There is no outcome between them, so the
   percentage implied a precision the sample cannot deliver and would have
   invited an after-the-fact argument about where 10% really sits. A count says
   the same thing and cannot be re-litigated.

   **THE RESOLUTION LIMIT, STATED:** this threshold can distinguish 0-1 silent
   from 2+. It CANNOT distinguish a 10% silence rate from a 15% one. If the
   result lands at exactly 2, that is a FAIL by the pre-registered rule and also
   **within the noise this n can resolve** — both facts get reported, and the
   honest follow-up is more sources, not a re-reading of this number.
2. **Requested placements ≥ 1.5× arm A** on trigger-bearing sources. Lower than
   v2's 2× deliberately — v2 asked for a doubling and got silence; the bar that
   matters first is *emitting at all*.
3. **`dropped_by_us` does not rise faster than `requested`.** Doubling requests
   while doubling our own drops is a louder version of the same defect.

### REPORTED, NOT THRESHOLDED
- **Bare-beat rate.** The arcads shape's claim is that purpose+duration makes
  restraint *legible*. I do not know the correct number and inventing one would
  be fake precision. But a bare beat **must carry a `read`** — a bare beat with
  no stated reason is indistinguishable from an omission, and that distinction is
  the entire point of the field.
- **Beat-duration distribution.** Whether the model uses duration as a real
  variable or emits uniform beats. Uniform beats mean `t_start`/`t_end` is
  decoration.

### COSTS
- **Wall clock: up to +30% p50 is acceptable** if the win holds. Editorial p50 is
  28.0s serial, so the ceiling is **≈36s**. Beyond that the 120s law is at risk
  and the trade must be re-argued, not assumed.
- **A token INCREASE is a red flag, not a cost.** `PLAN_ONLY` is already the
  cheapest mode; if arm B costs more input tokens, the exemplars are the reason
  and the approach is more expensive per call forever.

---

## 4. What a WORSE result would mean — stated now, because it is easy to explain away

In order of likelihood, and each is separable:

1. **Beat-major is harder for the model than component-major.** Walking a
   timeline and deciding at each step is a different task from filling four
   lists. v2's silence on 6/10 is evidence for this, and v3 changes the beat's
   *identity* rather than fixing the difficulty. **Separable** by running the v3
   doctrine on the OLD component-major schema.
2. **`purpose` is the wrong axis.** If beats are emitted but `purpose` is
   near-constant (everything labelled `claim`), the enum is not carrying
   information and the shape reduces to v2 with extra fields.
3. **The exemplars anchored it low.** If arm B lands near the exemplar's
   placement count regardless of source, the exemplar became a template.
4. **Duration is decoration.** Uniform `t_start`/`t_end` spacing means the model
   is not reasoning about time and the arcads shape did not transfer.

**I will not re-run with a different corpus to get a better number.** If the
result is worse it is reported worse, naming which of the four the evidence
supports.

---

## 4b. REPEAT COUNT — amended 2026-08-24, before the cross-arm run

**Every source runs arm B N times, and silence is a RATE per source, not a bit.**

WHY, MEASURED: the same source, same arm, same doctrine, same prompt-token count
answered with **8 beats and 14 requested components**, then twenty minutes later
returned **0 beats** — `safe_edit: false`, `status: plan_only`, one Gemini call,
no error. The model simply emitted an object with no beats.

**Silence is non-deterministic.** That breaks the primary threshold as written:
"≤ 1 of 13 silent" scores one draw per source, so a stochastic 30% silence rate
and a shape that is broken on 30% of sources produce the SAME number and point
at opposite fixes. v2's headline "silent on 6 of 10" was one draw per source
too — it may have been measuring variance, and nothing in that run could have
distinguished the two.

**The threshold is therefore restated on the repeated measure:**

> A source counts as SILENT only if it returns no beats on **a majority of its N
> runs**. Sources that are silent on some runs and not others are reported
> separately as **FLAKY**, with the per-source rate, and a flaky population is a
> RELIABILITY finding — not evidence about beat-major as a shape.

N is fixed at **5 for the reliability probe** (2 sources, arm B, ~$2.00) and the
cross-arm run's N is set from what that probe shows: if per-source silence is
0/5 or 5/5, N=1 is defensible and the cross-arm run costs ~$5.20 as priced; if
it is intermittent, N must rise and the cross-arm cost rises with it. **That
number is not chosen after seeing the cross-arm result.**

---

## 5. Sample size, honestly

13 sources per arm. Enough to see a 1.5× effect and a silence rate; **not**
enough to resolve a 20% difference. Any delta under ~30% is reported as
**inconclusive at this n**, not as a direction.

## 6. Cost, priced in advance

26 cells (13 sources × 2 arms), plan-only, serial, at the ledgered $0.20/cell:
**≈$5.20.** No render — a render cannot change what the PLANNER emits.


---

## FIELDS THIS PRE-REGISTRATION READS — added 2026-08-25, after the stall defect

§4's four "worse result" readings all draw on `v2_counts`, which `flatten_beats`
computes and handler, until now, only PRINTED. They were therefore readable
inside a harness run and UNREADABLE from production — the same defect as the
stall experiment's `preserved`, one step removed. A conclusion that can only be
drawn inside a container is not a production reading, and §4.2 ("`purpose` is
near-constant") and §4.4 ("uniform `t_start`/`t_end` spacing") are exactly the
two that would have gone unanswerable had arm B ever run on real traffic.

`v2_counts` is now persisted on the job row. On arm A it is `None` — honest, and
distinguishable from "arm B ran and emitted nothing", which is itself §4.1.

```reads
stage_timings.v2_counts
component_ledger
stage_timings.gemini_tokens
stage_timings.editorial_model
```

§4b's repeat count (silence as a RATE per source, not a bit) is a property of
the RUN DESIGN, not of a field, and is not declarable here.
