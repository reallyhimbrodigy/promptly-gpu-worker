# MODAL BILL — DECOMPOSED FROM THE INVOICE, 2026-09-01

**Source: `modal billing report --start "30 days ago" --show-resources --json`,
pulled with the isolated 1.5.4 client (`./cost_weekly.sh`). Window Aug 3 – Sep 1,
1,534 rows. Rate card pulled live from `modal billing rates`, not recalled.**

Volume denominator from `video_jobs` over the same window. Every number below is
either an invoice line or a DB count; the one fitted model is labelled as such.

---

## 0 — THE ANSWER: there is no missing $1,365

The premise was `$0.07/render × ~1,500 renders = $105`, against a $1,500 bill.
Both terms are wrong, each by a multiplier, and together they account for the
whole invoice. Nothing exotic is hiding.

| term | premise | measured | factor |
|---|---|---|---|
| renders / month | ~1,500 | **6,084** Modal-spawned (5,930 completed) | **4.06×** |
| $ / render | $0.07 | **$0.2112** | **3.02×** |
| **product** | **$105** | **$1,285** | **12.2×** |

`$0.2112 × 6,084 = $1,285` against an actual `promptly-gpu-worker` line of
**$1,284.96**. The reconciliation is exact to 0.03%.

**And the bill is no longer $1,500/mo.** Trailing 30 days is **$1,312.49**; the
last 7 days are **$173.58 = $24.80/day = a $744/mo run-rate**. The 30-day window
still contains the expensive early-August regime (Aug 4 alone was $110.59). Cut
to a clean cohort, current spend is roughly half the cap.

### Why $0.07 was wrong

$0.07 prices **one `run_pipeline_bg` container** (cpu=16, 12 GiB =
$0.000237/s) for 300s. Two independent errors:

1. **300s is not the lifetime.** Measured mean is **196.4s** (785 jobs, Aug 26 –
   Sep 1). At one container that is $0.047, not $0.07.
2. **A job is not one container.** This is the big one — see §3.

---

## 1 — THE INVOICE, AS BILLED

| | 30 days (Aug 3 – Sep 1) |
|---|---|
| **Total** | **$1,312.49** ($43.75/day) |
| `promptly-gpu-worker` | **$1,284.96 — 97.9%** |
| all agent/cert/probe apps combined | **$27.53 — 2.1%** |
| **last 7 days** | **$173.58 = $24.80/day → $744/mo run-rate** |

Agent test spend is the whole 2.1%, and the largest single line in it is
`density-delete-test` at $5.32. `agentic-editor` is **$0.44** for its entire
life to date.

### By resource

| resource | 30d | share |
|---|---|---|
| CPU | $983.35 | 74.92% |
| Memory | $329.06 | 25.07% |
| **all GPU** | **$0.0691** | **0.005%** |

Rate card (live): **CPU $0.0473/core/hr, Memory $0.008/GiB/hr.**
Implied for the worker: **73,227,752 core-seconds** and **145,273,195 GiB-seconds**
over 30 days = 2.44M core-s and 4.84M GiB-s per day.

---

## 2 — THE THREE SUSPECTS, EACH CLOSED

### GPU — ruled out, $0.07 of $1,312

| line | 30 days |
|---|---|
| Nvidia L4 | $0.0369 |
| Nvidia T4 | $0.0322 |
| A10G | $0.0000 |
| L40S | $0.0000 |

**$0.0691 total — 0.005% of the bill.** No production function requests a GPU;
the worker is CPU-only by design (`modal_app.py:1756`). The two trace lines are
retired probes. There is no idle GPU and nothing to reclaim.

### min_containers / warm pools — ruled out, and observed twice

Code: **zero** active `min_containers=`, `keep_warm=`, or `buffer_containers=`
across `modal_app.py`, `handler.py`, `premium.py`. The one that existed
(`PromptlyPrewarmWorker min_containers=1`) was removed at v60.

Observed, not just read:

- `modal container list` → **0 active containers**. `modal app list` → **0 tasks**.
- **The hourly floor**, which is the real test — one instant is not a
  measurement. Over **167 hourly buckets**: min **$0.0167/hr**, p05 $0.21, p50
  $0.90, p90 $1.96, max $3.46. A single always-on prewarm container (4 GiB,
  0.125 cpu) would cost $0.0379/hr — **more than the cheapest hour on the
  invoice**. Nothing is being held alive.

### Container idle-timeout billing — real, and small

No warm pool, but five `scaledown_window` settings do bill idle:

| container | cpu | mem | idle window |
|---|---|---|---|
| `run_pipeline_bg` (orchestrator, per job) | 16 | 12 GiB | 45s |
| `PromptlyWorker` (dispatcher) | 8 | 32 GiB | 30s |
| `PromptlyPrewarmWorker` | default | 4 GiB | **600s** |
| `PromptlyValidator` | 4 | 2 GiB | 300s |
| `PromptlyDiagnoseUpload` | 2 | 1 GiB | 300s |

Sized in §3 as the fitted floor: **$5.69/day ≈ $171/mo, 13–19% of the bill.**
Real, worth a look, not the story. The 600s prewarm window is the biggest single
idle exposure and its own note says the hit rate is 43% — 57% of prewarms are
wasted download+transcribe.

---

## 3 — WHERE THE $0.21/JOB ACTUALLY GOES

