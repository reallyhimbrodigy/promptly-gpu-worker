# L1 / L2 — the MEASURED net, the split boundary, and the protocol `[Law 1]`

**TRACK D, 2026-08-16. Design + measurement. NOT a merge, not a deploy.**
Rate card verified from Modal; invoice pulled from Modal; everything else read
from `video_jobs` / `analytics_events`. Cost model and denominators live in
`MODAL_COST_LEVERS.md`.

**Headline: both levers are real, both are correctly reasoned, and both are too
small to build now.** L1 nets **+$0.14/day (0.37%)**, L2 nets **+$0.69/day
(1.82%)**, against an always-on floor of **$20.56/day (54.1%)** that neither
touches.

---

## 0 — WHAT SURVIVED FROM THE PRIOR ROUND, AND WHAT DID NOT

| prior claim | verdict |
|---|---|
| Resources are decoration-time only; L1/L2 are function splits, not knobs | **CONFIRMED** — `@app.function(cpu=, memory=)` only; `Function.remote()` takes args/kwargs |
| Break-even for L1 is ~12.9s of moved wait | **CONFIRMED to 0.1s** — falls out of the rate card, denominator-independent |
| L1 is net-negative at today's profile | **CONFIRMED in direction, wrong in magnitude** — it is net-POSITIVE but by $0.10-0.14/day |
| "L2 is ~$14.8/day = ~42% of the bill" | **REFUTED — off by 21x.** See §2 |
| "Render is only 18% of wall, the other 82% is network wait" | **REFUTED.** Render is **82%** of editorial wall; wait is ~18%. See §1 |
| Orchestration is 72.3% of spend | **REPLACED** — 34.2% is job-attributable, 54.1% is an always-on floor |

---

## 1 — L1: MEASURED NET

### Denominator

**Standard editorial route (`route` absent = the headline route), Aug 09-14,
n=289 jobs, 48.2/day.** Identified by the rich `stage_timings` schema
(`normalize_transcribe_upload`, `edit_plan`, `fps_normalize`, `gemini_call`,
`timeline`); the 697 `minimal`/`minimal_speech_uncut` jobs carry the lite schema
and are reported separately.

### The stage table (seconds)

| field | n | p50 | mean | p90 | sum/day |
|---|---|---|---|---|---|
| **total** | 289 | **125.5** | **154.1** | 282.0 | 7,421 |
| download | 289 | 1.1 | 1.3 | 1.9 | 62 |
| `normalize_transcribe_upload` | 289 | 19.5 | 31.6 | 63.0 | 1,524 |
| ...of which `fps_normalize` (ENCODE) | 289 | 8.2 | 19.4 | 46.6 | 934 |
| `edit_plan` | 289 | 15.4 | 18.6 | 34.1 | 895 |
| ...of which `proxy_encode` (ENCODE) | 289 | 0.9 | 1.3 | 1.7 | — |
| **render** | 289 | **94.9** | **110.6** | 195.9 | **5,326** |
| upload_export | 289 | 4.4 | 6.0 | 10.4 | 289 |
| source_duration_s | 289 | 19.4 | 28.8 | 61.0 | — |
| **`gemini_call`** | 289 | **0.0** | **0.0** | **0.0** | **0** |

**Two-term fit (all spawned std-editorial):** `wall = 18.8s + 1.08 x
source_duration`, n=228, mean source 22.8s. The floor is 18.8s.

**Render occupies the last 82% of the job** (median of `render_start / total`
from the `timeline` field). **The premise that 82% of wall is network wait is
inverted.** It was true when it was written; it is not true now.

### The reason L1 has nothing to move: Gemini is not being called

**`gemini_call = 0.0` on 289/289 editorial jobs.** Zero. The Vertex dunning
outage (`project_vertex_dunning_outage`) is still live, so every editorial job is
running the deterministic `build_safe_recipe` path. **L1's entire thesis is
"move the Gemini network wait off 16 cores". Right now there is no Gemini wait to
move.**

### The net

Movable = `total - render - fps_normalize - proxy_encode` (i.e. everything that
is neither the render nor an encode): **p50 16.0s, mean 22.8s, p90 44.4s.**

