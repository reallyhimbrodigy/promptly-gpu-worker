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
