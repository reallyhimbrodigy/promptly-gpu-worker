# DOES LENGTH HURT QUALITY? — test design, pre-registered, HELD on approval

The one version of the claim nobody has measured. Cost and latency are settled
(prefix cached at 0.25×; wall-clock r=0.59 vs OUTPUT not input; `prompt_token_count`
flat across arms). Quality is not.

## The design problem, stated up front

**A "materially shortened" prompt that keeps all capability does not exist.**
Five measurements agree the lossless ceiling is ~1.1–1.3×, so the largest honest
lossless cut is ~2,605 tok (6.4%) — not material by any reading.

To make a *material* cut you must remove capability, which confounds the test:
plans change because instruments vanished, not because the prompt got shorter.
The design handles that by removing **one whole family** and then measuring
**everything except that family**.

## Arms (4 × 16 frozen clips = 64 PLAN_ONLY runs, no render)

| arm | prompt | Δ | purpose |
|---|---|---:|---|
| **A** control | full | — | baseline |
| **A2** control replicate | full | — | **the noise floor. Non-negotiable** — last run measured control-vs-control em-Jaccard at **0.516**, i.e. two identical configs agree on only ~52% of emphasis words. Without A2 every result is unreadable. |
| **B** lossless-max | −worked examples (1,834) −emit passes (421) −thumbnail (350) | −2,605 (−6.4%) | the largest cut that removes no capability |
| **C** material | B + the entire MG catalogue entries (5,743) | −8,348 (−21%) | Zac's claim at a size that could plausibly matter |

## Pre-registered reads — locked BEFORE the run

Measured on **cuts, zooms, captions and pace only.** MG metrics are excluded
throughout, because they are trivially zero in arm C and would fake a difference.

1. `events/25s` excluding MG (pace)
2. zoom-type distribution + variety (is the mix less concentrated?)
3. `caption_keywords` per 25s
4. emphasis density (moments per 25s)
5. em-Jaccard vs control, **judged against the A-vs-A2 noise floor**

## Verdict rule — also pre-registered

- **Arm B or C beats control on (1)(2)(3)(4) by more than the A-vs-A2 band**
  → length hurts quality. Shortening is justified and the size workstream reopens.
- **Within the noise band** → length is not the problem. Close honestly.
- **Below control** → the removed prose was load-bearing; length is doing work.

An arm that merely *differs* from control proves nothing — differing is what a
0.516 noise floor does for free.

## Cost — stated both ways, per the ledger's own lesson

64 tasks, cpu=8 / 32 GiB, PLAN_ONLY, no render.

- **~$5.3** by the harness's per-clip figure (the same figure I inherited for the
  96-task run and reported as `$8`)
- **possibly ~$10** recomputing from the resource request (~19,200 container-seconds;
  at cpu=8/32 GiB the memory-time term is large and the per-clip figure does not
  obviously cover it)

**Treat ~$10 as the number to approve against, not $5.3.** The $8 I quoted before
was a docstring estimate I did not derive, and that is exactly the Rule-8 gap.

## Status

**HELD.** Session spend is $8.06, already past the $5/session cap, and the freeze
lift named speed and errors. Needs an explicit GO naming this run and its ceiling.

## What I'd say before it runs

I expect **"within the noise band"** — every mechanism measured so far says the
prompt's length is carrying capability rather than diluting it, and the WHY-class
result (96% of rationale has no code guarantee and is what lets the model
generalise) points the same way. Recording that prediction here so the result is
a test and not a story told afterwards.

If it comes back inside the band, the honest close is: **length is not the
quality problem**, and the prompt-side value is discrimination, not size.
