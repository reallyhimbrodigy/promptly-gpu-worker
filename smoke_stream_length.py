#!/usr/bin/env python3
"""The delivered video stream runs as long as its audio and its kept duration.

THE DEFECT, round 43. inspect() read `format.duration` and nothing else — the
CONTAINER duration, which the longest stream sets. That is the audio. So a file
whose video ended two thirds of the way through reported its full length:

    screen_recording   video 9.267s / 278 frames   audio 30.960s
                       "output: 30.96s 1080x1920 audio=True"   <- reported
                       "frames_actual=139 (ok=True)"           <- passed

THREE of five fixtures shipped truncated. The composite sizes the output to the
OVERLAY rather than the base, so the defect appears exactly when the overlay is
shorter than the video — invisible on every corpus where captions happened to
span the whole clip.

  python3 smoke_stream_length.py     exit 0 = the verdict separates them
"""
import sys
import agentic_editor_app as app

fails = []


def check(label, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        fails.append(label)


if not hasattr(app, "stream_length_verdict"):
    print("  [FAIL] stream_length_verdict does not exist")
    sys.exit(1)
v = app.stream_length_verdict

# THE REAL ROUND-43 NUMBERS, from ffprobe on the delivered files. Driven by
# measurement, not by invented cases — these are the draws that must separate.
# (video_s, audio_s, kept_s, fps, spans, want). Round 43 BROKEN and round 44
# FIXED, on the same instrument — the pair is what proves the bar separates
# rather than merely rejects.
REAL = [("r43 talking_head", 20.266667, 20.270998, 20.25, 30.0, 1, "OK"),
        ("r43 motion", 22.689333, 22.709002, 22.69, 59.94, 2, "OK"),
        ("r43 car_short", 7.033333, 10.008005, 10.0, 30.0, 1, "TRUNCATED"),
        ("r43 screen_recording", 9.266667, 30.960000, 30.96, 30.0, 3, "TRUNCATED"),
        ("r43 car_mid", 11.833333, 13.226000, 13.72, 30.0, 1, "TRUNCATED"),
        # ROUND 44, AFTER THE CURE — the same fixtures must now pass, including
        # screen_recording at +1.80 frames on a 4-span output, which a flat
        # 1.5-frame bar wrongly flagged.
        ("r44 talking_head", 20.300, 20.271, 20.250, 30.11, 1, "OK"),
        ("r44 motion", 27.961, 27.957, 27.940, 35.95, 2, "OK"),
        ("r44 car_short", 10.033, 10.008, 10.000, 30.0, 1, "OK"),
        ("r44 screen_recording", 40.900, 40.960, 40.960, 30.0, 4, "OK")]

print("both rounds on one instrument — broken must fail, fixed must pass:")
for name, vid, aud, kept, fps, spans, want in REAL:
    st, _ = v(vid, aud, kept, fps=fps, spans=spans)
    check(f"{name:22} -> {st}", st == want, f"expected {want}")

# THE SEPARATION, stated as a number rather than trusted. The bar's exact value
# is not load-bearing precisely because this gap is 40 frames wide.
_fixed = [abs(a - vd) * f for n, vd, a, k, f, sp, w in REAL if w == "OK"]
_broken = [abs(a - vd) * f for n, vd, a, k, f, sp, w in REAL if w == "TRUNCATED"]
check("worst FIXED case is far below the best BROKEN case",
      max(_fixed) * 10 < min(_broken),
      f"fixed max {max(_fixed):.2f} frames vs broken min {min(_broken):.2f} frames")

# A FLAT 1.5-FRAME BAR — the one I invented — must be shown to fail the real
# fixed case, so the reason for the change is in the check and not only in a
# commit message.
_st_flat, _ = v(40.900, 40.960, 40.960, fps=30.0, spans=None)
check("the ORIGINAL flat bar wrongly flags r44 screen_recording",
      _st_flat == "TRUNCATED",
      "this is why the bound is span-aware, not a widened constant")

# ABSENCE MUST NEVER PASS. An unreadable stream duration is the condition the
# defect lived in.
print("\nabsence fails closed:")
for label, args in (("video duration None", (None, 30.96, 30.96)),
                    ("video duration 0", (0, 30.96, 30.96)),
                    ("no audio and no kept", (9.27, None, None)),
                    ("non-numeric", ("x", "y", None))):
    st, _ = v(*args)
    check(f"{label:22} -> {st}", st == "ABSENT")

# The tolerance must sit clear of every real draw, in both directions.
print("\nthe tolerance is not near any real draw:")
st_ok, _ = v(30.0, 30.02, 30.0)
st_bad, _ = v(30.0, 30.20, 30.0)
check("a 0.020s deficit is OK (motion's real margin)", st_ok == "OK")
check("a 0.200s deficit is TRUNCATED", st_bad == "TRUNCATED")
check("the smallest real defect (1.393s) is caught",
      v(11.833333, 13.226, None)[0] == "TRUNCATED")

# The kept duration is checked independently of the audio, so a file whose
# AUDIO is also short does not excuse a short video.
st, det = v(9.267, 9.267, 30.96)
check("audio ALSO short does not excuse it — kept duration still fails",
      st == "TRUNCATED", det[:70])

# WIRING — a correct verdict nobody acts on changes nothing.
#
# M5 in the RED proof removed the fail() call and left the function perfect;
# the value legs above all still passed. "Is it computed" is not "is it
# enforced", so this reads the AST of inspect() rather than the file's text: a
# `fail("video_truncated", ...)` string can survive the change it exists to
# catch, and only the call graph shows it is reached.
import ast
import os
print("\nwiring — inspect() must compute it AND fail on it:")
tree = ast.parse(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "agentic_editor_app.py"), encoding="utf-8").read())
insp = next((n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name == "inspect"), None)
check("inspect() exists", insp is not None)
if insp is not None:
    calls = [n for n in ast.walk(insp) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "stream_length_verdict"]
    check("inspect() CALLS stream_length_verdict", len(calls) == 1, f"{len(calls)}")
    bound = [n for n in ast.walk(insp) if isinstance(n, ast.Assign)
             and any(isinstance(x, ast.Call)
                     and getattr(x.func, "id", "") == "stream_length_verdict"
                     for x in ast.walk(n))]
    check("its result is BOUND, not discarded", len(bound) == 1)
    fails_called = [n for n in ast.walk(insp) if isinstance(n, ast.Call)
                    and getattr(n.func, "id", "") == "fail"
                    and n.args and isinstance(n.args[0], ast.Constant)
                    and n.args[0].value == "video_truncated"]
    check("inspect() calls fail('video_truncated', ...)", len(fails_called) == 1,
          f"{len(fails_called)}")
check("video_truncated is a CONTRACT_FAILURES member",
      "video_truncated" in app.CONTRACT_FAILURES)

print()
if fails:
    print(f"{len(fails)} failure(s)")
    sys.exit(1)
print("the verdict separates the real truncations from the real healthy runs")
