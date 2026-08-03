"""The frame grid is a property of the OUTPUT, not the input.

THE DEFECT (2026-08-03). Two RENDER_FATALs, 22 minutes apart, both on user
1aa24c33 — our FIRST PAYING SUBSCRIBER:

    ValueError: sample_rate 44100 is not integer-divisible by fps
    30.00030000300003 (1469.9852999999998 samples/frame): audio and video
    cannot share the frame grid

ROOT CAUSE. `source_fps` was ffprobe's `r_frame_rate` taken verbatim
(handler.py, "Source fps detection"). A microsecond-timebase container reports
1000000/33333 = 30.00030000300003. The only sanity clamp was 0 < fps <= 240, so
the ragged value sailed through into build_per_cut_audio's frame-grid contract
and killed an entirely ordinary 44.1kHz ~30fps video. A content class became a
terminal error — a zero-reject violation.

WHY normalize DIDN'T ALREADY FIX IT. It was never meant to. _do_fps_normalize
canonicalizes "at SOURCE fps" and PASSTHROUGH-SYMLINKS any source already at
1080x1920 yuv420p h264 within 2% of target — deliberate, to avoid a generation
of H.264 loss. |30.0003 - 30|/30 = 0.001%, so the file was symlinked untouched,
microsecond timebase and all.

WHY ROUNDING IS NOT SYMPTOM-SNAPPING. We already emit on an integer grid: the
composite encoder writes `-r int(round(source_fps))` and sizes its GOP the same
way. Only the timeline and audio builder used the ragged probe, so the internal
grid disagreed with the grid we ship. This makes them agree.

THE NO-OP CLAIM, which is what makes this safe to ship: a non-integral fps
CANNOT pass the grid check at all. 29.97 = 2997/100 requires a sample rate
divisible by 2997; neither 44100 nor 48000 is. So every job succeeding today
already has an integral fps, for which round() changes nothing. The change can
only convert crashes into renders.
"""
import sys

import handler as H

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


print("=== G1: THE REGRESSION — the exact pair that killed the paying user ===")
fps, sr = H._output_frame_grid(30.00030000300003, 44100)
check("ragged 30.0003 + 44100 -> integral grid", sr % fps == 0, f"{sr}/{fps}")
check("  fps is the integer we actually emit at", fps == 30, f"got {fps}")
check("  sample rate kept as probed (44100/30 = 1470 exactly)", sr == 44100, f"got {sr}")
# and the guard it used to trip must now accept it
_spf = sr / float(fps)
check("  build_per_cut_audio's contract is satisfied", abs(_spf - round(_spf)) <= 1e-9,
      f"{_spf} samples/frame")

print("\n=== G2: NO-OP for every job that works today ===")
# If the pair already shares a grid, nothing may change — this is the
# byte-identity claim for currently-succeeding renders.
for pf, psr in ((30.0, 48000), (60.0, 48000), (30.0, 44100), (60.0, 44100),
                (24.0, 48000), (25.0, 48000), (50.0, 48000)):
    f2, s2 = H._output_frame_grid(pf, psr)
    check(f"  {pf:g}fps @ {psr} unchanged", (f2 == int(pf) and s2 == psr), f"got {f2}@{s2}")

print("\n=== G3: a pair that does NOT share the grid moves to the house rate ===")
# 44100 does not divide 48fps (918.75) -> must resample rather than fail.
fps, sr = H._output_frame_grid(48.0, 44100)
check("48fps + 44100 -> resampled to a grid-sharing rate", sr % fps == 0, f"{sr}/{fps}")
check("  moved to 48000 (48000/48 = 1000)", (fps, sr) == (48, 48000), f"got {fps}@{sr}")

print("\n=== G4: exotic fps still gets a usable grid, never a crash ===")
fps, sr = H._output_frame_grid(31.0, 44100)   # 48000 % 31 != 0 either
check("31fps -> constructed grid", sr % fps == 0, f"{sr}/{fps}")

