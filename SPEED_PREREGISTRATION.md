# PRE-REGISTERED before round 50's paint_ms lands — Zac, 2026-09-09

The speed pillar is the only failing one. Product wall 187–623s against the
120s law; `build_zoom` is 87–92% of the worst cases. It has been unattributed
for six rounds because `paint_ms` was collected by `render_remotion_batch` and
**dropped between the batch and the ledger**, while the printer's `or 0` turned
the missing key into `paint 0.0s`.

`paint_ms` is now recorded. **What it says decides which fix, and the two fixes
are unrelated.** Written down before the number exists so the reading cannot be
fitted to it.

## The measured baseline (round 47, motion)

    build_zoom        458.57s      87.5% of a 524.3s wall
    zooms                   3      0.5s each
    frames            ~45 total    (3 x ~15 at 30fps)
    bundle               9.6s      reported
    paint                 0.0s     NOT REPORTED — the defect, now fixed
    instrument          11.43s     2.2% — my verification passes, already excluded

So ~449s is unattributed inside the stage.

## The branches

**A — paint_ms SMALL (say < 25% of build_zoom).**
The time is in **setup**, not painting. Candidates, all inside the stage:
per-zoom pre-extract ffmpeg (`-ss/-t`, re-encoded crf 16, one per zoom), process
spawn, bundle, asset sync. The fix is **a shared process or a warm bundle** —
`render_remotion_batch` already exists to amortise startup across jobs, and the
zoom path may not be getting the benefit. **Nothing about the components
changes.**

**B — paint_ms LARGE (say > 60% of build_zoom).**
It is **per-frame render cost**. At ~45 frames that would be ~10s/frame, which
is one to two orders of magnitude above a normal 1080x1920 Remotion frame — so
branch B is *itself* a finding rather than an answer, and would point at
something pathological in the composition (an fps mismatch, a per-frame asset
re-read, a full-source decode per frame). **Zac's fidelity ruling means the
render itself stays**; the pathology is what gets fixed, not the quality.

**C — paint_ms ABSENT.**
Neither branch. The batch did not report, the fix did not take, and the answer
is UNMEASURED — not a small number. This must not be read as branch A.

**D — paint_ms + bundle + instrument still leaves a large remainder.**
The stage is doing something none of the three name, and the next step is
sub-timers inside `build_zoom` rather than a fix. An unattributed remainder is
where the next optimisation lives; it is not permission to guess.

## My prediction, registered

**Branch A.** 10s/frame is not plausible; ~449s across 3 zooms is 150s each,
which reads as fixed per-invocation cost rather than per-frame work. Round 47
also showed per-zoom cost *rising* as zoom count *fell* (72.4s/zoom at n=8 vs
152.9s/zoom at n=3), which is the signature of a fixed cost divided by fewer
invocations.

That prediction is registered so that if B or D lands, it is on the record that
I was wrong rather than quietly re-derived.

## What is NOT in scope either way
No quality trade. Zac's standing law is that quality wins over speed in every
trade, and none of these fixes touches output fidelity — A is process
architecture, B is a defect, D is instrumentation.
