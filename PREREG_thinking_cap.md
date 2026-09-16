# PRE-REGISTRATION — capping thinking on the execution half

Written BEFORE the arms run. Fixed here so the read afterwards cannot be the
one the numbers suggest.

## Why now, and why this is a different question than this morning

On run 24 thinking was 139.4s of 908.4s — 15% — and the target was the 308s of
tool-call generation and 156s of Bash, both of which were the agent typing and
running `curl` on signed S3 URLs. The frame server removed that:

    run 24   wall 908.4s   tool_use 308.5s   thinking 139.4s   Bash 155.8s
    run 25   wall 284.1s   tool_use  12.2s   thinking 123.4s   Bash   0.03s

Thinking barely moved in absolute terms (139.4 -> 123.4) and went from 15% of
the wall to **89% of GENERATING** (123.4 of 139.1). Same knob, different target,
because the bigger thing is gone.

## The knob, stated exactly

`MAX_THINKING_TOKENS`, plumbed as `--think-tokens`, read from the Claude Code
binary's own strings. Default 0 = UNCAPPED.

**It is not per-turn and cannot be.** The CLI takes no effort flag, and the whole
conversation is ONE process, so one value governs all 8 turns. Anything reported
per turn below is the EFFECT of a single cap, never a per-turn setting.

## Where the thinking actually is (run 25, n=1)

    turn 7   73.69s   60% of all thinking   <- the review of the composed frames
    turn 6   33.31s   27%
    turn 3   16.41s   13%
    everything else ~0

Turns 1, 2, 4, 5, 8 think for ~0s combined. So a cap can only take time off
three turns, and 60% of the prize sits on the one turn whose job is JUDGEMENT —
the pass that looks at the composed frames and decides whether anything is
wrong. That is the turn most likely to get worse, which is why the quality
observables below are not optional.

## Arms

Same clip, same plan, same brief, same launch command as run 25, tree clean at
`2d0540e` (chatcut_job_app.py sha 76b5fe002e704b03).

    UNCAPPED    --think-tokens 0        2 replicates (run 25 is NOT reused; both are new)
    CAP 4096    --think-tokens 4096     2 replicates
    CAP 1024    --think-tokens 1024     2 replicates

4096 is chosen to bind turn 7 (~7k thinking tokens at the observed rate) and
leave turns 3 and 6 roughly alone. 1024 is chosen to bind all three and show
whether the review breaks — a dose, not a third replicate.

PRICE STATED: 6 ChatCut runs, ~$0.45 each => **~$2.70**.

## The observables, fixed now

SPEED
  1. `wall_s`
  2. `turn_budget.generating_by_block_s.thinking`
  3. per-turn thinking seconds for turns 3, 6, 7

QUALITY — a cap that buys seconds and loses any of these is a LOSS, not a
trade. Quality wins over speed in every trade, including this one.
  4. `chain` hops 3,4,5,6,7 — every one MEASURED. Any drop to FAILED or
     UNCHECKED fails the arm.
  5. `placements.items_added == planned_adds` (11/11)
  6. `visual_pass.state == MEASURED` — it read the source and previewed
  7. `frames_served.state == MEASURED` and the count of preview_timeline calls
     — an agent that stops LOOKING because it has less room to think is the
     failure mode this cap is most likely to cause, and it would show as a
     faster run with a green chain.
  8. `shape.final_text`: does it still name what it checked, or does the
     review collapse into a summary?

## What would make me say the cap works

Thinking seconds down, AND all of 4-7 unchanged, AND the final message still
names the frames it reviewed. Anything else is reported as a loss or as
unresolved — including "faster and still green", if the agent stopped looking.

## What would make me say it does not

Any hop leaving MEASURED; fewer preview_timeline calls with no other
explanation; or a wall saving inside the run-to-run spread, which on this
harness has been large (67.4s to 375.1s across four planner arms on one brief).

n=2 per arm. Two replicates per lever, then stop and report unresolved rather
than adding a third.
