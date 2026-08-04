"""The FREEZE source-echo must source-check a span even when it CROSSES A CUT.

Sibling of test_integrity_black_echo_boundary.py. _ig_source_echo (freeze) and
_ig_source_echo_black carried the SAME branch:

    if src_s is None or src_e is None or src_e <= src_s:
        defects.append((s, e)); continue      # freezedetect NEVER RUNS

out_to_src maps each endpoint through whichever clip contains it, so a span
straddling a cut resolves to DISCONTINUOUS source times. Whenever the next clip
starts earlier in the source (any reordering or backward cut) src_e <= src_s and
the span is filed as OUR defect without the source ever being looked at — so a
faithful render of the user's own STATIC footage fails the gate.

Evidence this is not theoretical: job 7e8a303f tripped
`freeze=[[43.066667, 43.9]]` on the same clip whose BLACK spans were proven to
be source content (job 017fa6d3, forced 2026-08-02).

THE SECOND CASE IS THE ONE THAT MATTERS. The freeze internals differ from black
(freezedetect, and no dark-scene fallback), so "crossing + source MOVING must
still trip" is what proves the fix is a repair and not a blanket downgrade.
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
    """4s: 0-2s a FROZEN still (single colour, no motion), 2-4s MOVING noise.

    freezedetect keys on frame-to-frame difference, so a flat colour reads as
    frozen and random noise never does.
    """
    fd, path = tempfile.mkstemp(suffix="_freeze.mp4")
    os.close(fd)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "color=c=green:s=320x240:r=30:d=2",
         "-f", "lavfi", "-i", "nullsrc=s=320x240:r=30:d=2",
         "-filter_complex",
         "[1:v]geq=random(1)*255:128:128[n];[0:v][n]concat=n=2:v=1:a=0[v]",
         "-map", "[v]", "-pix_fmt", "yuv420p", path],
        capture_output=True, timeout=180)
    return path


SRC = make_source()
print(f"fixture: 4s, 0-2s FROZEN (flat green), 2-4s MOVING (noise)  "
      f"({os.path.getsize(SRC)} bytes)\n")

print("=== F0: sanity — the fixture really is frozen then moving ===")
d, g = H._ig_source_echo(SRC, [(0.4, 1.4)], lambda t: t)
check("a span over the FROZEN half downgrades", len(g) == 1 and not d, f"d={d} g={g}")
d, g = H._ig_source_echo(SRC, [(2.4, 3.4)], lambda t: t)
check("a span over the MOVING half stays a defect", len(d) == 1 and not g, f"d={d} g={g}")

print("\n=== F1: THE BUG/FIX — crossing a cut, both ends over FROZEN source ===")
# clip A: output 0.0-1.0 -> source 0.9-1.9 (frozen)
# clip B: output 1.0-2.0 -> source 0.0-1.0 (ALSO frozen, but EARLIER)
def crossing(t):
    return 0.9 + t if t < 1.0 else t - 1.0


src_s, src_e = crossing(0.9), crossing(1.1)
print(f"    out_to_src(0.9)={src_s:.2f}  out_to_src(1.1)={src_e:.2f}  "
      f"-> src_e <= src_s: {src_e <= src_s}")
check("the mapping really is discontinuous (this IS a boundary crossing)",
      src_e <= src_s)
check("BOTH mapped windows land in the FROZEN half", src_s < 2.0 and src_e < 2.0)
d, g = H._ig_source_echo(SRC, [(0.9, 1.1)], crossing)
check("crossing span over FROZEN source is DOWNGRADED, not tripped",
      len(g) == 1 and not d, f"d={d} g={g}")
check("and it records WHY it was downgraded",
      bool(g) and g[0].get("boundary_crossing") is True, str(g))

print("\n=== F2: THE CASE THAT MATTERS — crossing a cut over MOVING source ===")
# Both mapped windows land in the noise half: this is a REAL render defect and
# must still trip. Freeze internals differ from black, so this is the guard
# against turning the fix into a blanket downgrade.
def crossing_moving(t):
    return 2.4 + t if t < 1.0 else t + 1.4


d, g = H._ig_source_echo(SRC, [(0.9, 1.1)], crossing_moving)
check("crossing a cut over MOVING source is STILL our defect",
      len(d) == 1 and not g, f"d={d} g={g}")

print("\n=== F3: the cut no longer decides ===")
d2, g2 = H._ig_source_echo(SRC, [(0.9, 1.1)], lambda t: 0.9 + t)
check("same span inside ONE clip -> downgraded", len(g2) == 1 and not d2, f"d={d2} g={g2}")

print("\n=== F4: unmappable endpoint still fails closed ===")
d3, g3 = H._ig_source_echo(SRC, [(0.4, 1.4)], lambda t: None)
check("no mapping -> defect (never downgrade what we could not check)",
      len(d3) == 1 and not g3, f"d={d3}")

os.unlink(SRC)
print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print(f"  FAILED: {f}")
sys.exit(1 if FAIL else 0)