| plan leg | save/s | gross $/day | handoff $/day | **NET $/day** | break-even | jobs above it |
|---|---|---|---|---|---|---|
| **cpu=2 / 4 GiB** | $0.00020172 | 0.221 | 0.126 | **+0.096** | 12.9s | 71% |
| **cpu=8 / 8 GiB (encode-safe)** | $0.00011400 | 0.125 | 0.126 | **-0.000** | 22.9s | 25% |

Across **all routes** (n=986 jobs with `stage_timings`, 164.3/day): gross
$0.570/day, handoff $0.428/day, **NET +$0.142/day = 0.37% of the invoice.**

**At an encode-safe cpu=8 the net is exactly zero.** The saving and the second
cold start cancel to three decimal places.

### The cost this model does NOT yet charge L1

`normalize_transcribe_upload` is a **single concurrent pool**: the Deepgram wait
(movable) and `fps_normalize` (an encode, not movable) run in parallel *in the
same stage*. Splitting them across containers requires staging the source media
to S3 and back. **`render_burst` already measured that round-trip: "~20s fixed
overhead (cold-start + staging)"** (`handler.py:25963`). Charging L1 even 20s of
extra orchestrator hold per job costs **$0.96/day — seven times L1's entire gross
saving.** L1 as scoped is therefore net-negative once staging is priced honestly,
and the $0.10-0.14/day above should be read as an **upper bound**.

---

## 2 — L2: MEASURED NET (the instrument reported)

### Denominator, and its limits stated

| | |
|---|---|
| instrument first event | 2026-08-15T07:43:17Z |
| observation window | **27.1 hours** |
| Modal-reaching jobs in window | **191** (168.9/day-equivalent) |
| **jobs that fired the burst** | **8 -> a 4.2% firing rate** |
| `.remote()` calls observed | 14 (**1.75 per firing job** — see Defect 2) |
| `blocked_s` | p50 **200.4s**, mean 235.5s, sd 131.0, range 108.9-622.2 |
| blocked seconds/day | **2,916** |

**Limits, named:**
- **One day, n=14, 8 jobs.** Everything below inherits that.
- **Failed bursts are invisible.** The insert sits *after* `_out = _fn.remote(...)`
  (`handler.py:26048-26075`); a burst that raises never emits. So this is a
  **lower bound**.
- The `burst_reported_render_s` half of the instrument is dead (Defect 1), so the
  dispatch/queue/cold-start split that motivated it is still unmeasured.

### The net

L2 removes **the orchestrator's own 16c/12GiB hold** during `.remote()`. It does
not change the burst container, the wall clock, or the render.

```
2,916 blocked-s/day  x  $0.00023689/s  =  $0.69/day  =  1.82% of the $38.00/day invoice
```

| | |
|---|---|
| double-hold per firing job | 412s -> **$0.0976/job** of orchestrator waste |
| burst container over the same window | $0.2319/job — **NOT removed by L2** |
| sensitivity (0.5x / 1x / 2x the observed mix) | $0.35 / $0.69 / $1.38 per day |

### Why the prior estimate was 21x too high

The prior model took `$35.34/day / $0.000561/s = ~335 burst-seconds per job` and
applied it to **every** job. **The burst fires on 4.2% of jobs**, because
`PROMPTLY_BURST_MIN_OUTPUT_S = 45` gates it on projected output >= 45s
(`handler.py:25977`) and the organic median clip is ~10s. Dividing whole-app
spend by all jobs assigned the burst a denominator 24x too large.

**On the jobs where it does fire, L2's premise is exactly right:** the
orchestrator is idle for **56-76% of the whole job span** (measured on all 8).
The mechanism is real. The population is 4.2%.

---

## 3 — THE SPLIT BOUNDARY, AND THE NO-ENCODE PROOF

The guard `validate_deploy.py:9268` ("L1 PLAN LEG CARRIES NO ENCODE") is ARMED
but not binding because no plan leg exists. Here is the boundary it would have to
enforce, derived from the code and priced from the corpus.

### STAYS on the render leg (cpu >= 16) — every encode

