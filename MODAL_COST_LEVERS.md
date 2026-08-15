# MODAL PER-RENDER COST, PINNED — and the levers `[§6.1, Law 1]`

**Measured 2026-08-15 on full-envelope completions since Aug 12 (n=279), cut BY
ROUTE.** Unit is the repo's own model (`modal_app.py:2664`):

```
core_seconds = wall × 16          (orchestrator cpu=16, held the WHOLE wall)
             + render_s × 32      (burst cpu=32, the double-pay)
GiB_seconds  = wall × 12 + render_s × 64
```

| route | n | wall p50 | render p50 | **core-s p50** | GiB-s p50 |
|---|---|---|---|---|---|
| `minimal` | 179 | 30.5s | 4.5s | **632** | 726 |
| `minimal_speech_uncut` | 98 | 49.7s | 9.5s | **1,099** | 1,233 |
| `moodreel` | 2 | 83.4s | 34.4s | 2,576 | 3,308 |
| **weighted** | **277** | — | — | **797** | ~995 |

*(`moodreel` n=2 — reported for shape, not as a result.)*

**The premium path is NOT in this table because it has never run.** The premium
pipeline is dark (0 fires in 2,074 jobs), so its per-render cost can only be
**projected**, and is labelled as such below.

## THE FINDING: 82% of the bill is WAITING

**Render is only 18% of wall.** The orchestrator holds **cpu=16 for the other
82%** — and that 82% is Gemini, Deepgram, upload and network *wait*, with no
compute happening at all. We are paying 16 cores to hold a socket open.

## THE LEVERS, in core-seconds

| lever | weighted core-s | delta |
|---|---|---|
| today | 797 | — |
| **L1** — orchestrator drops to **cpu=4 during network wait** | 425 | **−47%** |
| **L2** — L1 **+ release the orchestrator during the burst** | 325 | **−59%** |

**L1** is the big one. Nothing computes while we wait on Gemini; cpu=16 during
that window buys latency for no one.

**L2** removes the *double-pay*: during the burst render, the orchestrator (16)
**and** the burst (32) are both held — 48 cores for one piece of work. Only the
burst is doing anything.

These are **percentages, so they are rate-independent** and hold whatever the
rate card says.

### Why L1 matters MORE on the premium path

The 70s Lumen scene budget is **almost entirely network wait** — the model
generates, we hold.

| | core-s | vs today |
|---|---|---|
| today, standard | 797 | — |
| **projected premium**, scenes at cpu=16 | **1,917** | **+140%** |
| **projected premium**, scenes at cpu=4 (L1) | **1,077** | +35% |

**Adding Lumen at today's cpu profile more than doubles Modal core-seconds per
render, before a single extra frame is rendered.** L1 turns that into +35%. That
is the single biggest cost decision in front of the campaign, and it is
independent of Vertex spend ($0.56/edit at 4 scenes).

## THE ONE MISSING INPUT — dollars

**I will not quote $/render.** The Modal rate card is not recorded anywhere in
this repo, and the project's own anchor ("job compute was ALREADY ~$0.09",
`modal_app.py:674`) was measured under a different configuration and cannot be
back-solved into a core-second rate with confidence.

What is needed is one number — **$ per core-second and $ per GiB-second from the
actual invoice** — after which every row above converts directly. Until then the
honest report is core-seconds and percentages, both of which are measured.

**This is deliberately not estimated.** The cost law says *measured, never
estimated*, and a plausible-looking $/render built on a guessed rate is exactly
the kind of number that gets quoted back for months.

## GPU-SECONDS

**Zero on the render path — the worker is CPU-only** (GPU was the parallelism
ceiling and was removed). The only GPU surface in the campaign is the **RVM
matting sibling** for Component C, whose seconds and dollars are unmeasured and
priced at a **$0.05 measurement** in `RVM_PRICING.md` — and which, per that
design, runs **only** when the plan places text behind the subject, so the common
path pays **0 GPU-seconds**.