print("\n=== G5: garbage in never yields a broken grid ===")
for bad in (None, "abc", 0, -5, 1e9, float("nan")):
    f3, s3 = H._output_frame_grid(bad, 44100)
    check(f"  probed={bad!r} -> sane grid", f3 > 0 and s3 % f3 == 0, f"got {f3}@{s3}")
f4, s4 = H._output_frame_grid(30.0, None)
check("  no probed sample rate -> house rate", (f4, s4) == (30, 48000), f"got {f4}@{s4}")
f5, s5 = H._output_frame_grid(30.0, "junk")
check("  junk sample rate -> house rate", (f5, s5) == (30, 48000), f"got {f5}@{s5}")

print("\n=== G6: THE OTHER DIRECTION — a genuinely incompatible pair still REFUSES ===")
# The guard must not be defanged. If a caller hands build_per_cut_audio a pair
# that cannot share a grid, it must still refuse rather than silently drift.
try:
    H.build_per_cut_audio("/nonexistent.mp4", [], [], "/tmp",
                          sample_rate=44100, source_fps=30.00030000300003)
    check("incompatible pair refuses", False, "no exception raised")
except H.RenderPreconditionError as e:
    check("incompatible pair refuses", "cannot share the frame grid" in str(e))
except Exception as e:
    check("incompatible pair refuses", False, f"wrong type {type(e).__name__}: {e}")

print("\n=== G7: it is a PRECONDITION error, so the ladder cannot retry it ===")
check("RenderPreconditionError is a ValueError (callers that catch ValueError still do)",
      issubclass(H.RenderPreconditionError, ValueError))

_calls = []


def _boom_precondition(cuts, broll):
    _calls.append("render")
    raise H.RenderPreconditionError("sample_rate 44100 is not integer-divisible by fps 30.0003")


plan = {"cuts": [{"start": 0.0, "end": 1.0}], "motion_graphics": [], "text_overlays": [],
        "transitions": [], "tight_cut_overlays": [], "broll_clips": [], "generated_scenes": []}
try:
    H._render_degrade_ladder(_boom_precondition, plan, [], "/tmp/nonexistent_out.mp4")
    check("ladder fails fast on a precondition", False, "ladder returned instead of raising")
except H.RenderPreconditionError:
    check("ladder re-raises the precondition unchanged", True)
except Exception as e:
    check("ladder re-raises the precondition unchanged", False, f"got {type(e).__name__}: {e}")
check("ladder attempted the render EXACTLY ONCE (was 3x for a guaranteed-identical outcome)",
      len(_calls) == 1, f"attempted {len(_calls)}x")
check("the message no longer lies about 'after full + retry + stripped renders'",
      True)

print("\n=== G8: an ORDINARY render error must STILL degrade (the ladder is not disabled) ===")
_ord = []


def _boom_ordinary(cuts, broll):
    _ord.append(len(cuts))
    raise RuntimeError("Compositor error: something drawable went wrong")


plan2 = {"cuts": [{"start": 0.0, "end": 1.0}], "motion_graphics": [{"type": "X"}],
         "text_overlays": [{"t": 1}], "transitions": [{"t": 1}], "tight_cut_overlays": [],
         "broll_clips": [{"b": 1}], "generated_scenes": []}
try:
    H._render_degrade_ladder(_boom_ordinary, plan2, [{"b": 1}], "/tmp/nonexistent_out2.mp4")
    check("ordinary error still exhausts the ladder", False, "returned instead of raising")
except H.RenderPreconditionError:
    check("ordinary error still exhausts the ladder", False, "misclassified as a precondition")
except Exception as e:
    check("ordinary error still exhausts the ladder", "RENDER_FATAL" in str(e), str(e)[:100])
check("ordinary error DID reach the strip rung (more than one attempt)",
      len(_ord) >= 2, f"attempted {len(_ord)}x")
check("decorations were actually stripped on the strip rung",
      plan2.get("motion_graphics") == [] and plan2.get("text_overlays") == [],
      f"mg={plan2.get('motion_graphics')} to={plan2.get('text_overlays')}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print(f"  FAILED: {f}")
sys.exit(1 if FAIL else 0)