| stage | code | fires on | p50 | mean | max |
|---|---|---|---|---|---|
| **`_do_fps_normalize`** | `handler.py:37995`, stage marker `:38082` | **98.7%** of editorial jobs | 8.2s | 19.1s | **299.3s** |
| **`_do_gemini_proxy_impl` path 3** (480p@16fps on-server) | `handler.py:37846` | **3.0%** (proxy_encode >3s) | — | — | **19.0s** |
| ffmpeg audio extraction | `handler.py:37810-37823` | 100% | — | — | — |
| `render_stage` (Remotion + x264 + HLS + exports) | `handler.py:35781` | 100% | 94.9s | 110.6s | 730.2s |

### MAY move to the plan leg (cpu=2) — network only

| stage | why safe |
|---|---|
| `download` | HTTP GET, 1.1s p50 |
| Deepgram `transcribe_audio` | socket wait (`handler.py:37828`) |
| Gemini `edit_plan` call | socket wait — **currently 0.0s, 0/289 jobs** |
| `_do_gemini_proxy_impl` paths 1 and 2 | client-proxy download / prewarm-volume read. **No encode.** |
| proxy upload | network |

### The proof, and the trap inside it

**`proxy_encode` is a CHILD of `edit_plan` in the timeline** — measured directly,
289/289 jobs carry an `edit_plan/proxy_encode` node. `edit_plan` is precisely the
leg L1 proposes to move to cpu=2.

**This is the cpu=8 outage, exactly.** That cut crashed completion **78.9% ->
35.7%** because "a 480p ultrafast proxy encode was CPU-starved"
(`modal_app.py:689`). It is the *same encode*, in the *same stage*, and a cpu=2
leg is **a quarter of the cores that already failed**.

It hides well: **97% of jobs never run it** (client proxy or prewarm cache wins,
p50 0.9s). A canary would very likely miss it. **The 3% that do run it are the
ones that break**, and they are invisible until they are 3% of production.

**Therefore the boundary is NOT `edit_plan -> plan leg`.** It is
`_do_gemini_proxy_impl` **paths 1 and 2 only**, with path 3 forced back to the
render leg or pre-empted. That is a finer cut than the guard's function-body
symbol scan can express — **the guard as written would pass a plan leg that calls
`_do_gemini_proxy`, because the ffmpeg call is one frame deeper.** Extending it
to follow callees is a prerequisite for L1, not a nice-to-have.

---

## 4 — PRE-REGISTERED PROTOCOL

*The Aug-4 prewarm revert is the anti-template: a window cut 600->30 to free a
ceiling that was never binding (7/100 utilisation). It "bought nothing and cost
~20s latency."* The way to not repeat it is to check, **before building**,
whether the primary read can even move.

### 4.0 — THE GATE THAT FIRES FIRST: is the effect detectable?

Measured daily invoice sd over the clean cohort: **$5.73/day (CV 15.1%)**.
Days per arm for a two-arm comparison whose 95% CI excludes zero:

| lever | effect | days/arm | verdict |
|---|---|---|---|
| L1 (all routes) | $0.14/day | **12,524** | **INFEASIBLE** |
| L1 (editorial) | $0.10/day | 27,402 | INFEASIBLE |
| **L2** | **$0.69/day** | **529** | **INFEASIBLE** |
| `scaledown_window` 45->10s | $1.68/day | 89 | infeasible |
| dispatcher 8c/32G -> 2c/4G | $12.19/day | **2** | **feasible** |

**Neither L1 nor L2 can be validated on the invoice at any feasible sample size.**
Any protocol whose primary read is `$/day` would return a null for both and could
not distinguish "it worked" from "it did nothing" — which is the Aug-4 failure in
its purest form. **So the primary read must not be dollars.**

### 4.1 — Registered protocol, if either is built anyway

