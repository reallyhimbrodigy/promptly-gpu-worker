# Falsifier — the localised placement-effect measure

**Committed BEFORE any arm exists.** No region measure has been written, no
fixture rendered, no number produced. Same discipline as Builder-1's
`zoom_bar_fourth_population.py`, and for the same reason: this lane has now set
three thresholds from the wrong measurement, and each was defensible at the
moment it was fitted.

## What is being replaced and why

`_record_effect` compares GLOBAL PSNR over the placement window against global
PSNR over a control window, and calls the placement real when the difference
clears `_VIDEO_REL_MARGIN_DB = 3.0`.

A StatCard covers a small fraction of a 1080x1920 frame. Averaged over the whole
frame, a correctly rendered card moves global PSNR about as much as encode noise
moves the control window. Round 42, Zac's real footage: **three false
`placement_inert` failures on cards that render correctly and legibly** — "10
TIMES A DAY" with a StatCard reading 10 / POSTS PER DAY. Observed margins
clustered 1.58-3.29 against a 3.0 bar, so the verdict turned on about 1 dB.

The metric is wrong, not the constant. Moving 3.0 is the thing this lane has done
three times.

## The replacement, in one line

Compare only the pixels inside the placement's own bounds against the same region
of the same frames without the placement — so a small overlay on a large frame is
not averaged away.

## Where the bounds come from

The alpha layer the components paint into. Painted pixels ARE the placement's
bounds; nothing else needs to know a component's geometry. This also makes the
empty-alpha case fall out rather than needing a separate rule: no painted pixels
means no region, which is a different answer from "a region that did not change".

## The four states, and none of them may be silent

    CHANGED     a region exists and it differs from the same region without
                the placement
    INERT       a region exists and it does NOT differ
    EMPTY       no painted pixels — the layer composited and painted nothing
    UNMEASURED  the region could not be read at all

EMPTY and UNMEASURED must never report as CHANGED or as INERT. The distinction
between EMPTY and INERT is the case that started this: an empty alpha layer
composites, re-encodes, changes the file, and passes a global check.

## Arms, before they are rendered

On **both** corpora — v1 (`reliability-fixtures-v1`, synthetic) and v3
(`reliability-fixtures-v3`, Zac's real footage). Per corpus:

    A  REAL OVERLAY      a StatCard rendering correctly, composited
    B  EMPTY ALPHA       an alpha layer with nothing painted, composited
    C  NULL REGION       the same box at a time with no placement
    D  TEXT OVERLAY      a smaller painted region than a card, same treatment

A and D must read CHANGED. B must read EMPTY. C must read INERT.

## Ship criteria — all four required

1. **Correctness**: 4/4 arms per corpus land in their stated state, on both.
2. **Separation**: across the UNION of both corpora, the window between the
   worst CHANGED arm and the best INERT arm is **>= 4.0 dB wide**, so a bar at
   its midpoint carries **>= 2.0 dB either side**. Same standard registered for
   the zoom bar, applied consistently rather than re-derived to fit.
3. **One constant, both corpora.** A bar that works on v1 and not v3, or the
   reverse, is NOT SHIPPED. Picking the corpus where the number works is exactly
   what produced the absolute geometry bar, the scale-fit bar and the 3.0 here.
4. **EMPTY is separable by state, not by threshold.** If EMPTY can only be told
   from INERT by where it falls on the dB axis, the measure has not actually
   distinguished them and does not ship.

## What I will do if it fails

Report `placement_effect` UNMEASURED, exactly as Zac ruled for zoom geometry, and
leave `placement_inert` unable to fail a round. **Unmeasured is honest and cheap;
mismeasured is expensive and looks like knowledge** — and here it has already
cost three false failures pointing at working components.

I will not widen the margin requirement after seeing the numbers, and I will not
ship on one corpus. If I want to change either, that is a new pre-registration
with its reasons stated before the next measurement, not an edit to this file.

## What this cannot answer

Whether a placement is any GOOD. It measures that the pixels changed where the
placement claimed they would. Editorial fit is not a PSNR question and this
instrument must not be read as one.
