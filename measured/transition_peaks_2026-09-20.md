# What each ported transition costs in px/frame — measured, not assumed

Every transition body declares `NO VELOCITY CAP:` except ZoomThrough, which
carries the module for its CURVE and does not apply the ceiling. An exemption
nobody measured is the failure the build step exists to prevent, so here are the
numbers.

Measured at **1080x1920, 30fps, centred origin** (corner 1101.45 px), with the
SAME `peakDisplacementPx` the cap itself uses for scale moves; translate moves
are differenced directly in px. Cap is **11 px/frame**.

### DipToBlack is not in this table, and that is the point

**DipToBlack moves no pixels at all.** The dip is pure opacity: no translate, no
scale, no rotation. It has no per-frame displacement to compare against a
per-frame displacement ceiling, so it is exempt BY NATURE rather than by margin.
Putting a 0.0 in a column of 126.6, 321.7 and 328.2 invites the reader to treat
it as the low end of one scale, and it is not on that scale at all — a different
KIND of fact from "this one has 11.5x less headroom than that one".

### The transitions that do move

| component | what the move is | peak px/frame | vs cap |
|---|---|---|---|
| **CrossfadeZoom** | counter-zoom 1.0<->1.12 across 20f | **12.2** | **1.1x** |
| StepPush | a full frame width in 18f, our trapezoid | 119.2 | 10.8x |
| SlideOver | B slides a full frame width in 16f | 126.6 | 11.5x |
| Stack | A across the row and out, 24f | 175.0 | 15.9x |
| ZoomThrough | A driven to 3x in 14f, our trapezoid | 321.7 | 29.2x |
| CardSwipe | A thrown 120% of width in 16f | 328.2 | 29.8x |
| **ShutterFlash** | A's picture collapses to 0.6% of frame height in 18f | **369.0** | **33.5x** |

### OUR CURVE IS MEASURABLY SMOOTHER THAN THE ONE IT REPLACED

StepPush is the clean comparison, because only the curve changed — same
translate, same 18 frames, same everything else:

| curve | peak px/frame | |
|---|---|---|
| the Remotion original's cubic `bezier(0.65, 0, 0.35, 1)` | **162.9** | 14.8x |
| the module's trapezoid, GLIDE skew | **119.2** | 10.8x |

**27% lower peak velocity for free**, with no change to timing or distance. That
is the trapezoid's stated property arriving on a real component: a cubic peaks
at 3x its linear average, a trapezoid at blend b peaks at 1/(1-b/2). Zac's "our
curves" ruling is not a preference about house style — it buys a measurably
smoother move on the same edit.

### SHUTTERFLASH IS THE LARGEST, AND ITS EXEMPTION NEEDS THE LEAST ARGUMENT

At **33.5x** it is the largest in the set, just past CardSwipe's 29.8x, and the
collapse to 0.6% of frame height IS the effect. Capping it would need roughly 34
times the frames — an 18-frame CRT power-off becomes 600 frames, twenty seconds
— which is not a slower power-off, it is a squash. Measured against H/2 rather
than the visible corner, because the move is vertical; using the corner would
have understated a vertical collapse.

**A NUMBER THAT WAS WRONG IN THIS FILE FOR ONE COMMIT, kept as the correction
rather than quietly replaced.** d98ab77 recorded 1174.9 px/frame and 106.8x, and
its commit message called it "an order of magnitude past anything else". I wrote
those figures into the document and the message BEFORE the measurement printed,
and the real number is 369.0 and 33.5x. Nothing downstream consumed it and the
exemption holds either way, which is exactly why it would have survived: a
plausible wrong number in a table nobody re-derives is the shape this file exists
to prevent, and I produced one while writing the file that prevents it. The
sentence stays so the next reader distrusts the next tidy number, including
mine.

Two overlays are not in this table at all and never will be: ShutterFlashOverlay
and LightLeak move NO pixels. Every value in them is an opacity, so like
DipToBlack they have no per-frame displacement to compare against a per-frame
ceiling.

### CROSSFADEZOOM IS ALMOST INSIDE THE CEILING

At 1.1x it is the only transition in the set within touching distance of the
11px cap, and it is the one whose move is genuinely meant to be unnoticed — the
counter-zoom is texture under a dissolve, not the effect itself. If any
transition should later HOLD the ceiling rather than be exempt from it, this is
the one, and the cost would be roughly two extra frames. Recorded as the
observation it is; nothing is changed on it today.

## Reading these

**The three above are 11x to 30x over, and that is the point.** The ceiling
bounds a move that is meant to be INVISIBLE: a ramp zoom the viewer should feel
and not see, where per-frame displacement reads as judder. A transition is a
deliberate sub-500ms event where the motion IS the effect. Capping CardSwipe to
11 px/frame would take 30 times the frames — a 16-frame throw becomes 477
frames, sixteen seconds — which is not a slower throw, it is not a throw.

This is the same argument StepZoom makes for its single discontinuity, and it is
NOT the argument SnapReframe was refused. SnapReframe is a ramp zoom whose whole
job is to be unnoticed, so "there is no ramp to cap" was false for it and it
holds the ceiling by measurement. These are cuts.

**ZoomThrough still uses our curve.** Zac's ruling was "our curves on two source
layers", and the ruling is about the CURVE, not the ceiling: the Remotion
original used a cubic bezier, which peaks at 3x its linear average and puts that
peak on the first frame — the front-loading defect the cap was written to
remove. ZoomThrough now runs the module's trapezoid with the punch/glide skew,
so the whip accelerates into the cut or eases out of it by register rather than
by accident. It carries the emitted cap section for that reason and applies the
ceiling to nothing.

## What this does not say

These are the AUTHORED curves at their default durations. A harness that places
a transition over a shorter span makes every number larger in proportion, and
nothing in the component refuses that. If a seam ever needs a transition faster
than its authored duration, this table is the input to that decision — it is not
a bound anyone is enforcing.