| | L1 | L2 |
|---|---|---|
| **primary read** | plan-leg **container-seconds x (16-2) cores**, emitted per job as a ledger event | **`blocked_s` per burst-firing job**, already instrumented |
| **why not $/day** | effect is 1/40th of daily noise | effect is 1/8th of daily noise |
| **expected direction** | movable seconds move off the 16c leg; **total wall unchanged** | `blocked_s` -> ~0 orchestrator core-seconds; **`blocked_s` itself unchanged** |
| **null threshold -> REVERT** | <10s/job of wait actually relocated | orchestrator hold not eliminated on >=90% of firing jobs |
| **n required** | 200 editorial jobs (~4 days at 48.2/day) | **190 burst-firing jobs = ~24 days at 8/day** |
| **guard 1 — wall by route** | std-editorial p50 AND mean must not rise >10%; report the two-term fit `18.8s + 1.08 x source` both sides | same |
| **guard 2 — queue delay** | p50 and %>60s must not rise at all | same |
| **guard 3 — completion by route** | must not fall. **Hard stop: the cpu=8 precedent is 78.9% -> 35.7%** | same |
| **guard 4 — encode presence** | `proxy_encode` p99 on the plan leg must stay <3s; **any sample >3s on a cpu<8 leg is an immediate revert**, not a tuning signal | n/a |
| **guard 5 — orphans** | `modal app list` = 0 tasks after teardown | **`.spawn()`-orphan class: exactly one terminal emitter, named, and a burst that dies WITHOUT raising must classify loudly** |
| **clean cohort** | >=4 full days each side, no deploy boundary inside, no outage hour, cut by route, Vertex state identical both sides | >=24 days each side |
| **revert trigger** | any guard breached -> revert same day, **no tuning in-window** | same |
| **denominator, stated in advance** | jobs/day per route both sides | burst-firing jobs/day both sides |

### 4.2 — Rule 1: the checks that make the regression impossible

1. **Extend `validate_deploy.py:9268` to follow callees.** Today it scans a
   function body for forbidden symbols; `_do_gemini_proxy` calls ffmpeg one frame
   deeper and would pass. Until it follows the call graph, the guard does not
   cover the exact defect it was written for.
2. **Assert the plan leg's cpu >= the highest-cpu encode it can reach.** A
   literal pin, checked against the decorator, in the same style as the existing
   `PROMPTLY_RENDER_CORE_BUDGET == cpu=` pin.
3. **A cost-fingerprint check**: assert the fitted always-on floor stays within
   its 95% CI [$18.36, $22.76]/day. This is the one number large enough to be
   detectable, and it is where a container-sizing regression would show up first.

---

## 5 — RECOMMENDATION

**Do not build L1. Do not build L2 yet.** Neither is wrong; both are small, and
one of them is dangerous for a $0.10/day return.

| | |
|---|---|
| **L1** | **DROP.** +$0.14/day upper bound, $0.00 at an encode-safe cpu=8, negative once S3 staging is priced. Its premise (Gemini network wait) is measured at **0.0s on 289/289 jobs**. **Re-open only when Vertex billing is restored and `gemini_call > 0`** — then re-measure before building. Lumen's 70s of scene generation would also re-open it, on the same condition. |
| **L2** | **HOLD, cheaply.** The mechanism is confirmed (orchestrator idle 56-76% of a burst job) but the population is 4.2% of jobs and the net is $0.69/day. **Fix Defect 1 (one word) and let the instrument run** — it costs nothing and in 24 days it has an n that can support a decision. Revisit if the burst floor drops or long jobs grow. |
| **INSTEAD** | **Measure `PromptlyWorker`'s peak RSS.** It is ~1.1 containers held 24/7 at 8c/32GiB to do `.spawn()`, it is **$17.22/day = 45% of the invoice**, resizing it is worth **$4,448-$5,033/yr**, and it is the only lever on this surface **detectable on the invoice in 2 days**. See `MODAL_COST_LEVERS.md` §3. |

---

## 6 — DEFECTS FILED (evidence attached; not chased)

**1. `burst_double_hold.burst_reported_render_s` is `None` on 14/14 events —
the instrument's comparator half never worked.**
`handler.py:26054` reads `_out["rs"]["stage_timings"]["render"]`, but
`render_stage` returns a dict whose keys are
`['edit_plan', 'timings', 'floor_state', 'render_elapsed', ...]` — **there is no
`stage_timings` key**. The correct read is `rs["timings"]["render"]` or
`rs["render_elapsed"]`. Consequence: the gap between "time the orchestrator was
pinned" and "time the render took" — the single number the instrument was built
to produce — was never captured. One-word fix.

