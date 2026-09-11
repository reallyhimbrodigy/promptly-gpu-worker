#!/usr/bin/env python3
"""RED PROOF: the frame labelled "beat k" must be beat k's frame.

FOUND BY WATCHING, round 54 motion. extract_beat_frames selects
between(t, T-0.03, T+0.03) for every beat midpoint in ONE decode pass. At
35.905 fps a 60ms window holds 2-3 frames, so 9 timestamps wrote 19 files and
the function kept the FIRST NINE — positionally. The model was shown beats
0,0,0,1,1,2,2,3,3 labelled "Frame 1..9" and described the first 11.5s of a
28s clip as all nine beats. "Extreme close-up blur" on beats 7-8 was the whip
pan at 11.5s. Every visual-route ruling on that fixture, rounds 51-54, reasoned
from the wrong beat's frame — and the whys agreed with SEEN perfectly, because
SEEN was a faithful description of the wrong picture.

The guard checked `len(got) < len(times)` and truncated `got[:len(times)]`:
too few was FAILED, too many was silently made to fit. A guard that only
checks one direction lets the other through.

This builds a clip where every frame IS its own timestamp (burned-in frame
number, known fps), asks for beat midpoints, and checks that each returned
frame decodes to within one frame of the time it was requested for. At 35.905
fps, on the code that shipped, it fails. It also runs at 30 fps, where the
window happens to land 1-2 frames and the bug is intermittent — a check that
only ran at the lucky rate would have stayed green.
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402

fail = 0
for fps in (35.905, 30.0):
    d = tempfile.mkdtemp(prefix=f"vf{int(fps)}_")
    clip = os.path.join(d, "clip.mp4")
    # 30s clip at an exact, known fps. Content is irrelevant: the check reads
    # the capture time the function now reports per frame, not the picture.
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"testsrc=s=320x180:r={fps}:d=30",
                    "-pix_fmt", "yuv420p", clip], check=True)
    times = [0.75, 3.0, 7.5, 11.5, 14.0, 17.5, 20.12, 22.55, 26.13]
    state, paths, detail = A.extract_beat_frames(clip, times, os.path.join(d, "bf"))
    if state != "MEASURED":
        print(f"  *** {fps}fps: {state} — {detail}")
        fail += 1
        continue
    if len(paths) != len(times):
        print(f"  *** {fps}fps: asked {len(times)} got {len(paths)}")
        fail += 1
        continue
    # The function records, per returned path, the pts_time it actually
    # captured (parsed from showinfo, exact regardless of fps). Compare THAT.
    got_t = getattr(A, "_last_beat_frame_times", None)
    if not got_t:
        print(f"  *** {fps}fps: the function does not report which time each "
              f"frame came from — positional mapping cannot be verified")
        fail += 1
        continue
    bad = [(k, want, got) for k, (want, got) in enumerate(zip(times, got_t))
           if abs(want - got) > (1.0 / fps) + 1e-6]
    for k, want, got in bad:
        print(f"  *** {fps}fps: slot {k} asked {want:.3f}s, frame is from "
              f"{got:.3f}s ({got - want:+.2f}s) — this is a different beat")
    fail += len(bad)
    print(f"  {fps}fps: {len(paths)} frames, {len(bad)} in the wrong beat")

print(f"smoke_vision_frames_are_the_beats: {fail} wrong")
sys.exit(1 if fail else 0)
