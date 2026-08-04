# LEAN-SCHEMA A/B — PRE-REGISTRATION

Written before any arm data exists. Deployed `55fe84c`.

## 1. RECONCILING THE AUG-1 ARM-5 NUMBERS

| | arm 5 | control | delta |
|---|---|---|---|
| text_overlays /25s | 0.36 | 0.40 | **−10%** |
| sound_effects /25s | 1.93 | 2.20 | **−12%** |

**I cannot treat those as established, and the reason is power, not doubt about
the measurement.** Per-job variance on the current corpus (792 planned jobs):

| metric | mean /25s | sd | cv | N/arm to detect −10% |
|---|---|---|---|---|
| text_overlays | 0.819 | 1.852 | **2.26** | **8,011** |
| sound_effects | 6.098 | 5.649 | 0.93 | 1,346 |
| **combined decoration** | 8.40 | 7.37 | 0.88 | **1,207** |

Volume is ~79 planned jobs/day, so ~40/day/arm. **8,011 per arm is 200 days.**
Unless the Aug-1 read had an N the traffic cannot have supplied, a −10% move in
`text_overlays` is not separable from noise.

**So the null is not "~10% below control". It is "−10% and 0% are
indistinguishable on that metric at any feasible N."** I am treating Aug-1 as
DIRECTIONAL, not as an established effect — and if its N is on record and large,
that changes and I will say so.

⚠️ **`text_overlays` alone is retired as a decision metric for this A/B.**
cv=2.26 (61% of jobs emit zero) makes it unusable. Replaced by the **combined
decoration metric** — text_overlays + sound_effects + motion_graphics +
tight_cut_overlays + broll_clips — cv=0.88, which is the same families arm 5
names, and is what arm 5 is actually supposed to protect.

## 2. THE EXCHANGE RATE, STATED BEFORE LOOKING

**There isn't one, and that is the answer, not an evasion.** The standing law is
*quality wins over speed in every trade, including reconsidering speed decisions
already made.* So no wall-clock saving buys a confirmed density loss.

That makes this a **non-inferiority test**, not a trade:

- **Non-inferiority margin: −10% relative** on combined decoration. Chosen as the
  largest effect Aug-1 suggested — arm 5 has to beat the thing it was built to
  fix, not merely be uncertain about it.
- **Density within −10% of control** → arm 5 worked; ship it and bank the
  wall-clock, which is then free.
- **Density worse than −10%** → arm 5 did not work. Revert both flags and say so.
- **Wall-clock is never a tiebreaker.** If density is inconclusive, the answer is
  "inconclusive", not "ship it because it was faster."

## 3. TWO N THRESHOLDS, SEPARATELY

| read-out | metric | cv | N/arm | ETA at 40/day/arm |
|---|---|---|---|---|
| **first** | wall-clock, −10% | 0.53 | **438** | **~11 days** |
| second | combined decoration, −15% | 0.88 | 537 | ~14 days |
| **decision** | combined decoration, −10% | 0.88 | **1,207** | **~30 days** |

**No density claim before N=1,207/arm.** The 14-day read can only see a −15%
move; if it shows one, that is already worse than the margin and I revert early.
It cannot be used to declare success.

⚠️ **My wall-clock numbers disagree with the ones in the brief** and I am not
silently substituting mine. Brief: p50 82.6 / p90 194.6. Measured here over 749
jobs with a `stage_timings` total: **p50 321.7 / p90 656.8, mean 364.6,
sd 192.5.** Different cohorts — mine is every planned job, the brief's is
probably a route cut or a different field. The N above uses cv, which is the
scale-free part, so it survives the disagreement; but the absolute figures need
reconciling before any latency claim is made from them.

## 4. THE no-job_id FALLTHROUGH

`_lean_ab_arm()` returns `"control"` when `_ACTIVE_JOB_ID` is empty. If that
population is non-trivial, control is contaminated by a non-random slice.

**Expected size: ~zero on production traffic** — content-studio dispatch always
carries `job_id` because the completion callback keys on it. **That is inference,
not observation**, so it gets a check rather than an assumption:

> **The persisted `stage_timings.lean_arm` must land within 45/55.** At n ≥ 400
> per arm, a split outside that band means the fallthrough is real and control is
> polluted — in which case the arm assignment moves to an explicit random field
> written at dispatch, and this A/B restarts.

That check runs at the first read-out, before any density or latency claim.

## 5. WHAT WOULD MAKE ME REVERT EARLY

- arm balance outside 45/55 at n≥400/arm (design broken)
- combined decoration below −15% at the 14-day read (worse than the margin)
- any completion-rate move off baseline (the same tripwire the speed lane is on)