**2. `_outer_safe_rescue` re-renders the whole job, and it is not rare.**
`handler.py:32984` does `_inner = (run_fn or handler)(job)` — a **recursive
re-entry into `handler()`**. On the burst cohort, **6 of 8 jobs (75%) fired
`render_burst` twice**; the second render accounts for **41% of all blocked
seconds observed**. Two further consequences:
  - It **overwrites `worker_started_at`** (`handler.py:36874` runs again), so
    every container-lifetime measurement keyed on that column silently loses the
    entire first attempt. This is the likely cause of the prior model's "5.1%"
    denominator.
  - The blocked window alone costs $0.96/day extrapolated; **the repeated
    download + normalize + transcribe + plan is not counted in that.**
  - `render_started` shows **0 duplicate job_ids** (114 distinct/114), so this is
    server-side, not a client double-dispatch.

**3. `post_upload_watchdog_fired` is vacuous.** 274 fires over 47 jobs on Aug 15,
with `terminal_write_ok: false` and `terminal_write_attempted: false` on **every
one**, reason: *"no result_payload in the timer thread; a bare completion would
strip route/floor/vocab"*. It also reports `held_core_s: 1920.0` on every fire —
that is the constant `120s x 16`, not a measurement. Nine fires on a single job.

**4. `gemini_call = 0.0` on 289/289 standard-editorial jobs, Aug 09-14.** The
Vertex outage is still live and still silent. Reported here because it
invalidates L1's premise and would silently invalidate any speed or quality A/B
run in this window.

**5. `worker_started_at` present on only 494/1241 Modal-reaching jobs (40%).**
The column shipped 2026-08-10; combined with Defect 2 it is not a safe basis for
container-lifetime work. Use `started_at`.

## L1 RE-SIZED AGAINST THE MEASURED EDITORIAL WAIT (2026-08-17)

L1 was priced against a **6.4s** editorial slice and came out marginal
(+$0.14/day, and exactly $0.000/day at an encode-safe cpu=8 plan leg). That
figure rested on a measurement taken while **Vertex was down**: `gemini_call =
0.0` on 289/289 standard-editorial jobs. L1's premise is "move the Gemini network
wait off 16 cores", and there was no wait to move.

**The first full Lumen render measured it directly: `editorial_plan = 97.1s`,
54.3% of a 178.8s wall.**

    measured wait / break-even = 7.5x

L1 is no longer marginal. It is **7.5x break-even** on the axis it was
designed for, and the same seconds appear on BOTH boards — cost AND the 120s
latency law, which this run misses by 59s with the editorial plan as the single
largest term.

### The core-seconds, computed rather than asserted

    97.1s x (16 - 2) cores = 1,360 core-seconds per job
    x 164.3 jobs/day                = 223,372 core-s/day = 62 core-hours/day

**I am deliberately NOT converting that to dollars here.** Track D's per-core-hour
figure was derived from the invoice under a different traffic mix, and the one
number I have that is not an estimate is `modal billing report --csv`. Turning
core-hours into a headline dollar figure with an inferred rate is exactly the
probe-collapse shape this project keeps paying for. The core-hours are measured;
the rate is owed.

### What must be re-checked before L1 ships

Track D's blocker stands and is now MORE dangerous, not less: `proxy_encode` is a
measured child of `edit_plan` (289/289 timelines) — the exact stage L1 moves —
and it is the same encode that crashed completion 78.9% -> 35.7% at cpu=8. A
cpu=2 plan leg is a quarter of those cores. `validate_deploy.py:9268` would PASS
a plan leg that calls `_do_gemini_proxy` because its body scan stops one frame
short. That gate must follow callees before this ships.

### Caveat on the measurement itself

178.8s is a BUILD-LANE upper bound: full 75MB source inline where production
sends a proxy, and no prewarm. The 97.1s editorial wait is the least
affected term — it is a network wait on a model call, not a function of source
size — but it is one sample, on one reference, and it wants a second before it
carries a spend decision.