Clean cohort **Aug 19 – Sep 1 (14 days)** — `worker_started_at` is populated
throughout and the daily series is stable (Aug 17–18 are excluded: 371,606 and
135,601 worker-seconds against ~230 jobs/day is reconciler contamination, not
traffic).

| | 14-day total |
|---|---|
| worker-app spend | $410.16 |
| Modal-spawned jobs | 1,866 |
| `stage_timings.render` seconds | 207,422 |
| **observed $/job** | **$0.2198** |
| orchestrator-lifetime model (381,068 worker-s × $0.000237) | $90.27 — **22%** |
| **unexplained by one container** | **$319.88 — 78%** |

### The fit (labelled: this is a regression, not an invoice line)

`spend/day = $5.69 + $0.000842 × render_s + $0.0836 × jobs` — **R² = 0.880**,
n = 14 days. Single-variable fits are weaker (`vs worker_s` R² = 0.341), which
is itself the finding: **spend does not track orchestrator lifetime.**

| term | 14d | share | reading |
|---|---|---|---|
| render seconds | $174.65 | **42.6%** | the render leg |
| per-job fixed | $155.99 | **38.0%** | cold start, dispatch, prewarm, scaledown tail |
| daily floor | $79.66 | **19.4%** | idle windows |

**The load-bearing coefficient: $0.000842 per render-second is 3.55× the
orchestrator's own rate** ($0.000237/s) and 1.50× a single `render_burst`
(cpu=32/64 GiB). During the render stage roughly **3.5 orchestrator-equivalents
of compute are held at once** — consistent with `PROMPTLY_RENDER_FANOUT=1`
running heavy chunks on concurrent `render_chunk_fanout` containers
(cpu=16/32 GiB each) while the orchestrator holds cpu=16 waiting.

That is the answer to "why is it 3× the rate card": **the rate-card estimate
priced one container, and the render leg runs several.**

---

## 4 — WHAT FAILED JOBS COST BEFORE DYING

Same 14-day cohort. **Lead with users, per Rule 7.**

| | jobs | **users** | mean container life | render_s |
|---|---|---|---|---|
| completed | 1,743 | **1,381** | 186.6s | 205,266 |
| **failed** | **338** | **228** | **467.4s** | 2,156 |
| canceled | 38 | 37 | 49.2s | — |

**A failed job holds a container 2.5× as long as a successful one and produces
1.0% of the render seconds.** It burns the wait, not the work — the long tail is
jobs running to a timeout rather than failing fast.

Cost, modelled on the §3 coefficients (failures do almost no rendering, so
they price at orchestrator rate + per-job overhead):
`55,151 worker-s × $0.000237 + 338 × $0.0836 ≈ **$41 / 14 days ≈ $88/month**`.

~7% of the bill, across **228 affected users**. The user number is the one that
matters: those are people who paid attention and got nothing.

---

## 5 — THE PER-FUNCTION SPLIT IS NOT AVAILABLE, AND THAT IS A FINDING

**Modal's billing API cannot separate `ingest_bundle` / planner / render / HLS.**
Checked directly rather than assumed:

- `Workspace.billing.report(start, end, resolution, tag_names)` — the complete
  signature. Grouping is **app × resource × tag** and nothing finer.
- **Tags are set on `modal.App(name, tags=...)` — the App, not the function.**
  `inspect.signature(modal.App.function)` has **no `tags` parameter** in either
  the deploy client (1.2.6) or the current client (1.5.4).

So the finest grain the invoice will ever give is the **App**. The §3 split is a
regression against `stage_timings`, and it is labelled that way — it is not an
invoice line and must not be quoted as one.

**Two ways to make it a measurement instead of a fit:**

1. **Split the Apps.** `render_burst` and `render_chunk_fanout` in their own
   Modal App would decompose themselves on the invoice, permanently, with no
   instrumentation. Largest change, exact answer.
2. **Self-report core-seconds** (cheaper). Every relocated function returns its
   own `cpu × wall` core-seconds; the orchestrator sums them into
   `stage_timings.core_s_by_fn`. Summed across jobs × the rate card, that must
   reconcile against the invoice total — and **the residual is then a measured
   non-job number instead of a fitted intercept.**

Per the contract rule for the three-container split: this must be a **return
value**, never an out-parameter across the boundary.

Both need a deploy, which is the TRUTH lane's call. Filed, not shipped.

---

## 6 — WHAT I'D DO WITH THIS, RANKED BY $ AND BY USER

| lever | worth | confidence |
|---|---|---|
| render-leg concurrency (the 3.55× coefficient) | ~42% of the bill | fitted — needs §5 to become exact |
| per-job fixed overhead ($0.0836 × 6,084/mo ≈ $509/mo) | ~38% | fitted |
| fail-fast on the 467.4s failure tail | ~$88/mo + **228 users** | measured |
| prewarm 600s window at a 43% hit rate | part of the $171/mo floor | measured window, unmeasured volume |
| GPU | **$0.07/mo — nothing** | measured, closed |
| warm pools | **$0 — nothing** | measured, closed |

**Do not start on cost until §5 lands.** Two of the top three lines are
regression coefficients. The precedent is in this repo: the previous cost model
was off by 72% against the invoice, and a stale HLS number cost a directed
session on a win that was already banked.

## Standing rule this file adds

**Regenerate before planning, and state the window.** `./cost_weekly.sh 30`
reproduces §1 in one command. A cost number without a date and a denominator is
a number that will misdirect a session — the trailing-30-day figure and the
current run-rate differ by 1.8× *right now*.
