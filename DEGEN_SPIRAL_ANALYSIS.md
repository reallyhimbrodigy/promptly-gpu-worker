# DEGEN SPIRALS — the re-rolls work, and the cost is the missing edit_plan time

## THE THREE ANSWERS

**1. Rate: 59 of 361 jobs (16%)** carry a non-zero `gemini_wasted_degen` in my
window (2026-07-28 →). Lower than the 25% quoted, on a different denominator.

**2. DO THE RE-ROLLS SUCCEED? YES, decisively.**

| | completed | failed | landed on safe-edit fallback |
|---|---|---|---|
| spiralled (59) | **56 (95%)** | 3 | 3 (5%) |
| clean (302) | 270 (89%) | 32 | 1 (0%) |

**A spiralled job is MORE likely to deliver than a clean one.** The abort +
re-roll machinery works. This is not a quality problem wearing a success — the
quality cost is 3 jobs that fell back to safe-edit.

**3. THE COST IS LATENCY, AND IT IS THE MISSING edit_plan TIME.**

| stage | spiralled | clean | delta |
|---|---|---|---|
| **edit_plan** | **253.2s** | **109.0s** | **+144.2s (+132%)** |
| gemini_call | 101.3s | 64.6s | +36.7s |

🔑 **That +144s is almost certainly the "~130 SECONDS LIVE INSIDE edit_plan AND
NOBODY KNOWS WHAT IT IS."** The unexplained edit_plan gap and the degen spirals
are the same phenomenon. Median wasted-degen is 87.3s, but the stage costs +144s
— so the spiral costs roughly 57s MORE than the aborted stream itself, which is
the re-roll.

Total burn: **6,658 seconds — 1.85 hours** of Gemini compute across 361 jobs.

## WHAT IT IS **NOT** — three hypotheses tested and refuted

| hypothesis | spiralled | clean | verdict |
|---|---|---|---|
| long/script-like vibes | 71 chars median, 7% multi-line | 47 chars, 4% | **weak** — >1000 chars is 1.8× but n=3 vs 9, noise |
| long sources | 20.2s median | 19.2s | **no difference** |
| prose-heavy output | 1,592 chars | 1,681 chars | **0.95× — refuted** |

The prose test is the one I most expected to land, given the known
`why`-repetition root cause. It did not.

## ⚠️ WHY I CANNOT NAME THE PROMPT WEAKNESS

**The aborted stream is discarded.** `gemini_wasted_degen` records SECONDS and
nothing else — not the tier that fired, not the shape (phrase-loop vs
vocab-collapse vs self-argument), not a sample of the text. `gemini_tokens` is
present in `stage_timings` but reads 0 on every job.

So my prose measurement is of the **successful re-roll**, not the spiral. I am
measuring the survivor and calling it the failure. No stored-data analysis can
characterise these spirals, and "it is a prompt signal" is currently untestable.

**This is the same class as two other gaps found today:** the light routes store
no transcript, so their safety assumption is unfalsifiable; the aborted stream is
discarded, so the spiral's shape is unfalsifiable. **We keep throwing away
exactly the evidence needed to diagnose the failure.**

## THE ONE CHANGE THAT WOULD MAKE THIS DIAGNOSABLE

Persist, on abort: **the tier/signal that fired, and the first ~500 characters of
the aborted stream.** Tiny, no PII beyond what the plan already stores, and it
turns an untestable hypothesis into a one-query answer. Without it the next
person repeats this analysis and reaches the same wall.

## Method

`video_jobs.result.stage_timings.gemini_wasted_degen > 0` as the spiral marker,
2026-07-28 onward, n=361 with the counter present. Vibe strings joined from
`vibe_input`; prose volume summed over `edit_rationale`, `video_identity`,
`notes`, `video_plan.*` narrative fields, `transitions[].why` and
`emphasis_moments[].viewer_feeling/why_emphasis`.
