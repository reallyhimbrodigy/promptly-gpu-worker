#!/usr/bin/env python3
"""A transition carries BOTH SIDES of the cut: no frame of the ramp shows the root.

Ruled by Zac 2026-09-21 on SlideOver: "the uncovered region shows the outgoing
clip, never black."

WHY THIS IS ARITHMETIC AND NOT A LOOK. The gap opens for part of the ramp and
closes at both ends, so the two frames anyone naturally samples — the start and
the seam — are exactly the two that look correct. SlideOver's worst moment is
around e=0.7 and its endpoints are both clean. A still can only ever catch this
by luck; the ramp can be checked in full.

IT READS THE SHIPPED NUMBERS. The endpoints are parsed out of the body itself,
so this is not a second copy of the geometry that can drift from it — change a
lerp in the .jsx and this check changes with it. What it knows independently is
only the PROPERTY: the union of the layers covers the canvas at every sample.

BOTH SIGNS ARE TESTED. `direction` picks sign = +/-1 and the two are mirror
images, so a defect that exists in one direction exists in both — but a fix
applied to one and not the other is exactly the kind of half-repair that passes
a single-direction check.

AND IT REFUSES WHAT IT CANNOT MODEL, WHICH IS THE WHOLE REASON THIS DOCSTRING
IS LONG. The first version assumed both layers translate horizontally in
percent, because that is what SlideOver does and the variables are named the
same in both files. CardSwipe's B layer is `translateY(<px>)` — a VERTICAL
PIXEL RISE underneath, while A swipes off on top — so the model was wrong and
it printed 42.24%, a confident number about geometry that does not exist. I was
one edit from "fixing" a component on it.

So the axis and unit are now READ FROM THE TRANSFORM STRING, and a layer this
cannot model makes the component UNMODELLED — named and counted, never silently
skipped and never given a number. A measurement of the wrong thing is worse
than no measurement, because only one of the two stops you.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BODIES = os.path.join(HERE, "port", "bodies")
FAILS = []


def leg(name, ok, got):
    print("  %-34s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def _endpoints(src, name, sign):
    """-> (from, to) for `const <name> = lerp(e, A, B);`, or None if absent."""
    m = re.search(r"const\s+%s\s*=\s*lerp\(\s*e\s*,\s*([^,]+?)\s*,\s*([^)]+?)\s*\)" % name, src)
    if not m:
        return None
    def val(tok):
        tok = tok.strip()
        # the only non-literal form these bodies use is `sign * N` / `-sign * N`
        s = re.match(r"^(-?)sign\s*\*\s*(-?[\d.]+)$", tok)
        if s:
            return (-1 if s.group(1) == "-" else 1) * sign * float(s.group(2))
        return float(tok)
    return val(m.group(1)), val(m.group(2))


def _axis_and_unit(src, transform_var):
    """-> ('x'|'y', '%'|'px') for the transform that consumes this variable.

    Read from the template literal that actually renders, not assumed from the
    variable's name. `translateY(${translateB}px)` and `translateX(${translateA}%)`
    are different geometry wearing near-identical names.
    """
    m = re.search(r"translate([XY])\(\$\{%s\}(%%|px)\)" % re.escape(transform_var), src)
    if not m:
        return None
    return m.group(1).lower(), m.group(2)


def _span(e, tr, sc):
    t = tr[0] + (tr[1] - tr[0]) * e
    s = sc[0] + (sc[1] - sc[0]) * e
    return (50 - 50 * s + t, 50 + 50 * s + t), s


def worst_gap(src, sign, samples=101, grid=120):
    """-> worst UNCOVERED AREA of the canvas, as a % , over the whole ramp.

    TWO DIMENSIONS, BECAUSE ONE DIMENSION GAVE A FALSE PASS. The first version
    tracked width and height separately and asked whether ANY layer was full
    height — so SlideOver's A shrinking to 0.92 was reported as covered, on the
    strength of a full-height B that only spanned part of the width. The red
    proof caught it: restoring the real scale defect left the check green.
    A layer covers a RECTANGLE, and only the union of the rectangles answers it.
    """
    tA = _endpoints(src, "translateA", sign)
    tB = _endpoints(src, "translateB", sign)
    if tA is None or tB is None:
        return None
    for var in ("translateA", "translateB"):
        au = _axis_and_unit(src, var)
        if au != ("x", "%"):
            return ("UNMODELLED", "%s is %s" % (var, "absent" if au is None else "translate%s in %s" % (au[0].upper(), au[1])))
    sA = _endpoints(src, "scaleA", sign) or (1.0, 1.0)
    sB = _endpoints(src, "scaleB", sign) or (1.0, 1.0)
    worst = 0.0
    for i in range(samples):
        e = i / (samples - 1)
        rects = []
        for tr, sc in ((tA, sA), (tB, sB)):
            t = tr[0] + (tr[1] - tr[0]) * e
            sv = sc[0] + (sc[1] - sc[0]) * e
            # scale is about the centre; translate is horizontal, in % of canvas
            rects.append((50 - 50 * sv + t, 50 + 50 * sv + t,
                          50 - 50 * sv, 50 + 50 * sv))
        uncovered = 0
        for gx in range(grid):
            x = (gx + 0.5) * 100.0 / grid
            for gy in range(grid):
                y = (gy + 0.5) * 100.0 / grid
                if not any(x0 <= x <= x1 and y0 <= y <= y1 for x0, x1, y0, y1 in rects):
                    uncovered += 1
        worst = max(worst, 100.0 * uncovered / (grid * grid))
    return worst


def main():
    bodies = sorted(f for f in os.listdir(BODIES) if f.endswith(".jsx"))
    twolayer = []
    for f in bodies:
        src = open(os.path.join(BODIES, f), encoding="utf-8").read()
        if _endpoints(src, "translateA", -1) and _endpoints(src, "translateB", -1):
            twolayer.append((f[:-4], src))

    # A CHECK OVER AN EMPTY POPULATION ASSERTS NOTHING.
    leg("L0 population_nonempty", len(twolayer) >= 2,
        "%d two-layer transition(s): %s" % (len(twolayer), ", ".join(n for n, _ in twolayer)))
    if not twolayer:
        print("0/0 — refusing to report a pass over an empty population")
        return 1

    bad_x, unmodelled = [], []
    for name, src in twolayer:
        for sign in (-1, 1):
            g = worst_gap(src, sign)
            if g is None:
                continue
            if isinstance(g, tuple) and g[0] == "UNMODELLED":
                if sign == -1:
                    unmodelled.append("%s (%s)" % (name, g[1]))
                continue
            tag = "%s(dir %s)" % (name, "left" if sign == -1 else "right")
            print("     %-22s worst uncovered AREA  %6.2f%%" % (tag, g))
            if g > 0.01:
                bad_x.append("%s %.2f%%" % (tag, g))

    leg("L1 no_root_showing_any_frame", not bad_x, "%s" % (bad_x or "none"))

    # L3 THE REFUSALS ARE VISIBLE, and the number of MODELLED components is
    # asserted — otherwise a body drifting out of the model would quietly empty
    # this check while it went on printing a pass.
    modelled = len(twolayer) - len(unmodelled)
    leg("L3 unmodelled_are_named", modelled >= 1,
        "%d modelled, %d UNMODELLED %s" % (modelled, len(unmodelled), unmodelled or ""))

    print("%d/%d legs ok" % (3 - len(FAILS), 3))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
