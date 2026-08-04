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
            "_emphasis_moments": [{"zoom_effect": {"type": "SnapReframe"}, "motion_graphic": {"type": "Stamp"}}],
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

print("\n=== R1: one crash -> rung 1 SKIPPED (Lever 4), stripped rung succeeds ===")
# LEVER 4 (2026-07): rung 1 restores the EXACT rung-0 spec, so its inputs are
# byte-identical by construction and re-rendering them cannot produce a
# different result — it only burns the seconds. The ladder skips it and
# advances to the next INPUT-DIFFERING rung. This encodes the standing law
# "never retry as an answer to failure": the ONLY re-render the ladder ever
# performs is one whose inputs actually changed.
# (This file asserted the pre-Lever-4 three-rung shape and was permanently RED
#  while no runner invoked it — fixed 2026-08-02 and wired into validate_deploy.)
calls, ep, err, o = run(1)
check("two render calls, success (rung 0 + stripped rung; rung 1 never rendered)",
      err is None and len(calls) == 2, f"{err!r} calls={len(calls)}")
check("rung=1 logged as SKIPPED by Lever 4",
      "rung=1 SKIPPED" in o and "identical" in o)
check("the identical-input skip is ledgered",
      "action=ladder_identical_input_skip" in o)
check("NO byte-identical re-render ever happened (decorations differ on call 2)",
      calls[1]["mgs"] == 0 and calls[1]["broll"] == 0,
      f"call1={calls[1]}")
check("stale staging keys dropped on re-entry", "_render_cuts" not in ep)

print("\n=== R2: the second render is the STRIPPED one (cuts+captions+zooms kept) ===")
calls, ep, err, o = run(1)
check("stripped log + divergence",
      "[render-degrade] stripped=" in o and "action=render_stripped" in o)
check("second call ran STRIPPED (no MGs, no broll)",
      calls[1]["mgs"] == 0 and calls[1]["broll"] == 0)
check("zooms KEPT in stripped render", calls[1]["zoom"] is True)
check("emphasis MGs nulled", ep["_emphasis_moments"][0]["motion_graphic"] is None)

print("\n=== R3: stripped rung also fails -> RENDER_FATAL, correctly classified ===")
calls, ep, err, o = run(2)
check("raises after exactly 2 renders (never 3 — Lever 4 skipped the identical rung)",
      err is not None and len(calls) == 2, f"{err!r} calls={len(calls)}")
check("RENDER_FATAL message", "RENDER_FATAL" in str(err))
check("classified RENDER_FATAL (beats greedy ffmpeg match)",
      H.classify_error(err)["error_code"] == "RENDER_FATAL")
check("cause chained", isinstance(getattr(err, "__cause__", None), RuntimeError))

print("\n=== R4: the ladder NEVER renders more than twice, however many crash ===")
for _ft in (2, 3, 5, 99):
    _c, _e, _err, _o = run(_ft)
    check(f"fail_times={_ft}: exactly 2 render attempts (no retry storm)",
          len(_c) == 2, f"calls={len(_c)}")

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL RENDER-LADDER CASES PASS")
