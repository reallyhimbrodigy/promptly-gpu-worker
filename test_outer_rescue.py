"""Outermost rung (P1a) — behavioral tests for _outer_safe_rescue + force_safe.

Decision-table tests drive the REAL rescue helper with injected run_fn stubs;
the force_safe test drives the REAL generate_edit_gemini through the 3-stub
harness with a Gemini stub that raises if touched (proves the rescue path is
Gemini-free).
"""
import contextlib
import copy
import io
import os
import sys
import time

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

def fresh(mode="full", ready=True, t0=None, dur=30.0, marker=None):
    inp = {"job_id": "j1", "video_url": "u", "vibe": "v", "user_id": "u1"}
    if marker:
        inp["_safe_edit_rescue"] = marker
    job = {"input": inp}
    state = {"ready": ready, "mode": mode, "dur": dur,
             "t0": t0 if t0 is not None else time.time()}
    return job, inp, state

CLASSIFIED = {"error_code": "UNKNOWN", "user_message": "x", "retryable": True,
              "requires_new_video": False, "requires_vibe_change": False}

def run_rescue(job, inp, state, classified=None, run_fn=None, env=None):
    saved = {}
    for k, v in (env or {}).items():
        saved[k] = os.environ.pop(k, None)
        os.environ[k] = v
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            out = H._outer_safe_rescue(job, inp, classified or dict(CLASSIFIED),
                                       state, run_fn=run_fn)
    finally:
        for k, old in saved.items():
            os.environ.pop(k, None)
            if old is not None:
                os.environ[k] = old
    return out, buf.getvalue()

print("=== O1: eligible failure -> ONE marked re-run -> success payload returned ===")
calls = []
def ok_run(job):
    calls.append(dict(job["input"]))
    return {"status": "success", "job_id": "j1", "video_url": "https://cdn/x.mp4"}
job, inp, state = fresh()
out, o = run_rescue(job, inp, state, run_fn=ok_run)
check("payload returned", isinstance(out, dict) and out.get("video_url") == "https://cdn/x.mp4", repr(out))
check("exactly one re-run", len(calls) == 1)
check("marker set on the re-run input", calls and calls[0].get("_safe_edit_rescue") == "outer:UNKNOWN")
check("engaged log line", "[safe-edit] engaged reason=outer:UNKNOWN" in o)
check("divergence recorded", "safe_edit_rescue" in o)

print("\n=== O2: re-entry guard — marker present -> NO second rescue ===")
calls = []
job, inp, state = fresh(marker="outer:UNKNOWN")
out, o = run_rescue(job, inp, state, run_fn=ok_run)
check("returns None", out is None, repr(out))
check("run_fn never called", len(calls) == 0)
check("no engaged line", "engaged reason=outer" not in o)

print("\n=== O3: every deny-listed class refuses the rescue ===")
denied_ok = True
for code in sorted(H._OUTER_RESCUE_DENY):
    calls = []
    job, inp, state = fresh()
    out, o = run_rescue(job, inp, state,
                        classified={**CLASSIFIED, "error_code": code}, run_fn=ok_run)
    if out is not None or calls:
        denied_ok = False
        check(f"deny {code}", False, repr(out))
check("all deny classes -> None, zero re-runs", denied_ok)
check("directive's input-reject classes are all denied",
      {"NO_SPEECH", "NOT_TALKING_HEAD", "INVALID_SOURCE_URL",
       "INVALID_FORMAT"} <= set(H._OUTER_RESCUE_DENY))
check("irreducible inner-net classes are denied",
      {"RENDER_FATAL", "RECIPE_INVALID", "TRANSCRIPTION"} <= set(H._OUTER_RESCUE_DENY))

print("\n=== O4: a FUTURE unknown class IS eligible (the 1a72b344 property) ===")
calls = []
job, inp, state = fresh()
out, o = run_rescue(job, inp, state,
                    classified={**CLASSIFIED, "error_code": "SOME_BUG_FROM_2027"},
                    run_fn=ok_run)
