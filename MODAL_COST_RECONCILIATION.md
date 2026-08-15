# COST RECONCILIATION — before L1/L2 are touched `[Law 1]`

**Rate: $0.0000131/core-second (owner-supplied). Memory at Modal list
$0.00000222/GiB-s.**

## 1 — THE $0.09 ANCHOR IS NOT A MYSTERY. It reconciles exactly.

```
$0.09 / $0.0000131 = 6,870 core-seconds = 429s at cpu=16
```

The repo states that era held the container **~450s/job** (`modal_app.py:674`).
`450 × 16 × $0.0000131 = $0.094`. **Exact.** The anchor is a 450s-wall job from
the pre-split configuration; today's measured walls are **30.5–49.7s**. It was
never a contradiction — it is a different job profile, and comparing my model
against it was comparing two different eras.

## 2 — MY MODEL WAS MISSING THE CONTAINER LIFETIME

The naive model billed only `worker_started_at → completed_at`. A container is
billed from **cold start through scaledown**.

| | naive | + 11s cold start + 45s tail | ratio |
|---|---|---|---|
| `minimal` (n=179) | 632 core-s · $0.0083 | 1,528 core-s · **$0.0200** | 2.4× |
| `minimal_speech_uncut` (n=98) | 1,099 core-s · $0.0144 | 1,995 core-s · **$0.0261** | 1.8× |
| **weighted (n=277)** | **$0.0104** | **$0.0222** | **2.1×** |

Cold start is the documented "in-body handler import ~10-12s"; the tail is
`scaledown_window=45`. **At ~1 job/30min the tail is never amortised** — the repo
says so itself: each job cold-starts anyway, so the idle window buys ~zero reuse.

## 3 — THE TERM THAT DOMINATES, AND IT IS NOT JOB COMPUTE

`modal_app.py:674`, already measured by this project:

> *"the real gap is **~$87/day of NON-JOB warmup/prewarm/idle**, which cpu never
> touched."*

At ~150 jobs/day that is **~$0.58/job — about 26× the $0.0222 of actual job
compute.**

### Therefore: L1/L2 are the WRONG FIRST LEVER

| lever | acts on | per-render saving |
|---|---|---|
| L1 (cpu=4 while waiting) | job compute | ~$0.010 |
| L2 (+ no burst double-pay) | job compute | ~$0.013 |
| **non-job idle/prewarm** | **the other 96%** | **up to ~$0.58** |

**L1 and L2 together optimise roughly 4% of the bill.** They remain correct — a
47–59% cut of job compute is real, and it matters *more* on the premium path
where 70s of scene generation is pure wait — but they must not be done **first**,
and the earlier framing of them as "the biggest lever we own" was wrong.

**The idle surface, from the code:**

| surface | scaledown | note |
|---|---|---|
| prewarm `@app.cls` | **600s** | 10 min of idle per fire; fires per upload, not per render |
| two web endpoints | 300s each | |
| orchestrator | 45s | at cpu=16 — the expensive one |
| `rife_normalize_remote` | 90s, **`gpu="H100"`** | **DEAD CODE** — `modal_app.py:1244` says so, no live callers. Costs $0 today because it never fires, but a §4.8 removal candidate: a dead H100 entrypoint is one accidental call from ~$0.00117/s. |

## 4 — WHAT I CANNOT DO, AND WHAT IS NEEDED

**I cannot pull the invoice.** The Modal CLI exposes no billing/usage command
(`modal --help` has `config` and `profile` only); there is no per-app,
per-resource spend available to me from this machine.

**What closes this, and it is small:** from the Modal dashboard's usage/billing
view, the **per-app, per-resource split for the last 7 days** — CPU-seconds,
GiB-seconds, GPU-seconds, broken out by app (`promptly-gpu-worker`,
`promptly-matting`, the prewarm class). That single export:

1. confirms or kills the ~$87/day non-job figure at today's traffic,
2. tells us whether the tail is prewarm, endpoints, or orchestrator scaledown,
3. converts every core-second figure in `MODAL_COST_LEVERS.md` to dollars.

**Until then no cpu/scaledown value should be changed.** Cutting a scaledown
window on a guess is exactly how the surge-cut of the prewarm class was reverted
on 2026-08-04 — it "bought nothing and cost ~20s latency" (`modal_app.py:1382`).

## 5 — GPU ON THE RENDER PATH: NONE

Confirmed by reading every `@app.function`: the only `gpu=` in the app is
`rife_normalize_remote` (H100), which is dead code. The render path is CPU-only —
GPU was removed because it capped parallelism. The sole live GPU surface in the
campaign is the RVM matting sibling (`promptly-matting`, deployed since
2026-07-03, currently 0 tasks).
