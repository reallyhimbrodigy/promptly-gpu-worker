"""Floor telemetry (directive #7 Part 3) — degradation markers in result jsonb.

Drives the real marker helpers, the real generate (forced safe edit), the
real render ladder (stripped rung), and the real handler failed path with a
stub supabase recorder — proving the terminal writes carry the markers.
"""
import contextlib
import copy
import io
import os
import sys

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

print("=== F1: _floor_markers shapes ===")
clean = H._floor_markers({"floor": None, "floor_reason": None, "enhancements_dropped": []})
check("clean run -> floor null, empty drops",
      clean == {"floor": None, "floor_reason": None, "enhancements_dropped": []}, str(clean))
m = H._floor_markers({"floor": "safe_edit", "floor_reason": "outer:UNKNOWN",
                      "enhancements_dropped": ["broll"]})
check("safe_edit markers carried",
      m["floor"] == "safe_edit" and m["floor_reason"] == "outer:UNKNOWN"
      and m["enhancements_dropped"] == ["broll"])
check("junk state never raises", H._floor_markers(None)["floor"] is None)

print("\n=== F2: _sync_floor_state precedence ===")
st = {"floor": None, "floor_reason": None, "enhancements_dropped": []}
H._sync_floor_state(st, {"_floor": {"floor": "safe_edit", "floor_reason": "r"},
                         "_floor_render": "stripped-reason"})
check("safe_edit (recipe floor) wins over render floor", st["floor"] == "safe_edit")
st2 = {"floor": None, "floor_reason": None, "enhancements_dropped": []}
H._sync_floor_state(st2, {"_floor_render": "two render crashes — decorations stripped"})
check("render floor recorded when no recipe floor",
      st2["floor"] == "render_stripped" and "stripped" in st2["floor_reason"])
H._sync_floor_state(st2, {})  # second sync with clean plan must not erase
check("sync never erases a recorded floor", st2["floor"] == "render_stripped")
H._sync_floor_state(None, None)
check("junk args never raise", True)

print("\n=== F3: forced safe-edit run marks the plan ===")
WORDS = [{"word": f"w{i}", "punctuated_word": f"w{i}", "start": round(i * 0.4, 2),
          "end": round(i * 0.4 + 0.35, 2), "confidence": 0.99, "speaker": 0}
         for i in range(20)]
H.compute_mechanical_cuts = lambda w, source_path=None: {
    "remove_words": [{"word_index": 5}], "notes": "stub", "pacing": "fast"}
H._call_gemini_post_cuts = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no Gemini"))
H._get_genai_client = lambda: None
with contextlib.redirect_stdout(io.StringIO()):
    plan = H.generate_edit_gemini(video_path="/x.mp4", vibe="t", duration=8.0,
                                  deepgram_words=copy.deepcopy(WORDS),
                                  inline_video_bytes=b"x",
                                  force_safe_reason="outer:UNKNOWN")
check("plan carries _floor safe_edit", (plan.get("_floor") or {}).get("floor") == "safe_edit"
      and (plan.get("_floor") or {}).get("floor_reason") == "outer:UNKNOWN", str(plan.get("_floor")))
SAFE = H.build_safe_recipe(WORDS)
H._call_gemini_post_cuts = lambda *a, **k: copy.deepcopy(SAFE)
with contextlib.redirect_stdout(io.StringIO()):
    plan2 = H.generate_edit_gemini(video_path="/x.mp4", vibe="t", duration=8.0,
                                   deepgram_words=copy.deepcopy(WORDS),
                                   inline_video_bytes=b"x")
check("clean run has NO _floor key", "_floor" not in plan2)

print("\n=== F4: ladder strip marks the plan ===")
def ladder_run(fail_times):
    ep = {"cuts": [{"source_start": 0.0, "source_end": 2.0, "speed": 1.0}],
          "motion_graphics": [], "text_overlays": [], "transitions": [],
          "tight_cut_overlays": [], "_resolved_tight_cut_overlays": [],
          "broll_clips": [], "generated_scenes": [], "_emphasis_moments": []}
    calls = []
    def render_once(cuts, bc):
        calls.append(1)
        if len(calls) <= fail_times:
            raise RuntimeError("boom")
    with contextlib.redirect_stdout(io.StringIO()):
        H._render_degrade_ladder(render_once, ep, [], "/tmp/x.mp4")
    return ep
check("stripped rung records the render floor",
      ladder_run(2).get("_floor_render") == "two render crashes — decorations stripped")
check("clean render leaves no marker", "_floor_render" not in ladder_run(0))

print("\n=== F5: guard sink appends; sink-less call stays back-compatible ===")
sink = []
with contextlib.redirect_stdout(io.StringIO()):
    H._enhancement_guard("broll", RuntimeError("x"), sink)
    H._enhancement_guard("cover_frame", RuntimeError("x"))  # no sink — P1b-era call
check("sink collected the drop", sink == ["broll"])

print("\n=== F6: terminal writes carry the markers (wire pins) ===")
src = open("handler.py").read()
_complete = src.find('status="complete", phase="Done"')
check("complete write spreads markers",
      "**_floor_markers(_floor_state)" in src[_complete:_complete + 400])
_failed = src.find('status="failed", phase="Something went wrong"', src.find("classified = classify_error(e)"))
check("failed write spreads markers",
      "**_floor_markers(_floor_state)" in src[_failed:_failed + 400])
check("sync at recipe collect AND post-ladder",
      src.count("_sync_floor_state(_floor_state, edit_plan)") == 2)
check("all 7 guard sites thread the sink",
      src.count("_floor_state['enhancements_dropped'])") == 7)

print("\n=== F7: failed-path write carries floor keys end to end (stub supabase) ===")
class StubSupabase:
    def __init__(self): self.patches = []
    def table(self, name):
        outer = self
        class _T:
            def update(self, patch):
                class _U:
                    def eq(self, col, jid):
                        class _E:
                            def execute(_s): outer.patches.append((patch, jid))
                        return _E()
                return _U()
        return _T()
saved_sb, saved_ft = H.supabase, H.fetch_user_tier
saved_env = os.environ.pop("JOB_STATUS_WRITES_ENABLED", None)
stub = StubSupabase()
H.supabase = stub
os.environ["JOB_STATUS_WRITES_ENABLED"] = "1"
H.fetch_user_tier = lambda uid: (_ for _ in ()).throw(RuntimeError("boom before pipeline"))
try:
    with contextlib.redirect_stdout(io.StringIO()):
        out = H.handler({"input": {"job_id": "j-floor", "video_url": "u", "vibe": "v",
                                   "user_id": "u1", "upload_url": "up"}})
finally:
    H.supabase, H.fetch_user_tier = saved_sb, saved_ft
    os.environ.pop("JOB_STATUS_WRITES_ENABLED", None)
    if saved_env is not None:
        os.environ["JOB_STATUS_WRITES_ENABLED"] = saved_env
fails = [p for (p, j) in stub.patches if p.get("status") == "failed" and j == "j-floor"]
check("failed write present", len(fails) == 1, str(stub.patches))
res = (fails[0].get("result") or {}) if fails else {}
check("write carries floor null + empty drops",
      "floor" in res and res["floor"] is None and res.get("enhancements_dropped") == [],
      str(res))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL FLOOR-TELEMETRY CASES PASS")
