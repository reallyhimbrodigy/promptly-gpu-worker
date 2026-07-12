"""WS1 MG entrance-arrival measurement. For each clip rendered by
mg-attack-battery.mjs, decode luma frames and compute per-frame PRESENCE =
mean(|Y - 128|) (deviation from the mid-gray plate = how much of the graphic
is drawn). The ENTRANCE arrival = the first frame where presence reaches 90% of
its steady value (median of the late frames) — the moment the graphic has
visually arrived, robust across fade/slide/scale/spring and immune to ongoing
content animation. attack_ms = arrival_frame / fps * 1000.
Usage: python3 measure_mg_attack.py <outDir>  [fps]"""
import glob
import os
import subprocess
import sys

import numpy as np

outDir = sys.argv[1] if len(sys.argv) > 1 else "mg-attack-out"
fps = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0


def luma_frames(path, w=192, h=341):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h},format=gray",
           "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (w * h)
    if n == 0:
        return None
    return np.frombuffer(raw[:n * w * h], dtype=np.uint8).reshape(n, h, w).astype(np.float32)


print(f"{'type':<20}{'hit_ms':>8}{'settle_ms':>10}{'steady':>8}   (hit=peak entrance velocity; settle=90% of the entrance plateau)")
rows = []
for f in sorted(glob.glob(os.path.join(outDir, "*.mp4"))):
    key = os.path.splitext(os.path.basename(f))[0]
    fr = luma_frames(f)
    if fr is None or fr.shape[0] < 8:
        print(f"{key:<20}  (no frames)")
        continue
    presence = np.abs(fr - 128.0).mean(axis=(1, 2))   # per-frame presence
    n = presence.shape[0]
    # steady = the ENTRANCE plateau, referenced at ~0.4-0.7s (frames 24-42) so
    # sequenced/count-up CONTENT that keeps building past the entrance doesn't
    # inflate the target. Cap to available frames.
    lo, hi = min(24, n - 1), min(42, n)
    steady = float(np.median(presence[lo:hi])) if hi > lo else float(np.median(presence))
    if steady < 0.02:
        print(f"{key:<20}  (blank render — presence≈{steady:.3f}; props wrong)")
        continue
    # HIT: frame of peak presence-velocity (the entrance's fastest appearance —
    # the container popping/sliding/fading in), immune to later content build.
    vel = np.diff(presence)
    hit_f = int(np.argmax(vel)) + 1
    # SETTLE: first frame reaching 90% of the entrance plateau (fully arrived).
    above = np.where(presence >= 0.9 * steady)[0]
    settle_f = int(above[0]) if above.size else hit_f
    rows.append((key, hit_f / fps * 1000.0, settle_f / fps * 1000.0, steady))
    print(f"{key:<20}{hit_f / fps * 1000.0:>8.0f}{settle_f / fps * 1000.0:>10.0f}{steady:>8.2f}")
print(f"\nMEASURED: {len(rows)} types")
if rows:
    print("settle_ms range:", round(min(r[2] for r in rows)), "-", round(max(r[2] for r in rows)))
