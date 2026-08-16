# MODAL COST LEVERS — measured against the INVOICE `[Law 1, Rule 5, Rule 6]`

**Round: TRACK D, 2026-08-16. Design + measurement only. No code changed, no
deploy, no Modal spend** (billing/rates are read-only API calls; every other
number is a local computation over a Supabase read).

---

## 0 — THE RATE CARD, VERIFIED (not assumed)

Pulled directly with `modal billing rates` (isolated client 1.5.4 at
`/tmp/modalbill_venv`, so the global client `deploy.sh` depends on was untouched):

```
CPU     $0.0473 / core / hour  =  $0.00001314 / core-second
Memory  $0.0080 / GiB  / hour  =  $0.00000222 / GiB-second
GPU     L4 $0.80/hr, A10G $1.10/hr, ...   (GPU spend on this app: $0.00)
```

Both match the values handed to this round. **They are now sourced, not
inherited.**

**No hidden CPU-only region multiplier.** The `region="us"` comment at
`modal_app.py:1275` claims a 1.5x tier multiplier. That is testable without
spending anything: for any container, `CPU$ / Memory$` is *independent of
runtime* and therefore fingerprints the cpu:mem shape. Thirteen ephemeral apps
in the August invoice (`cert-auth-ping`, `promptly-secret-readback`,
`probe-stuck-renders-s3`, and ten one-shot `promptly-gpu-worker` runs) land at an
implied **1.00-1.01 GiB/core** against a predicted 1.00 for their declared shape
— a **1% match**. A CPU-only 1.5x multiplier is **REFUTED**. (A *uniform*
multiplier on both dimensions would still be invisible to this test, but it would
push the reconciliation below from 88% to 59%, so it is inconsistent with the
data.)

---

## 1 — THE INVOICE (clean cohort, stated first)

**Cohort: Aug 09-14, 6 full days, `promptly-gpu-worker` only.**
Why clean: pre-dates the `burst_double_hold` instrument deploy (first event
2026-08-15T07:43Z); contains no agent GPU probe days. **Aug 15 is EXCLUDED** — it
spikes to $66.85 with CPU at $55.72 against a flat $11.13 memory, a shape that
does not match production traffic, and it carries L4/L40S/A10G-tagged
ephemerals.

| | |
|---|---|
| **invoice** | **$38.00/day** (CPU $26.95 = 70.9%, Memory $11.05 = 29.1%) |
| daily spread | 44.29 / 42.75 / 33.35 / 38.42 / 29.25 / 39.95 |
| **daily sd** | **$5.73/day (CV 15.1%)** |
| implied | 2,051,517 core-s/day, 4,971,663 GiB-s/day, **2.42 GiB/core** |
| Modal-reaching jobs | **202.3/day** |
| measured orchestrator span | 30,568 s/day (mean 153.9 s/job) |

The handed-down "$35.88/day, CPU 72.5%/Mem 27.5%" is **confirmed** — it is the
Aug 11-14 window ($35.24/day, mem 27.9%). The "last 3 days" framing is now stale:
Aug 13-15 reads $45.35/day because Aug 15 is contaminated.

---

## 2 — FIXED vs MARGINAL, measured by regression on 143 hours

App-level is the finest granularity the billing API offers (`Object ID` = app;
`--tag-names` exists but **no function in `modal_app.py` declares tags**). So the
decomposition is done by regressing **hourly invoice dollars** against **hourly
measured orchestrator job-seconds**, fitting CPU and Memory separately.

