# Orchestrator split — increment plan (Zac dir#3, 2026-08-03)

**Author:** speed agent. **Status:** design, not yet built. **Owner of merge/deploy:** speed.

## The defect (measured)

`run_pipeline_bg` (the orchestrator) is provisioned at **cpu=16 / 12GiB** and holds
that reservation for the **whole ~450s job**. But its seven phases have wildly
different core appetites — proven on real traffic by the `cpu_by_stage`
instrumentation (`_set_cpu_stage`, handler.py:34614):

| phase | bound by | cores wanted | evidence |
|---|---|---|---|
| download source | network / S3 | ~0 | boto3[crt], same-region |
| transcribe (Deepgram) | network API | ~0 | file-based FLAC upload |
| gemini_plan | Gemini API (network) | **~5.4** | advisor read, one container |
| **fps_normalize** | ffmpeg CPU | **~26** | advisor read, same container |
| dispatch → render_burst | network (`.spawn`) | ~0 | modal_app.py:23952 |
| burst-wait | blocking on future | ~0 | idle wait |
| upload + DB write | network | ~0 | Supabase write |

**Six of seven phases are network/IO-bound (≤~5 cores). Only `fps_normalize`
wants ~26.** Holding cpu=16 across all seven is the "double-hold": the container
sits at ~0.6 cores through planning (~81s) and at ~0 cores through the entire
burst-wait, paying cpu=16 the whole time. CPU is **67% of the bill** — this is the
single largest recoverable waste on the product route.

## The seam

`fps_normalize` (26 cores) vs `gemini_plan` (5.4 cores) in the **same** container
is exactly the split line. Move the one core-hungry step (and the residual
in-process render) off the orchestrator; run the six network-bound phases on a
cheap **planner** container.

## Increments (ship + measure one at a time — Rule 2)

### Increment A — route ALL renders to `render_burst` (kill the in-process sub-floor path)
- **Why first:** the planner cannot drop to few cores / low memory while it still
  renders sub-floor jobs (<45s output) in-process — a heavy short render would
  OOM/starve. This is the stated RESIDUAL in the run_pipeline_bg memory note.
- **Change:** remove the sub-floor branch; every render dispatches to `render_burst`.
  The burst floor check (`<45s` in-process) goes away — burst handles all shapes.
- **Cost of doing it:** sub-floor jobs pay a burst cold-start (~10-12s handler
  import). MEASURE: is the cold-start < the in-process saving? Mitigate with one
  warm burst container if the cold-start hurts the <30s-source latency law.
- **Gate:** validate_deploy assert — no `render_stage(`/in-process render reachable
  from `run_pipeline_bg`; the only render path is the burst dispatch.
- **Denominator to report:** % of jobs that were sub-floor (rendered in-process)
  over a clean cohort — that's the population this increment re-homes.

### Increment B — move `fps_normalize` into the core-rich container
- **Change:** the planner dispatches the **raw** source + plan to `render_burst`;
  burst runs `_do_fps_normalize` FIRST (at cpu=32, so ~2× faster than cpu=16), then
  renders. `_do_fps_normalize` (handler.py:34527) currently runs in the planner's
  `mega_pool`; it moves to the burst entrypoint before `render_stage`.
- **Dependency check (must verify before building):** the PLAN (gemini) consumes
  **face** signals (`_face_transform`, `_face_trajectory`, source_res) — those come
  from **face detection** (sparse, <4 cores), NOT from `fps_normalize`. Face
  detection STAYS on the planner. `fps_normalize`'s output (the normalized source
  file) feeds the RENDER only → safe to move. CONFIRM by grepping every reader of
  the normalize output; if any pre-dispatch stage reads it, this increment blocks.
- **Cost trade (per job, arithmetic):** old = normalize T×16 core-sec on planner;
  new = T×32 on burst BUT the planner is freed of cpu≈12 for the whole ~450s job.
  Net ≈ **−(450×12) + (T×16) ≈ −4400 core-sec/job saved** (T~60s), before the
  cpu=32 speedup shrinks T further. This is the bulk of the win.
- **Gate:** assert normalize runs inside the burst entrypoint, not the planner's
  mega_pool; assert the raw source is what's dispatched.

### Increment C — drop the planner to its true floor
- **Change:** `run_pipeline_bg` cpu 16→**measure-then-set (target 4–8)**, memory
  12GiB→its non-normalize non-render floor. Do NOT guess — read the planner's core
  peak from `cpu_by_stage` AFTER increments A+B remove normalize+render, then set
  cpu to that peak + headroom. The `gemini_plan` 5.4-core peak + parallel face
  detection is the likely binding constraint → cpu=6 is the safe first cut, 4 only
  if the measured peak clears it. `PROMPTLY_RENDER_CORE_BUDGET` becomes moot on the
  planner (it no longer renders) but keep the validate_deploy budget==cpu pin honest.
- **Gate:** the existing budget==cpu pin; a new assert that the planner never
  renders (composes with Increment A's gate).
- **Denominator to report:** cpu-seconds/job on the product route BEFORE vs AFTER,
  cut by route (Rule 5). Headline = standard-editorial.

## Folded-in: the thread-leak durable fix
The "N threads still running after container exit" tail (up to 30s billed) scales
with the container's cpu. On a cpu=6 planner it costs 6 core-sec not 16 — and
increments A+B remove the heaviest busy-thread candidates (normalize ffmpeg,
in-process render subprocess) from the planner's exit entirely. The SIGTERM
diagnostic (shipped 5afc5a4) will name the exact `-0/-4` worker on the next
scaledown; the split then either eliminates it or makes it near-free. **The split
is the durable fix; the diagnostic is how we confirm which thread it kills.**

## Order + measurement discipline
A → B → C, each deployed and **observed on real traffic with a denominator** before
the next (Rule 2). No synthetic Modal spend (Rule 6): validate on watched real jobs,
price each step. Report cost/latency **by route** (Rule 5), headline standard-editorial.
Every increment ships with the named gate above (Rule 1).

## Open questions for Zac (taste/credential calls only)
1. Accept the sub-floor burst cold-start (~10-12s) on tiny jobs, or fund one warm
   burst container to hold the <30s-source latency law?
2. Planner target cpu after measurement — 4 (aggressive) vs 6 (safe on the 5.4 peak)?
