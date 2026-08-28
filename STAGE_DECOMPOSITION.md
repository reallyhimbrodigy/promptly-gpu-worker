# STAGE DECOMPOSITION — MEASURED 2026-08-28

**Read it with `./run_modal.sh query_stage_picture_app.py --since <date>` (~$0.005,
one CPU container, no renders). Regenerate before planning off it.**

Cohort: 267 completed organic jobs, 2026-08-26 onward.
Routes: std-editorial 130 · moodreel 93 · minimal_speech_uncut 31 · hype 9 · minimal 4

## THE NUMBERS

| stage | p50 | p90 | n |
|---|---|---|---|
| **render** | **75.1s** | **223.0s** | 267 |
| normalize_transcribe_upload | 56.1s | 158.4s | 130 |
| → edit_plan *(nested inside)* | 50.6s | 138.8s | 130 |
| → → gemini_call *(nested inside)* | 18.0s | 29.7s | 130 |
| fps_normalize | 9.6s | 32.8s | 130 |
| upload_export | 5.4s | 13.0s | 130 |
| hls | 1.9s | 5.5s | 137 |
| download | 1.3s | 2.2s | 130 |
| **TOTAL** | **116.3s** | **355.8s** | 267 |

**THESE STAGES OVERLAP AND CANNOT BE SUMMED.** normalize contains edit_plan
contains gemini_call — verified structurally (normalize spans handler.py
t=40546..43390; edit_plan's `_mega_t0` spans 42636..42731, entirely inside).
116.3s is the measured wall, NOT the column sum. Treating a containing window as
a peer term inflated normalize into an apparent "second-largest independent
stage" for weeks.

## WHAT THIS CORRECTS — three board numbers that were stale

| board said | measured today | status |
|---|---|---|
| gemini_call ~82s | **18.0s** (`gemini-3.7-flash`, 130/130 jobs) | flip is LIVE; −78% already banked |
| HLS 72s → 1s "largest uncontested win" | **1.9s p50** | copy-mode ALREADY LIVE. Win already taken. |
| normalize ~29s unexplained fixed term | **5.5s residual** | dissolved — normalize is ~90% edit_plan |
| "five minutes end to end" | **116.3s p50** / 355.8s p90 | 5min is the TAIL, not the median |

Planning against the stale HLS number cost a directed session on a win that was
already banked. That is what this file exists to prevent.

## WHERE THE TIME ACTUALLY IS

**Render: 75.1s of a 116.3s p50 (65%), and 223s of the 355.8s p90.** Every other
stage is now small. Render is the only lane with a latency lever left.

`fps_normalize` (8.9s p50) is the largest pool task and the only substantial
work OUTSIDE edit_plan. It stays on the planner (ruled 2026-08-27; its only
measurement is at cpu=8 and inferring cpu=4 behaviour from it repeats the
shape-inference habit).

## STANDING RULE THIS FILE ENFORCES

**Regenerate before planning.** Every number here has a date and a command. A
decomposition without a date is a decomposition that will misdirect a session —
this one already did.
