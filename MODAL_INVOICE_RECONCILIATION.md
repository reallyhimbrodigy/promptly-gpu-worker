# INVOICE RECONCILIATION — the model vs the actual `[Law 1]`

**Source: `modal billing report --start 2026-08-01 --end 2026-09-01 --csv`.**
I previously reported that the Modal CLI had no billing command. **That was
wrong** — it exists; the installed client (1.2.6) predates it. Pulled with an
**isolated** venv client (1.5.4) so the global client `deploy.sh` depends on was
not touched mid-campaign.

## 1 — THE ACTUAL

| | |
|---|---|
| **Aug 1 → Aug 15 total** | **$878.10** (15 days, mean $58.54/day) |
| `promptly-gpu-worker` | **$829.37 — 94.4%** |
| all ephemeral apps (cert-*, plan-*, mem-*) | $48.73 — 5.6% |
| **Aug 12–15 (current regime)** | **$106.01 = $35.34/day** |
| resource split | **CPU 73.6% / Memory 26.4%** |
| GPU | **~$0.00** |

**The ~$87/day figure was REAL but STALE.** Aug 4 was $110.55, Aug 7 $86.27 —
that era matched. The current regime is **$35.34/day**. My inability to reproduce
it from the code was correct *and* the figure was correct; they described
different weeks. Possibility (1) — stale — is confirmed.

## 2 — THE MODEL vs THE ACTUAL

| | $/day | share of actual |
|---|---|---|
| fixed (warm surfaces) | 5.74 | 16% |
| marginal (orchestrator container lifetime) | 4.06 | 11% |
| **model total** | **9.80** | **27%** |
| **ACTUAL** | **35.34** | 100% |
| **RESIDUAL** | **25.54** | **72%** |

## 3 — WHERE THE RESIDUAL IS — localised by resource ratio

The invoice implies **1,985,496 core-s/day** and **4,202,703 GiB-s/day** →
**2.12 GiB per core**. That ratio is a fingerprint:

| container | cpu | mem | **GiB/core** |
|---|---|---|---|
| orchestrator `run_pipeline_bg` | 16 | 12 GiB | **0.75** |
| `render_burst` | 32 | 64 GiB | **2.00** |
| fanout class (`modal_app.py:972`) | 16 | 32 GiB | **2.00** |
| prewarm cls | 0.125 | 4 GiB | 32.00 |

**The bill's shape is the cpu:mem=2.0 burst/fanout class, NOT the orchestrator.**
My model counted the burst as `render_s × 32` — its *reported render seconds* —
and counted the fanout at **zero**.

If the bill is burst-class time: `$35.34 / $0.000561/s` = **62,964 burst-seconds
per day = ~335 seconds of burst container per job**, against a **reported render
p50 of 4.5–9.5s**. That gap — dispatch, payload upload, queueing for a container,
cold start, scaledown — is billed at 32–48 cores and is invisible in
`stage_timings`.

**This is derived from the invoice, not yet directly observed** — which is
exactly what the double-hold instrument now measures.

## 4 — L1/L2 RE-SIZED, INVOICE AS DENOMINATOR

| lever | acts on | $/day | **share of the $35.34 bill** |
|---|---|---|---|
| **L1** — orchestrator cpu=4 while waiting | orchestrator only ($5.66/day measured) | ~2.66 | **7.5%** |
| **L2** — release the orchestrator during the burst | the double-hold, ~335s/job × 16 cores | **~14.8** | **~42%** |

**L2 is the lever, and by a wide margin.** The orchestrator sits at cpu=16 doing
nothing for the entire blocking `.remote()` call — and that call is ~335s, not
the ~5–10s the render reports. My earlier ranking sized L2 off *reported render
seconds* and therefore undercounted it by ~35×.

**Neither ships before the instrument confirms 335s.** The number is inferred
from a ratio; `burst_double_hold` measures it directly, per job, in core-seconds.

## 5 — WHAT MY MODEL GOT WRONG, NAMED

1. **Counted only the orchestrator.** The fanout class contributes and was never
   in the model at all.
2. **Used reported render seconds for the burst** instead of the wall clock of
   the blocking call. `stage_timings.render` is the burst's *own* view; it cannot
   see its own dispatch, queue or cold start — all billed at 32 cores.
3. **Measured only completed jobs with full envelopes** (n=277). Failures burn to
   the timeout; they were excluded from the denominator that priced a render.

All three push the same direction — the model **undercounts** — which is the
dangerous direction for a cost model.


---

