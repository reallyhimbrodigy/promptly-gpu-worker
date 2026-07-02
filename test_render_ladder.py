"""Render degrade ladder — behavioral tests against the real helper."""
import contextlib
import io
import sys

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

def plan():
    return {"cuts": [{"source_start": 0.0, "source_end": 2.0, "speed": 1.0}],
            "motion_graphics": [{"type": "StatCard"}], "text_overlays": [{"variant": "sticky_note"}],
            "transitions": [{"type": "ZoomThrough"}], "tight_cut_overlays": [],
            "_resolved_tight_cut_overlays": [{"after_word_index": 3, "type": "ShutterFlash"}],
            "broll_clips": [{"keyword": "x"}], "generated_scenes": [{"x": 1}],
            "_generated_subjects": {"0": "/tmp/x.png"},
            "_emphasis_moments": [{"zoom_effect": {"type": "SnapReframe"}, "motion_graphic": {"type": "IconLabel"}}],
            "_render_cuts": ["stale"], "_render_fps": 60}

def run(fail_times):
    calls = []
    ep = plan()
    def render_once(cuts, bc):
        calls.append({"n": len(calls), "mgs": len(ep["motion_graphics"]),
                      "broll": len(bc), "zoom": bool(ep["_emphasis_moments"][0].get("zoom_effect"))})
        if len(calls) <= fail_times:
            raise RuntimeError(f"[composite] ffmpeg failed (injected #{len(calls)})")
    buf, err = io.StringIO(), None
    try:
        with contextlib.redirect_stdout(buf):
            H._render_degrade_ladder(render_once, ep, ep["broll_clips"], "/tmp/nonexistent_out.mp4")
    except Exception as e:
        err = e
    return calls, ep, err, buf.getvalue()

print("=== R0: success on rung 0 -> zero ladder lines (inertness) ===")
calls, ep, err, o = run(0)
check("one call, no error", err is None and len(calls) == 1, repr(err))
check("zero [render-degrade] lines", "[render-degrade]" not in o)
check("plan untouched", len(ep["motion_graphics"]) == 1 and ep["_render_cuts"] == ["stale"])

print("\n=== R1: one crash -> identical retry succeeds ===")
calls, ep, err, o = run(1)
check("two calls, success", err is None and len(calls) == 2, repr(err))
check("rung=1 logged", "[render-degrade] rung=1 (identical retry)" in o)
check("retry was IDENTICAL (decorations intact)", calls[1]["mgs"] == 1 and calls[1]["broll"] == 1)
check("stale staging keys dropped on re-entry", "_render_cuts" not in ep)

print("\n=== R2: two crashes -> stripped re-render succeeds ===")
calls, ep, err, o = run(2)
check("three calls, success", err is None and len(calls) == 3, repr(err))
check("stripped log + divergence", "[render-degrade] stripped=" in o and "action=render_stripped" in o)
check("third call ran STRIPPED (no MGs, no broll)", calls[2]["mgs"] == 0 and calls[2]["broll"] == 0)
check("zooms KEPT in stripped render", calls[2]["zoom"] is True)
check("emphasis MGs nulled", ep["_emphasis_moments"][0]["motion_graphic"] is None)

print("\n=== R3: three crashes -> RENDER_FATAL, correctly classified ===")
calls, ep, err, o = run(3)
check("raises after 3 attempts", err is not None and len(calls) == 3, repr(err))
check("RENDER_FATAL message", "RENDER_FATAL" in str(err))
check("classified RENDER_FATAL (beats greedy ffmpeg match)",
      H.classify_error(err)["error_code"] == "RENDER_FATAL")
check("cause chained", isinstance(getattr(err, "__cause__", None), RuntimeError))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL RENDER-LADDER CASES PASS")
