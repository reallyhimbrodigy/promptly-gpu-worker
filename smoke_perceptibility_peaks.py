#!/usr/bin/env python3
"""The source stays perceptible through every full-frame overlay, at its peak.

THIS RE-RUNS THE MEASUREMENT; IT DOES NOT READ A RECORDED NUMBER. The fixture
lives in the tree (measured/perceptibility_fixture.jpg) precisely so the bar is
re-derived on every run and cannot quietly become a number somebody typed. A
gate that compares a constant against a constant in a JSON file is checking that
two copies agree, which is the class lane_contract.py exists to delete.

WHY IT IS A GATE AT ALL. ShutterFlashOverlay learned this in June — 0.95 made
the speaker a near-invisible silhouette, 0.82 kept them readable — and the
lesson stayed inside ShutterFlash. LightLeakOverlay shipped its l2 bloom at 1.00
and nothing anywhere noticed, because a too-strong overlay renders a perfectly
valid frame: right duration, right colour, real footage, no error. It is the
third failure class, real and wrong, and only a comparison against the SOURCE
sees it.

AND THE BORROW IS WHY THE MEASUREMENT HAD TO HAPPEN. Carrying 0.82 across from
ShutterFlash scored 0.1402 here — still under the bar. The borrowed number was
not conservative, it was wrong in the same direction, on a composite whose
blend mode and colour are both different. Measured answer: 0.71.
"""
import os
import re
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import measure_perceptibility as M                             # noqa: E402

FIXTURE = os.path.join(HERE, "measured", "perceptibility_fixture.jpg")
BODIES = os.path.join(HERE, "port", "bodies")
FAILS = []


def leg(name, ok, got):
    print("  %-36s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    if not os.path.exists(FIXTURE):
        print("HARNESS FAILURE: no fixture at %s — the bar cannot be derived" % FIXTURE)
        return 2
    src = np.asarray(Image.open(FIXTURE).convert("RGB"), dtype=np.float64) / 255.0
    base = M.detail_rms(src)
    # A FLAT FIXTURE MAKES EVERY COMPOSITE LOOK LEGIBLE. Refuse, do not divide.
    if base <= 1e-3:
        print("HARNESS FAILURE: fixture has no detail to retain (rms=%.6f)" % base)
        return 2
    print("  fixture detail rms %.5f" % base)

    bar = M.detail_rms(M.shutterflash(src, 0.82)) / base
    rejected = M.detail_rms(M.shutterflash(src, 0.95)) / base

    # L0 THE INSTRUMENT MUST ORDER TWO KNOWN-GOOD/KNOWN-BAD POINTS CORRECTLY.
    # Without this the whole gate could be measuring nothing and still pass:
    # 0.82 SHIPPED and 0.95 was rejected as a blown exposure, so retention at
    # 0.82 has to be materially higher. A check calibrated on one point cannot
    # tell a working instrument from a broken one.
    leg("L0 instrument_separates_known_pair", bar > rejected * 1.5,
        "0.82 -> %.4f vs 0.95 -> %.4f" % (bar, rejected))

    # Re-solve the ceiling for LightLeak's l2 on this run.
    lo, hi = 0.0, 1.0
    if M.detail_rms(M.lightleak(src, 0.0)) / base < bar:
        leg("L1 ceiling_is_solvable", False, "even l2 off is under the bar")
        solved = 0.0
    else:
        for _ in range(40):
            mid = (lo + hi) / 2
            if M.detail_rms(M.lightleak(src, mid)) / base >= bar:
                lo = mid
            else:
                hi = mid
        solved = lo
        # L1 a degenerate solve (0.0 or 1.0) means the bisection learned nothing.
        leg("L1 ceiling_is_solvable", 0.02 < solved < 0.99, "solved %.3f" % solved)

    # L2 ShutterFlash's registered peak has not been raised. Its label says
    # "do not raise" and a label is not a gate.
    import json
    props = json.load(open(os.path.join(HERE, "port", "transition_properties.json")))
    found = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("key") == "peak":
                found.append(float(o.get("defaultValue")))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(props)
    leg("L2 shutterflash_peak_not_raised", bool(found) and max(found) <= 0.82,
        "registered peak(s) %s" % found)

    # L3 LightLeak's shipped l2 constant is at or under the solved ceiling.
    body = open(os.path.join(BODIES, "LightLeakOverlay.jsx"), encoding="utf-8").read()
    m = re.search(r"l2Opacity\s*=\s*interpolate\([^)]*?\[\s*0\s*,\s*([\d.]+)\s*\*\s*intensity", body)
    shipped = float(m.group(1)) if m else None
    leg("L3 lightleak_l2_under_ceiling",
        shipped is not None and shipped <= solved + 1e-3,
        "shipped %s vs ceiling %.3f" % (shipped, solved))

    # L4 the retained detail at the SHIPPED value clears the bar. L3 compares
    # two numbers; this one asks the question directly on pixels, so a mistake
    # in the solve cannot pass both.
    if shipped is not None:
        got = M.detail_rms(M.lightleak(src, shipped)) / base
        leg("L4 shipped_value_clears_the_bar", got >= bar,
            "retained %.4f vs bar %.4f" % (got, bar))

    print("%d/%d legs ok" % (5 - len(FAILS), 5))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
