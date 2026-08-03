"""A DEAD MOMENT that is dead in the SOURCE is the user's footage, not our hole.

The gate computes  silence ∩ (freeze ∪ black)  and called it `both_stream_hole`.
That name says "a segment is missing"; the detector actually measures "nothing
is happening" — a dead MOMENT. The name cost hours of investigation today
(reasoning about frame math and mux gaps for something that is a content
measurement), so the check is renamed `dead_moment`.

WHY THE ECHO MISSED IT. black and freeze are each source-echoed individually,
but the intersection never was. The only hole relief was subtracting spans that
had ALREADY been downgraded — which requires them to have cleared their trip
floors first (_IG_FREEZE_TRIP_S / the black residual path). A short freeze or
black span below those floors never enters the echo, so a hole built from it is
never subtracted. And the SILENCE half was never checked against source silence
at all.

Job 7e8a303f tripped freeze + black + both_stream_hole on the SAME 96.2s clip
that carries 7.97s of its own black (proven by forced repro 017fa6d3). The echo
would have cleared both halves; the intersection tripped anyway.

THE RULE: if BOTH constituents of the intersection are source-echoed — the
source is silent there AND the source is black or frozen there — the dead moment
is the user's own footage and must be downgraded. If the SOURCE is live at that
moment, the output being dead is our defect and must still trip.
"""
import os
import subprocess
import sys
import tempfile

import handler as H

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


def make_source():
    """4s. 0-2s: black video + silent audio (a DEAD source moment).
           2-4s: moving noise + a tone (a LIVE source moment)."""
    fd, path = tempfile.mkstemp(suffix="_dead.mp4")
    os.close(fd)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "color=c=black:s=320x240:r=30:d=2",
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=2",
         "-f", "lavfi", "-i", "nullsrc=s=320x240:r=30:d=2",
         "-f", "lavfi", "-i", "sine=frequency=440:r=48000:d=2",
         "-filter_complex",
         "[2:v]geq=random(1)*255:128:128[n];"
         "[0:v][1:a][n][3:a]concat=n=2:v=1:a=1[v][a]",
         "-map", "[v]", "-map", "[a]", "-pix_fmt", "yuv420p", path],
        capture_output=True, timeout=240)
    return path


SRC = make_source()
print(f"fixture: 4s — 0-2s DEAD (black+silent), 2-4s LIVE (noise+tone)  "
      f"({os.path.getsize(SRC)} bytes)\n")

print("=== D0: the helper reads source silence ===")
check("source 0-2s is silent", H._ig_window_is_silent(SRC, 0.3, 1.2) is True)
check("source 2-4s is NOT silent", H._ig_window_is_silent(SRC, 2.4, 3.4) is False)

print("\n=== D1: a dead moment over a DEAD source is downgraded ===")
d, g = H._ig_source_echo_hole(SRC, [(0.4, 1.4)], lambda t: t)
check("source silent AND black -> downgraded, not a hole",
      len(g) == 1 and not d, f"d={d} g={g}")

print("\n=== D2: THE GUARD — a dead moment over a LIVE source still trips ===")
d, g = H._ig_source_echo_hole(SRC, [(2.4, 3.4)], lambda t: t)
check("source live -> the output being dead is OUR defect and must trip",
      len(d) == 1 and not g, f"d={d} g={g}")

print("\n=== D3: only ONE constituent dead is NOT enough ===")
# Map the output span onto a source window that is silent but NOT black:
# 2-4s is noise (live video) — build a mapping that lands there while the
# output span itself is short. Video live => must still trip.
d, g = H._ig_source_echo_hole(SRC, [(0.4, 1.0)], lambda t: t + 2.0)
check("source video LIVE (even if we only checked audio) -> still a defect",
      len(d) == 1 and not g, f"d={d} g={g}")

print("\n=== D4: crossing a cut, both windows over a DEAD source ===")
def crossing(t):
    return 0.9 + t if t < 1.0 else t - 1.0      # backward cut, both ends in 0-2s


d, g = H._ig_source_echo_hole(SRC, [(0.9, 1.1)], crossing)
check("boundary-crossing dead moment over dead source -> downgraded",
      len(g) == 1 and not d, f"d={d} g={g}")

print("\n=== D5: fail closed on an unmappable endpoint ===")
d, g = H._ig_source_echo_hole(SRC, [(0.4, 1.4)], lambda t: None)
check("no mapping -> stays a defect", len(d) == 1 and not g, f"d={d}")

print("\n=== D6: the check is RENAMED to dead_moment ===")
_src = open("handler.py").read()
check("gate emits check='dead_moment'", '"check": "dead_moment"' in _src)
check("the misleading name is gone", '"check": "both_stream_hole"' not in _src)

os.unlink(SRC)
print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print(f"  FAILED: {f}")
sys.exit(1 if FAIL else 0)
