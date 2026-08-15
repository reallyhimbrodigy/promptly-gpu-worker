# FIRST LIGHT — the run ledger `[§6.1]`

**2026-08-15 · `lumen_first_light_app.py` · Vertex AI `gemini-3-pro-image` ·
project `promptly-479218` · $1.96 of a $2.00 ceiling.**

`first_light_ledger.json` is the auditable artifact: **every call**, its
artifact, bytes, tokens, seconds, dollars, and how many 429 retries it absorbed.

## Why this file exists

Build-lane runs never touch production rows, so these numbers leave no trace in
`video_jobs` — there is nothing for JUDGE to audit unless the run commits its own
ledger. And it must be **measured in-run**: `result` loses its envelope on 38.6%
of completions (180/466, 161 users), so any figure read back from it is cut from
a corrupted population. The harness times and prices each call **at the call
site**.

## The envelope

| | measured | denominator |
|---|---|---|
| scenes ok | **10 / 10** — failure rate **0.00** | 10 |
| s/scene | **p50 18.73s** · min 15.6s · max 32.43s | 10 |
| $/scene | **$0.140** (1 image) | 10 |
| **alpha / hero** | **0 / 2** — failure rate **1.00** | 2 |
| $/hero-scene | **UNMEASURED** — nothing succeeded to price | — |
| run total | **$1.96** (ceiling $2.00, respected) | 12 billed images |

**One correction recorded rather than buried:** the first pass of this ledger
reported *12 scenes at 12/12*. It counted the alpha path's successful first leg
(`al_*`) as a scene. Scenes are `fl_*` (one call each); `al_*` are **legs** of a
two-call alpha attempt. The corrected split is 10 scenes and 2 alpha attempts,
which matches the harness's own printed envelope exactly.

## The limit is a RATE limit, not a spend cap

This is the answer to "is quota headroom money or design?" — **it is design.**

Evidence, all from this run:

1. **Every call ran serially** and 429s still occurred. Uncontended latency
   ~17.9s means a serial ceiling of **~3.4 requests/min**; the limit binds below
   that.
2. **The 429s decayed across the retry ladder** — attempt 1: 6, attempt 2: 5,
   attempt 3: 2. They *clear with time*.
3. **A spend cap does not recover in 5–8 seconds.** It fails all four attempts,
   persistently, until the budget resets or is raised. 13 of 15 429s resolved
   inside the ladder.

**The lever is a Vertex quota-increase request — an approval, not a purchase.**
Nothing here needs a spend decision.

## Component C is blocked here, and only here

A hero scene needs **two sequential calls** (white background, then black,
differenced into a matte). Leg 1 lands; leg 2 arrives while the quota is still
recovering from leg 1 and starves through all four retries. Single scenes survive
429s because one retry ladder is enough — the two-call path has to win **twice in
a row**, and at this quota it never does.

So **text-behind-subject is blocked on rate headroom, not on code.** The
segmentation work itself is unaffected.
