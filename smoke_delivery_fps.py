#!/usr/bin/env python3
"""Output fps is a delivery rate, not the source's average.

motion's VFR source measured 35.905 fps; the pipeline normalised to CFR at
35.905 and DELIVERED at 35.905 — faithful, and a rate nothing plays at, with
20% more frames to paint at ~1,418 ms each. Standard rates survive; anything
else becomes 30. Through the real delivery_fps, and through the normalisation
line that uses it (a helper nobody calls is a helper).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402

fail = 0
for actual, want in ((35.905, 30.0), (29.97, 29.97), (30.0, 30.0), (59.94, 59.94),
                     (60.0, 60.0), (24.0, 24.0), (23.976, 23.976), (25.0, 25.0),
                     (50.0, 50.0), (47.3, 30.0), (120.0, 30.0), (0, 30.0), (None, 30.0)):
    got = A.delivery_fps(actual)
    if got != want:
        print(f"  *** delivery_fps({actual!r}) = {got}, want {want}")
        fail += 1
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "agentic_editor_app.py")).read()
if "_tgt = delivery_fps(float(_actual))" not in src:
    print("  *** the VFR normalisation does not go through delivery_fps — 35.905 would ship again")
    fail += 1
print(f"smoke_delivery_fps: {fail} wrong")
sys.exit(1 if fail else 0)
