# What each ported transition costs in px/frame — measured, not assumed

Every transition body declares `NO VELOCITY CAP:` except ZoomThrough, which
carries the module for its CURVE and does not apply the ceiling. An exemption
nobody measured is the failure the build step exists to prevent, so here are the
numbers.

Measured at **1080x1920, 30fps, centred origin** (corner 1101.45 px), with the
SAME `peakDisplacementPx` the cap itself uses for scale moves; translate moves
are differenced directly in px. Cap is **11 px/frame**.

| component | what the move is | peak px/frame | vs cap |
|---|---|---|---|
| **DipToBlack** | opacity only — no geometry at all | **0.0** | — |
| SlideOver | B slides a full frame width in 16f | 126.6 | **11.5x** |
| ZoomThrough | A driven to 3x in 14f, our trapezoid | 321.7 | **29.2x** |
| CardSwipe | A thrown 120% of width in 16f | 328.2 | **29.8x** |

## Reading these

**DipToBlack needs no argument at all.** It moves no pixels — the dip is pure
opacity — so its exemption is a fact rather than a judgement. That is worth
separating from the other three, which are genuine decisions.

**The other three are 11x to 30x over, and that is the point.** The ceiling
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
