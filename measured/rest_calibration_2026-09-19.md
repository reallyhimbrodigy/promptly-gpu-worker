# The rest offset is a calibration — measured, derived, gated

## The finding

Our layer at scale 1.0 renders the source **brighter than the base item does**: a
flat additive offset, independent of level, saturation and channel. It is not
encode noise (survives 16x downsampling), not geometry (uniform across the frame,
97% of pixels), not a gain, not a gamma, and **not a limited-to-full range
expansion** — that would predict −13.4 at level 32 and +12.9 at level 192; the
measurement is +2.0 flat at both.

It is identical across four component variants — no background, our black root
background, `objectFit: fill`, and `transform: scale(1)` — to four decimal places
with the same worst pixel. **It belongs to the `<Video>` path inside a motion
graphic, not to our code.**

## Why it is a calibration and not a constant (Zac's ruling)

**It moved between two runs of the same arm on the same source:**

| run | R | G | B | mean |
|---|---|---|---|---|
| first | +2.2725 | +1.7784 | +2.0581 | **+2.0363** |
| second | +1.9300 | +1.5172 | +1.7212 | **+1.7228** |

A number written into the source would have been right on the day it was measured
and silently wrong after.

## The correction, and why it is CSS and not SVG

An SVG `feComponentTransfer` with a linear intercept is the textbook inverse of an
additive offset. **Inside a ChatCut motion graphic it does nothing** — proven at a
hundred times the magnitude: an intercept of −128/255 produced a frame identical
to no filter at all (worst pixel 34, same as uncorrected), while a CSS
`brightness(0.5)` on the same component in the same run moved the worst pixel to
157. CSS filters apply here; `url(#...)` filters do not.

CSS has no additive primitive, but two of its functions compose into one:

    brightness(b):  out = b * in
    contrast(c):    out = c * in + 0.5 * (1 - c)
    together:       out = (c*b) * in + 0.5 * (1 - c)

With `c = 1 + 2k/255` and `b = 1/c`: slope **exactly 1.000000**, intercept
**exactly −k levels**. A pure offset — the shape the measurement demands. A bare
`brightness()` multiply would be the wrong shape and correct at one level only.

## The result

    OFFSET     R +1.9300  G +1.5172  B +1.7212   over 7 frames
    DERIVED    subtract 1.7228 levels -> brightness(0.986668) contrast(1.013512)
    RESIDUAL   R +0.4001  G -0.0081  B +0.2156
    VERDICT    CALIBRATED — worst channel +0.4001, inside the 0.5 tolerance

The correction is uniform across channels because that is what CSS offers, while
the measured offset varies by ~0.4 levels between red and green. **That spread is
exactly what the tolerance judges**, and it is why the residual is reported per
channel rather than averaged.

## What is corrected, and what is not

**Only our own layer.** The base is never touched. Correcting the base would be
grading the whole video to fix a component.

Each ported component takes the correction as a `correct` property supplied by the
harness. No level is written into any blob.

## Still open

The partner email stands regardless: this is their video path, a flat offset
independent of level, saturation and channel, and it is the kind of thing fixed
upstream rather than compensated downstream forever.
