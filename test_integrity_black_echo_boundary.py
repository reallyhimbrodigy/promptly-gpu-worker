"""The black source-echo must source-check a span even when it CROSSES A CUT.

FORCED REPRODUCTION (2026-08-02, job 017fa6d3 on the known black clip):

    INTEGRITY_TRIP: [echo: source=Y map=29.92 downgraded=4]
                    black=[[20.366667, 20.6], [41.7, 42.3]]

The diagnostic refuted both standing hypotheses: the source WAS readable
(source=Y) and the mapping DID resolve (map=29.92), and the echo ran and
downgraded FOUR spans. Two short ones survived and tripped anyway — and the
survivor is demonstrably source black:

    ffmpeg -ss 29.62 -t 0.833 -i <source> -vf blackdetect=d=0.20:pix_th=0.10
      -> black_duration:0.6      (a 0.233s output span needs only 0.14s to clear
                                  the 0.60 cover threshold — it clears by 4x)

So the defect is not the preconditions and not the threshold. It is this branch
in _ig_source_echo_black:

    if src_s is None or src_e is None or src_e <= src_s:
        defects.append((s, e)); continue        # blackdetect NEVER RUNS

out_to_src maps an OUTPUT time through whichever clip range contains it. A span
that straddles a cut has its start in clip A and its end in clip B — both
resolve, but to DISCONTINUOUS source times. Whenever clip B starts earlier in
the source than clip A (every reordering or backward cut), src_e <= src_s and
the span is filed as OUR defect without the source ever being looked at. The
user's own black then fails the gate.

THE FIX (now in place, and what this pins): a boundary-crossing span is
evaluated as the TWO source windows it actually covers and downgraded if EITHER
is source black — while a crossing span over NON-black source still trips, so
the gate keeps its real value.
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
    """4s clip: 0-2s pure BLACK, 2-4s white. Real file, real blackdetect."""
    fd, path = tempfile.mkstemp(suffix="_echo.mp4")
    os.close(fd)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "color=c=black:s=320x240:r=30:d=2",
         "-f", "lavfi", "-i", "color=c=white:s=320x240:r=30:d=2",
         "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
         "-map", "[v]", "-pix_fmt", "yuv420p", path],
        capture_output=True, timeout=120)
    return path


SRC = make_source()
print(f"fixture: 4s, 0-2s BLACK, 2-4s white  ({os.path.getsize(SRC)} bytes)\n")

print("=== E0: a span INSIDE one clip, over source black -> DOWNGRADED ===")
# out_to_src is monotonic here: output t -> source t (single clip, no cut).
defects, downgraded = H._ig_source_echo_black(SRC, [(0.4, 0.9)], lambda t: t)
check("source-black span is downgraded, not a defect",
      len(downgraded) == 1 and not defects, f"defects={defects} downgraded={downgraded}")

print("\n=== E1: a span over NON-black source -> stays a defect (gate still works) ===")
defects, downgraded = H._ig_source_echo_black(SRC, [(2.4, 2.9)], lambda t: t)
check("white source keeps the span as our defect",
      len(defects) == 1 and not downgraded, f"defects={defects} downgraded={downgraded}")

print("\n=== E2: THE FIX — a span CROSSING A CUT, both ends over source BLACK ===")
# Two clips. Output 0.0-1.0 -> source 0.9-1.9 (clip A, black).
# Output 1.0-2.0 -> source 0.0-1.0 (clip B, ALSO black, but EARLIER in source).
# A span straddling output t=1.0 maps to src_s=1.8, src_e=0.1 -> src_e <= src_s.
# BEFORE the fix this was filed as our defect without blackdetect ever running.
def crossing(t):
    return 0.9 + t if t < 1.0 else t - 1.0      # clip A then a BACKWARD cut

span = [(0.9, 1.1)]
src_s, src_e = crossing(0.9), crossing(1.1)
print(f"    out_to_src(0.9)={src_s:.2f}  out_to_src(1.1)={src_e:.2f}  -> src_e <= src_s: {src_e <= src_s}")
check("the mapping really is discontinuous (this IS a boundary crossing)",
      src_e <= src_s, f"src_s={src_s} src_e={src_e}")
check("BOTH mapped windows are source BLACK (0-2s of the fixture)",
      src_s < 2.0 and src_e < 2.0, f"src_s={src_s} src_e={src_e}")
defects, downgraded = H._ig_source_echo_black(SRC, span, crossing)
check("crossing span over source black is DOWNGRADED, not tripped",
      len(downgraded) == 1 and not defects, f"defects={defects} downgraded={downgraded}")
check("and it records WHY it was downgraded",
      bool(downgraded) and downgraded[0].get("boundary_crossing") is True, str(downgraded))

print("\n=== E3: the cut no longer decides — same span, with and without ===")
defects2, downgraded2 = H._ig_source_echo_black(SRC, [(0.9, 1.1)], lambda t: 0.9 + t)
check("same span inside ONE clip -> downgraded", len(downgraded2) == 1 and not defects2,
      f"defects={defects2} downgraded={downgraded2}")
check("SO CROSSING A CUT IS NO LONGER THE DIFFERENCE (both downgrade now)",
      bool(downgraded) and bool(downgraded2))

print("\n=== E3b: NOT over-corrected — crossing over NON-black still trips ===")
def crossing_white(t):
    return 2.4 + t if t < 1.0 else t + 1.4      # both windows land in WHITE
defects3, downgraded3 = H._ig_source_echo_black(SRC, [(0.9, 1.1)], crossing_white)
check("crossing a cut over white source is STILL our defect",
      len(defects3) == 1 and not downgraded3, f"defects={defects3} downgraded={downgraded3}")

print("\n=== E4: an UNRESOLVABLE endpoint must still fail closed (unchanged) ===")
defects3, downgraded3 = H._ig_source_echo_black(SRC, [(0.4, 0.9)], lambda t: None)
check("no mapping -> defect (never silently downgrade what we cannot check)",
      len(defects3) == 1 and not downgraded3, f"defects={defects3}")

os.unlink(SRC)
print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print(f"  FAILED: {f}")
sys.exit(1 if FAIL else 0)