# ADDENDUM 2026-08-15 — the denominator re-measured, and the two investigations converge

## The 600s UNS wait is a RENDER process, not a Modal container

One read settles it: `SOURCE_WAIT_MS = 600_000` (`lib/source-presence.js:30`),
`waitForSource` is called at `dispatch-to-modal.js:1208`, and the Modal spawn is
at 1285/1377 — **after** it. The failure path says so in its own log line:
*"failing WITHOUT spawning Modal"*.

**So the 600s UNS wait costs ~$0 of Modal spend.** It is a Node async wait on
Render, which bills per instance, not per awaiting promise.

**This re-ranks the UNS fix: it is a USER-EXPERIENCE and correctness problem
(users wait ten minutes and are then refunded), NOT a cost lever.** Anyone
sizing it as ~$7/day of Modal was sizing the wrong thing — I would have, without
this read.

It also fixes the denominator below: the **80 jobs with no `worker_started_at`
never spawned Modal**, so they must be EXCLUDED from container-seconds.

## The denominator, re-measured

My earlier "5.1%" was wrong — it multiplied jobs by a flat 30s wall. Real
per-job lifetimes:

| denominator | $/day | vs $25.94 orchestration |
|---|---|---|
| `worker_started_at → end`, workers only | 5.66 | 21.8% |
| **`created_at → end`, workers only** | **9.12** | **35.2%** |
| `created_at → end`, ALL jobs | 12.91 | 49.8% |

The middle row is the honest one — the widest row double-counts the 80 jobs that
never spawned.

| term | $/day | share |
|---|---|---|
| measured job lifetimes | 9.12 | 35.2% |
| + 45s scaledown tail × 161 jobs/day | 1.71 | 6.6% |
| + 11s cold start × 161 jobs/day | 0.42 | 1.6% |
| **accounted** | **11.25** | **43.4%** |
| **RESIDUAL** | **14.69** | **56.6%** |

## THE CONVERGENCE — the residual and the envelope-loss class are the same population

The envelope-loss cohort is **180 jobs / 3 days = 60/day** whose worker never
reached its terminal write. If those containers are HUNG rather than gone, they
burn their container cap while writing nothing:

| assumed cap | added $/day | total vs invoice |
|---|---|---|
| 600s | +8.50 | 76% |
| **900s** | **+12.76** | **93%** |
| 1200s | +17.01 | 109% |

**A ~900s hang closes the residual to 93%** — and 900s is not an arbitrary
number in this system: it is the p99 wall and the 15-minute fallback timer.

**Stated as a FIT, not a measurement.** The cap was chosen to match the residual,
which is exactly the reasoning that must not be trusted on its own. But it makes
one prediction that is already being tested: **a hung worker emits NO
`worker_envelope_write` event at all**. At n≥100, the ratio of completions to
envelope-write events measures the hang rate directly.

**If it holds, the ranking changes completely:**

| lever | worth |
|---|---|
| **fix the worker hang** | **~$440/mo** + 38.6% envelope loss + the 304s/904s latency tail |
| L1 (Lumen path) | +$72/mo |
| prewarm / validator | $74.19 / $75.33 cycle-to-date |

One defect would account for the largest cost line, the largest telemetry hole,
and the worst latency class simultaneously. That is worth more than every
container-sizing lever combined, and it is why L1 stays uncommitted.


## DISPATCH_UNREACHABLE IS A DIFFERENT CLASS — do not collapse the labels

Checked directly, since a shared 904s tail made them look alike:

| | DISPATCH_UNREACHABLE | envelope-lost |
|---|---|---|
| n / distinct users (since Aug 1) | 12 / 8 | 180 / 161 (Aug-12 cohort) |
| **`modal_call_id`** | **0/12 — Modal was NEVER reached** | present |
| `worker_started_at` | **0/12** | 180/180 |
| result shape | full error envelope + `refund` | `{lifecycle_push_v1}` and nothing else |
| status | 11 failed, 1 completed | all completed |
| **overlap** | **1 job** | |

**They are opposites, not variants.** DISPATCH_UNREACHABLE fails *before* a
container exists; envelope-loss happens *after* a render succeeds. And because
0/12 ever held a container, **DISPATCH_UNREACHABLE contributes ~$0 to the cost
residual** — its 1420s p90 tail is the Render-side 600s source wait, which the
read above already proved costs nothing on Modal.

Collapsing the labels would have merged a 12-job dispatch fault into a 180-job
worker fault and pointed the fix at the wrong layer.