Cohort: 143 hours (Aug 09-14 minus the single $8.04/h outlier hour 2026-08-14T20,
5x the next highest; both fits are reported so the outlier's leverage is visible).

| fit | intercept ($/day) | slope ($/job-second) | R2 |
|---|---|---|---|
| total, all 144h | 17.55 | 0.00066895 (2.82x orch) | 0.726 |
| **total, 143h (outlier excluded)** | **20.56** | **0.00055798 (2.36x orch)** | 0.574 |
| CPU only, 143h | 13.35 | 0.00043367 | 0.619 |
| Memory only, 143h | 7.21 | 0.00012431 | 0.375 |

```
ALWAYS-ON FLOOR   $20.56/day   95% CI [$18.36, $22.76]   = 54.1% of the invoice
MARGINAL SLOPE    $0.00055798 +/- 0.0000317 per job-second = 2.36x +/- 0.26 orch
```

Sanity bracket: the **cheapest single hour observed** was $0.3894/h = $9.35/day
equivalent — and that hour still carried load, so the true floor sits between
**$9.35 and $20.56/day**. The fitted value is the upper end of that bracket.

---

## 3 — WHAT THE FLOOR *IS* — solved, then named

The floor implies **11.76 always-on cores and 37.6 always-on GiB**, i.e.
**3.19 GiB per core**. That ratio is a fingerprint, and only two declared classes
sit above it:

| class (from `modal_app.py` decorators) | cpu | GiB | GiB/core |
|---|---|---|---|
| `PromptlyWorker` dispatcher | 8 | 32 | **4.00** |
| `PromptlyPrewarmWorker` | 0.125 | 4 | 32.00 |
| `render_burst` | 32 | 64 | 2.00 |
| `render_chunk_fanout` | 16 | 32 | 2.00 |
| `run_pipeline_bg` | 16 | 12 | 0.75 |
| `PromptlyValidator` | 4 | 2 | 0.50 |
| `PromptlyDiagnoseUpload` | 2 | 1 | 0.50 |

`PromptlyWorker` **alone overshoots memory by 25%**, so the floor must contain it
*plus* something low-GiB/core. Solving the two-equation system:

```
PromptlyWorker dispatcher   97,730 container-s/day  = 1.13 containers ALWAYS-ON  -> $17.22/day
PromptlyValidator           58,622 container-s/day  = 0.68 containers ALWAYS-ON  ->  $3.34/day
                                                                          sum   -> $20.56/day
```

**INFERENCE, not measurement — and the honest caveat:** two equations cannot
uniquely determine six unknowns. Substituting idle `run_pipeline_bg` for the
validator also fits (dispatcher 1.10 always-on + 15,783 orchestrator-s/day of
unmeasured idle). **What is robust across every decomposition that fits is the
dispatcher term at ~1.1 containers held 24/7.** `PromptlyPrewarmWorker` is
*excluded* by the arithmetic: adding it forces a negative coefficient.

### The line item, in plain terms

`modal_app.py:1272` says it itself:

> *"under SPAWN_MODE=1 this cls is a pure DISPATCHER — run_job spawns
> run_pipeline_bg and returns in ms; it never renders."*

**8 cores and 32 GiB, held 24/7, to accept an HTTP POST and call `.spawn()`.**

| | $/day | $/yr |
|---|---|---|
| one always-on `PromptlyWorker` (8c / 32 GiB) | **15.23** | **5,557** |
| ...of which CPU (8 cores) | 9.08 | 3,315 |
| ...of which memory (32 GiB) | 6.14 | 2,243 |
| **resize to cpu=2 / 4 GiB** | 3.04 | — |
| **SAVING at 1.00 container** | **12.19** | **4,448** |
| **SAVING at the fitted 1.13 containers** | **13.79** | **5,033** |

That range — **$4,448 to $5,033/yr** — sits inside the $4,450-$5,586/yr that this
round was told L1/L2 were worth. **The annualised prize was real; it was attached
to the wrong container.**

**NOT A FLIP.** The 32 GiB is deliberate: it keeps the dormant `SPAWN_MODE=0`
sync-render fallback "degraded-but-survivable rather than an OOM/timeout
landmine", and `@modal.enter` re-imports handler (opencv/numpy/genai/deepgram)
under `enable_memory_snapshot=True`. **Sizing it needs the same discipline inc2
used: measured peak RSS of that container, then generous headroom.** The cgroup
sampler pattern already exists (`modal_app.py:735-772`). That measurement is the
next round's first job, not this round's recommendation.

---

## 4 — RECONCILIATION: bottom-up vs the invoice

| term | $/day | share | source |
|---|---|---|---|
| orchestrator, measured job spans | 7.24 | 19.1% | 30,568 s/day @16c/12GiB, `started_at`->`completed_at` |
| + cold start 11 s/job | 0.53 | 1.4% | in-body handler import |
| + `scaledown_window=45` s/job | 2.16 | 5.7% | `modal_app.py:690`, decorator literal |
| + ThreadPool exit tail <=30 s/job | 1.44 | 3.8% | documented + **UNFIXED** (`project_threadpool_exit_tail`) |
| + `render_burst` container | 1.64 | 4.3% | 2,916 blocked-s/day @32c/64GiB |
| **subtotal — job-attributable** | **13.00** | **34.2%** | |
| + always-on floor | 20.56 | 54.1% | fitted intercept, §2 |
| **MODEL TOTAL** | **33.57** | **88.3%** | |
| **INVOICE** | **38.00** | 100% | |
| **RESIDUAL** | **4.44** | **11.7%** | named below |

**The prior model explained 35-43%. This one explains 88.3%.** The difference is
entirely the always-on floor, which the prior model never had a term for.

**Independent cross-check on the marginal rate:** bottom-up gives
$0.00042541/job-second (1.80x orch); the regression slope is $0.00055798 (2.36x
orch). **The two methods agree within 24%** — they are built from disjoint
inputs (decorator literals + job timestamps vs. hourly invoice dollars), so the
agreement is meaningful.

### The residual, by name — $4.44/day (11.7%)

Ranked by how much each could plausibly carry. **All four are hypotheses; none is
measured.**

1. **Containers that outlive `completed_at`.** The terminal DB write is not
   container exit. Publisher drain, export upload, HLS, `work_dir` teardown and
   the ThreadPool join all run after it. Bounded above by the 1200s timeout. The
   30s exit tail above is a *documented lower bound* on this, not the whole of it.
2. **The `_outer_safe_rescue` double-run** (§Defect 2). It re-enters `handler()`
   in-process, so its container-seconds ARE inside my spans — but it overwrites
   `worker_started_at`, so any measurement keyed on that column undercounts by an
   entire first attempt. My spans use `started_at`, which is why they survive.
3. **`PromptlyDiagnoseUpload` / `prewarm_janitor` / the prewarm class.** Small
   individually; the arithmetic in §3 excludes prewarm from the *floor* but not
   from load-proportional churn.
4. **Regression attribution error.** R2 on the memory fit is only 0.375; the
   floor's 95% CI is +/-$2.20/day, which alone spans half the residual.

**What would close it:** `tags={"fn": "..."}` on every `@app.function` /
`@app.cls`. `modal billing report --tag-names` then decomposes the invoice by
function directly and this entire section becomes a measurement instead of a
solve. That is a one-line-per-decorator change and it is the highest-leverage
observability work available on this surface.

---

## 5 — THE LEVER TABLE, ranked by MEASURED $/day

Every row is net of its own handoff cost. Denominators in §6 and in
`L1_L2_BUILD_PLAN.md`.

| lever | net $/day | % of invoice | $/yr | detectable on the invoice? |
|---|---|---|---|---|
| **resize the always-on dispatcher** (8c/32G -> 2c/4G) | **+12.19** | **32.1%** | **4,448** | **yes — 2 days/arm** |
| kill/shrink the rest of the always-on floor | up to +20.56 | 54.1% | 7,504 | yes — 1 day/arm |
| `scaledown_window` 45s -> 10s | +1.68 | 4.4% | 613 | no — 89 days/arm |
| **L2** — release orchestrator during the burst | **+0.69** | **1.82%** | **252** | **no — 529 days/arm** |
| **L1** — plan leg at cpu=2, all routes | **+0.14** | **0.37%** | **52** | **no — 12,524 days/arm** |
| L1 — plan leg at cpu=2, editorial only | +0.10 | 0.25% | 35 | no — 27,402 days/arm |
| L1 — plan leg at cpu=8 (encode-safe) | **0.00** | 0.0% | 0 | never |

*Detectability = days per arm for a two-arm comparison whose 95% CI excludes
zero, at the measured daily sd of $5.73.*

**L1 and L2 together are 2.2% of the invoice.** The always-on floor is 54%. The
two levers this round was sent to design are, jointly, **1/24th** of the line
item sitting next to them.

---

## 6 — WHAT I COULD NOT MEASURE

| gap | why | what would measure it |
|---|---|---|
| per-function cost | billing API is app-level; no function declares `tags=` | add `tags={"fn": ...}` to every decorator |
| true container lifetime | DB has `completed_at` (terminal write), not container exit | log `time.time()` in an `atexit`/SIGTERM hook -> ledger |
| dispatcher peak RSS | never sampled on that class | port the `modal_app.py:735` cgroup sampler into `PromptlyWorker` |
| burst dispatch/queue/cold-start split | `burst_reported_render_s` is None 14/14 (Defect 1) | one-word fix, then blocked_s minus render is the answer |
| L1 under a working Gemini | `gemini_call = 0` on 289/289 editorial jobs | re-measure after Vertex billing is restored |
| whether a uniform rate multiplier applies | ratio test can't see it | one container of known shape and known runtime |
