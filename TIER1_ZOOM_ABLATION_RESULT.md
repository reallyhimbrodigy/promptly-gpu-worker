# Tier 1 — zoom-type ablation: composite zooms are the lever

**Question:** does a scale-only zoom cost what a composite one costs? If yes, the
~939 ms/frame is the composition frame itself (source decode + 1080×1920 paint)
and Tier 2 per-component profiling has nothing to find.

**Answer: no.** The effect implementation is the cost. Tier 2 is worth doing and
its target is named.

## Method

One harvested plan (35 cuts, 5 carrying `_zoom_effect`), `mode=render_only` on
the durable source `ab-sources/talking-head-v1/625dfdc5-73s.mp4`. Each arm
rewrites `cuts[]._zoom_effect.type` to a single value — scale, timing and events
untouched — so the frame set is identical and only the component changes. The
`NONE` arm strips the key, which routes the clip through `categorize_clip` to
FFmpeg.

## Result

| arm | kind | frames | ms/frame | render stage | vs NONE |
|---|---|---|---|---|---|
| StepZoom | scale-only | 271 | **785** | 96.9s | −6.6s |
| SnapReframe | scale-only | 271 | — | 102.8s | −0.7s |
| **NONE** | no zoom | **0** | — | 103.5s | — |
| FocusWindow | composite | 271 | **1164** | 132.8s | +29.3s |
| LetterboxPush | composite | 271 | **1796** | 173.7s | +70.2s |

**LetterboxPush costs 2.3× StepZoom per frame on identical work.**

## The two checks that make this readable

1. **Frame counts equal** — all four zoom arms rendered the same 271 frames.
2. **The lever provably moved** — `NONE` rendered **zero** micro chunks. In the
   first (invalid) run the baseline still rendered 271 frames, which is exactly
   what a no-op plan edit looks like when nobody counts.

## What this changes

- **Scale-only zooms are free.** StepZoom and SnapReframe land at or below the
  no-zoom baseline. Rendering them in Remotion costs about what rendering the
  clip in FFmpeg costs — so retiring the crop+lanczos path (forced by ffmpeg
  n7.1 dropping per-frame `out_w`/`out_h` evaluation) cost far less than the
  ~1000 ms/frame headline implied.
- **The headline was a mix.** This plan is 3 SnapReframe + 1 StepZoom + 1
  LetterboxPush, so ~974 ms/frame blended a 2.3× spread and pointed at "micro is
  expensive" instead of "two composite implementations are expensive".
- **Tier 2 has a target:** LetterboxPush (1796) first, FocusWindow (1164)
  second. Not "profile PromptlyMicroSegments" — profile those two components.

## Limits

- n=1 per arm; arms were dispatched concurrently, so absolute walls carry host
  contention. Per-frame ordering is robust (identical frame set), but a 6% gap
  is noise where a 129% one is not.
- **DepthPull and StagedPush are untested.** No conclusion about composites *as
  a class* until they are measured.
- SnapReframe's ms/frame was not captured in the log window; its render-stage
  wall (102.8s vs 103.5s baseline) carries the same conclusion.
