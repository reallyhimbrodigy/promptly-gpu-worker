"""MG ENTRANCE STEP AUDIT — which motion graphics actually STEP at 30fps.

Frame COUNT is not the defect; CONCENTRATION is. A 12-frame spring that does 60%
of its travel in one frame reads worse than a 6-frame curve that spreads evenly.
So this measures the MG analogue of the zoom's px/frame cap:

    peak_step = the largest fraction of the entrance's TOTAL TRAVEL (peak
                presence minus starting presence) that lands in ONE DELIVERED
                frame at 30fps.
    effective positions = 1 / peak_step. Below ~2 is the "low frame rate" read.

Feed it the OFF-arm battery renders (60fps), which it decimates to the 30fps
delivery grid:
    node src/remotion/mg-attack-battery.mjs /tmp/mg-off
    python3 mg_entrance_step_audit.py /tmp/mg-off
"""
import glob
import os
import subprocess
import sys

import numpy as np

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mg-off"
STEPS, MARGINAL = 0.34, 0.22   # >=1/3 of travel in one frame == <=3 positions


def luma(p, w=192, h=341):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-vf",
                          f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    n = len(raw) // (w * h)
    return None if n == 0 else np.frombuffer(
        raw[:n * w * h], dtype=np.uint8).reshape(n, h, w).astype(np.float32)


rows = []
for f in sorted(glob.glob(os.path.join(OUT, "*.mp4"))):
    key = os.path.splitext(os.path.basename(f))[0]
    fr = luma(f)
    if fr is None or fr.shape[0] < 8:
        continue
    pres = np.abs(fr - 128.0).mean(axis=(1, 2))
    p30 = pres[::2]                                # 60fps battery -> 30fps grid
    if float(p30.max()) < 0.02:
        continue                                   # blank probe props
    # NORMALISE BY TOTAL TRAVEL, not by a mid-entrance "steady" sample. The
    # earlier version sampled steady at 400-700ms, which lands INSIDE a long
    # staged entrance and under-reads the plateau: StepDivider measured 0.198
    # there vs 2.362 once settled, a 12x error that inflated its peak_step to
    # 3.10 and made a marginal component look like the worst in the set. Against
    # true travel it is 0.24. Reticle likewise fell 0.67 -> 0.25. Normalising by
    # the full excursion is scale-free and immune to both build-up and decay.
    travel = float(p30.max() - p30[0])
    if travel <= 0:
        continue
    peak_i = int(p30.argmax())                     # entrance ends at the peak
    d = np.abs(np.diff(p30[:max(4, peak_i + 1)])) / travel
    rows.append((key, float(d.max()), int((d > 0.02).sum())))

print(f"{'component':<18}{'peak_step':>10}{'eff.pos':>9}{'span_f30':>10}")
print("-" * 50)
for k, peak, span in sorted(rows, key=lambda x: -x[1]):
    flag = "  STEPS" if peak >= STEPS else ("  marginal" if peak >= MARGINAL else "")
    print(f"{k:<18}{peak:>10.2f}{(1 / peak if peak else 99):>9.1f}{span:>10}{flag}")
print(f"\nSTEPS: {sorted(k for k, p, _ in rows if p >= STEPS)}")