check("unknown class rescued", out is not None and len(calls) == 1, repr(out))
check("reason carries the class", "reason=outer:SOME_BUG_FROM_2027" in o)

print("\n=== O5: readiness / mode / budget gates ===")
job, inp, state = fresh(ready=False)
out, _ = run_rescue(job, inp, state, run_fn=ok_run)
check("not ready -> None", out is None)
job, inp, state = fresh(mode="render_only")
out, _ = run_rescue(job, inp, state, run_fn=ok_run)
check("re-edit mode -> None (existing video stands)", out is None)
job, inp, state = fresh(t0=time.time() - 800.0)
out, o = run_rescue(job, inp, state, run_fn=ok_run)
check("budget exhausted -> None with skip log", out is None and "rescue skipped — budget" in o)

print("\n=== O6: failure INSIDE the rescue exits through the ORIGINAL path ===")
def boom_run(job):
    raise RuntimeError("rescue run died")
job, inp, state = fresh()
out, o = run_rescue(job, inp, state, run_fn=boom_run)
check("raise inside rescue -> None (never raises)", out is None)
check("failure logged, original stands", "original error stands" in o)
def err_run(job):
    return {"error": "x", "error_code": "RENDER_FATAL", "user_message": "x"}
job, inp, state = fresh()
out, o = run_rescue(job, inp, state, run_fn=err_run)
check("inner error envelope -> None", out is None)
check("did-not-produce log", "did not produce a video" in o)

print("\n=== O7: kill switch disables the rung ===")
calls = []
job, inp, state = fresh()
out, o = run_rescue(job, inp, state, run_fn=ok_run,
                    env={"SAFE_EDIT_FALLBACK_ENABLED": "0"})
check("switch off -> None, zero lines", out is None and "[safe-edit]" not in o and not calls)

print("\n=== O8: force_safe — the rescue recipe path is deterministic + Gemini-free ===")
WORDS = [{"word": f"w{i}", "punctuated_word": f"w{i}", "start": round(i * 0.4, 2),
          "end": round(i * 0.4 + 0.35, 2), "confidence": 0.99, "speaker": 0}
         for i in range(20)]
def _never(*a, **k):
    raise AssertionError("Gemini was called on the forced-safe path")
H.compute_mechanical_cuts = lambda w, source_path=None: {
    "remove_words": [{"word_index": 5}], "notes": "stub", "pacing": "fast"}
H._call_gemini_post_cuts = _never
H._get_genai_client = lambda: None
buf = io.StringIO()
err = None
try:
    with contextlib.redirect_stdout(buf):
        plan = H.generate_edit_gemini(
            video_path="/x.mp4", vibe="t", duration=8.0,
            deepgram_words=copy.deepcopy(WORDS), inline_video_bytes=b"x",
            force_safe_reason="outer:UNKNOWN")
except Exception as e:
    err = e
o = buf.getvalue()
check("no raise, plan returned", err is None and isinstance(plan, dict), repr(err))
check("engaged with the OUTER reason", "[safe-edit] engaged reason=outer:UNKNOWN" in o)
check("safe recipe flowed through the span",
      err is None and plan.get("notes") == "safe-edit fallback"
      and plan.get("caption_style") == "CleanCut" and plan.get("cuts"))

print("\n=== O9: no force_safe -> byte-identical normal path (marker inert) ===")
SAFE = H.build_safe_recipe(WORDS)
H._call_gemini_post_cuts = lambda *a, **k: copy.deepcopy(SAFE)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    plan_a = H.generate_edit_gemini(
        video_path="/x.mp4", vibe="t", duration=8.0,
        deepgram_words=copy.deepcopy(WORDS), inline_video_bytes=b"x")
    plan_b = H.generate_edit_gemini(
        video_path="/x.mp4", vibe="t", duration=8.0,
        deepgram_words=copy.deepcopy(WORDS), inline_video_bytes=b"x",
        force_safe_reason=None)
import json
check("force_safe_reason=None == absent",
      json.dumps(plan_a, sort_keys=True, default=str)
      == json.dumps(plan_b, sort_keys=True, default=str))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL OUTER-RESCUE CASES PASS")
