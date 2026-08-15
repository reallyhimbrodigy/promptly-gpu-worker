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
| s/scene | **p50 17.9s** (nearest-rank) · p90 23.5s · min 15.6s · max 32.43s | 10 |
| $/scene | **$0.140** (1 image) | 10 |
| **alpha / hero** | **0 / 2** — failure rate **1.00** | 2 |
| $/hero-scene | **UNMEASURED** — nothing succeeded to price | — |
| images written | **12** | files on disk |
| **billed calls** | **14** = 10 scene + 4 alpha (2 attempts x 2 calls) | reconciles to $1.96 |
| run total | **$1.96** (ceiling $2.00, respected) | 14 x $0.14 |

### Two conventions, both stated because both were wrong once

**Percentiles are NEAREST-RANK**: k = ceil(p·n), value = sorted[k-1], no
interpolation. With n=10 the p50 is the **5th smallest = 17.9s**. The harness's
own printed p50 is **18.73s** — a different convention on the same data, not a
different measurement. The ledger uses nearest-rank throughout and says so; where
earlier documents quote 18.7s they are quoting the harness.

**Billed calls exceed images written.** A call that exhausts its retry ladder on
429 **still bills and writes no file** — so 12 files but 14 billed calls. Only
`billed_calls` reconciles against the run total, and the ledger now asserts that
reconciliation (`14 × $0.14 = $1.96`) so the two can never drift apart silently
again. The first version of this ledger reported `total_images_billed: 12`, which
did **not** reconcile against $1.96.

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

## What the alpha failure actually blocks — a correction

A hero scene needs **two sequential calls** (white background, then black,
differenced into a matte). Leg 1 lands; leg 2 arrives while the quota is still
recovering and starves through all four retries. Single scenes survive 429s
because one ladder is enough — the two-call path must win **twice in a row**, and
against a **2 req/min** limit it never does.

**CORRECTION.** I first wrote that this blocks Component C (text-behind-subject).
It does not. C is text behind the **user's real subject**, which
`SEGMENTATION_SPIKE.md` settles as **RVM** — a deterministic temporal matte with
**zero image generation**. The alpha path mattes a *generated* subject, which is
a **B-family** concern.

So what the alpha failure blocks is **hero/generated-subject compositions**, not
C. C's real blockers are the spike's three unpriced items — latency (an *editing*
effect, so §4.1 gives it no carve-out), cost (a second GPU app per job), and
concurrency. Quota is not among them.

## The exact limit

`GenContentImageGenRequestsPerMinutePerProjectPerBaseModelGlobal` = **2
requests/minute** on `promptly-479218`, confirmed via the Cloud Quotas API. That
is *below* the ~3.4/min a purely serial workload achieves, which is why serial
calls 429'd — the measurement and the documented limit agree.

Increase to **60/min** filed 2026-08-15 as `promptly-image-gen-60rpm`
(trace `d0e2fa72-b5fc-4633-9ad1-8ab89f048852`), pending Google review. No owner
click was required.
