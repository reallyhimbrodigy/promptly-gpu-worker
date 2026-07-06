"""RenderTimeline Slice-1 battery — the one truth + shadow divergence classes.

Drives the REAL render_timeline module. Proves: frames-first construction,
the ONE floor rule (#D3 sub-frame slot exists nowhere), body identity,
integrity vs rounding divergence classification, and the #D3 phantom-frame
detection that the shadow must surface for the census.
"""
import sys

import render_timeline as RT

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


def cut(ss, se, speed=1.0):
    return {"source_start": ss, "source_end": se, "speed": speed}


FPS = 60.0

print("=== T1: construction — frames-first, cumulative, one quantization ===")
# 3 cuts, bodies 1.0/2.0/1.5s, one 0.5s slot after cut 0
cuts = [cut(0, 1.0), cut(2, 4.0), cut(5, 6.5)]
eff = [1.0, 2.0, 1.5]
th = [0.0, 0.0, 0.0]
tt = [0.0, 0.0, 0.0]
tda = [0.5, 0.0, 0.0]
tmaps = [{"avg_speed": 1.0}] * 3
tl = RT.build_render_timeline(cuts, eff, th, tt, tda, tmaps, FPS)
check("body frames = round(body_s*fps)", RT.body_frames_list(tl) == [60, 120, 90],
      str(RT.body_frames_list(tl)))
check("slot after cut 0 = 30f", tl["entries"][0]["slot_frames_after"] == 30)
check("cumulative out_start_frame", [e["out_start_frame"] for e in tl["entries"]] == [0, 90, 210],
      str([e["out_start_frame"] for e in tl["entries"]]))
check("total = sum body + sum slot", tl["total_frames"] == 300, str(tl["total_frames"]))
check("seconds view derived from frames", abs(RT.total_seconds(tl) - 5.0) < 1e-9)

print("\n=== T2: THE ONE FLOOR RULE — sub-frame slot exists NOWHERE (#D3) ===")
# slot 0.005s at 60fps = 0.3 frames → rounds to 0 → must not exist
cuts2 = [cut(0, 1.0), cut(2, 3.0)]
tl2 = RT.build_render_timeline(cuts2, [1.0, 1.0], [0, 0], [0, 0], [0.005, 0.0],
                               [{"avg_speed": 1.0}] * 2, FPS)
check("sub-frame slot rounds to 0 (no phantom frame)",
      tl2["entries"][0]["slot_frames_after"] == 0)
check("total excludes the phantom", tl2["total_frames"] == 120, str(tl2["total_frames"]))

print("\n=== T3: shadow INTEGRITY class — #D3 phantom surfaced vs R1 ===")
# R1 (current) counts the 0-frame slot as max(1)=1; transitions_out omits it.
# The shadow must flag total_delta = -1 (timeline is 1 less than R1's phantom).
d = RT.shadow_check(
    tl2,
    current_total_frames=121,          # R1 with the max(1) phantom
    current_per_cut_render_frames=[60, 60],
    body_seconds=[1.0, 1.0],
    slot_seconds=[0.005, 0.0],
    transitions_out=[],                # transitions_out correctly omitted it
    clip_ranges=[{"start": 0, "end": 1.0}, {"start": 1.0, "end": 2.0}],
    source_fps=FPS)
check("integrity divergence flagged", d["integrity_divergence"], str(d))
check("total delta = -1 (the #D3 phantom)", d["total"]["delta"] == -1, str(d["total"]))
check("no slot divergence (both drop it)", d["slots"] == [], str(d["slots"]))

print("\n=== T4: shadow parity — clean render, zero divergence ===")
d2 = RT.shadow_check(
    tl,
    current_total_frames=300,
    current_per_cut_render_frames=[60, 120, 90],
    body_seconds=[1.0, 2.0, 1.5],
    slot_seconds=[0.5, 0.0, 0.0],
    transitions_out=[{"afterClipIndex": 0, "durationInFrames": 30}],
    clip_ranges=[{"start": 0, "end": 1.0}, {"start": 0.5, "end": 2.5},
                 {"start": 2.5, "end": 4.0}],
    source_fps=FPS)
check("clean render → no integrity divergence", not d2["integrity_divergence"], str(d2))
check("slot matches transitions_out", d2["slots"] == [], str(d2["slots"]))

print("\n=== T5: shadow BODY-identity defect surfaced ===")
d3 = RT.shadow_check(
    tl,
    current_total_frames=300,
    current_per_cut_render_frames=[60, 119, 90],   # cut 1 off by 1 → real bug
    body_seconds=[1.0, 2.0, 1.5],
    slot_seconds=[0.5, 0.0, 0.0],
    transitions_out=[{"afterClipIndex": 0, "durationInFrames": 30}],
    clip_ranges=None,
    source_fps=FPS)
check("body-frame mismatch flagged as integrity divergence",
      d3["integrity_divergence"] and d3["body"] and d3["body"][0]["cut"] == 1,
      str(d3["body"]))

print("\n=== T6: #D1 rounding class — sum-of-rounds vs round-of-sum ===")
# bodies that individually round up but whose sum rounds down (or vice versa)
cuts6 = [cut(0, 0.008), cut(1, 1.008), cut(2, 2.008)]
b = [0.008, 0.008, 0.008]  # each ×60 = 0.48 → round 0 → max(1)=1 each = 3
tl6 = RT.build_render_timeline(cuts6, b, [0, 0, 0], [0, 0, 0], [0, 0, 0],
                               [{"avg_speed": 1.0}] * 3, FPS)
d6 = RT.shadow_check(
    tl6, current_total_frames=tl6["total_frames"],
    current_per_cut_render_frames=RT.body_frames_list(tl6),
    body_seconds=b, slot_seconds=[0, 0, 0],
    transitions_out=[], clip_ranges=None, source_fps=FPS)
# sum-of-rounds = 3 (max(1) each); round-of-sum = round(0.024*60)=round(1.44)=1
check("#D1 delta recorded (rounding class, not integrity)",
      d6["rounding_divergence"] and not d6["integrity_divergence"],
      str(d6["d1"]))
check("#D1 sum-of-rounds > round-of-sum here", d6["d1"]["delta"] == 2, str(d6["d1"]))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
print("ALL RENDER-TIMELINE SLICE-1 CASES PASS")
