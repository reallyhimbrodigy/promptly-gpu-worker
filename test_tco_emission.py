"""R2 (directive #7): tight_cut_overlays is EMITTABLE — schema + span tests.

3-stub harness through the REAL generate_edit_gemini. Fixture geometry per
test_recipe_repair: 12 words at 0.4s pitch; removing src word N leaves a
0.45s gap (< 0.70s handle floor) → a TIGHT boundary at the preceding kept
word. Anchors are emitted in KEPT space and translated to src by the span.
"""
import contextlib
import copy
import io
import json
import sys

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

WORDS = [{"word": f"w{i}", "punctuated_word": f"w{i}", "start": round(i * 0.4, 2),
          "end": round(i * 0.4 + 0.35, 2), "confidence": 0.99, "speaker": 0}
         for i in range(12)]

def plan(tcos=None, vision="v", **over):
    p = {"video_identity": "x" * 40,
         "video_plan": {"what_happens": "a", "key_moments": [],
                        "arc_segments": [{"start_word_index": 0, "end_word_index": 10,
                                           "position": "hook", "intensity": 0.5}],
                        "story_shape": "s",
                        "movements": [{"start_word_index": 0, "end_word_index": 10,
                                        "job": "j", "energy": "hot",
                                        "lead_instrument": "clean_frame",
                                        "captions": "run", "what_happens": "w"}],
                        "editorial_vision": vision, "hook_word_index": 0,
                        "payoff_word_index": 8, "close_word_index": 10},
         "caption_style": "Prime", "caption_keywords": [],
         "transitions": [], "motion_graphics": [], "emphasis_moments": [],
         "text_overlays": [], "broll_clips": [], "sound_effects": [],
         "caption_position_changes": [], "thumbnail_word_index": 1,
         "audio_denoise": False, "outro": "none", "aspect_ratio": "9:16"}
    if tcos is not None:
        p["tight_cut_overlays"] = tcos
    p.update(over)
    return p

def run(pl, removes=(5,)):
    H.compute_mechanical_cuts = lambda w, source_path=None: {
        "remove_words": [{"word_index": i} for i in removes],
        "notes": "stub", "pacing": "fast"}
    H._call_gemini_post_cuts = lambda *a, **k: copy.deepcopy(pl)
    H._get_genai_client = lambda: None
    buf, err, out = io.StringIO(), None, None
    try:
        with contextlib.redirect_stdout(buf):
            out = H.generate_edit_gemini(
                video_path="/x.mp4", vibe="t", duration=4.8,
                deepgram_words=copy.deepcopy(WORDS), inline_video_bytes=b"x")
    except Exception as e:
        err = e
    return out, err, buf.getvalue()

print("=== T0: the schema finally tells the truth (Gemini CAN emit) ===")
schema = H.PostCutPlan.model_json_schema()
check("tight_cut_overlays in response schema", "tight_cut_overlays" in schema.get("properties", {}))
check("NOT required (omission-tolerant)", "tight_cut_overlays" not in set(schema.get("required", [])))
tco_def = schema.get("$defs", {}).get("_TightCutOverlay", {})
check("entry: type enum == registry",
      set(tco_def.get("properties", {}).get("type", {}).get("enum", []))
      == set(H.VALID_TIGHT_CUT_OVERLAYS), str(tco_def)[:200])
check("entry: after_word_index required, why optional",
      set(tco_def.get("required", [])) == {"after_word_index", "type"})
H.PostCutPlan.model_validate(plan(tcos=[{"after_word_index": 4, "type": "ShutterFlash",
                                         "why": "the reveal lands here"}]))
check("model_validate accepts a populated array", True)
H.PostCutPlan.model_validate(H.build_safe_recipe(WORDS))
check("safe recipe still round-trips", True)

print("\n=== T1: emission round-trips the REAL span to a resolved overlay ===")
out, err, o = run(plan(tcos=[{"after_word_index": 4, "type": "ShutterFlash",
                              "why": "cut punctuation on the turn"}]))
check("no raise", err is None, repr(err))
_res = (out or {}).get("_resolved_tight_cut_overlays") or []
check("resolved at src awi 4", any(r.get("after_word_index") == 4
      and r.get("type") == "ShutterFlash" for r in _res), str(_res))
check("resolved spec carries NO why (stripped for render)",
      all("why" not in r for r in _res))
check("recipe entry keeps normalized why",
      any(e.get("why") == "cut punctuation on the turn"
          for e in out.get("tight_cut_overlays") or []))
check("resolved log line", "tight_cut_overlay 'ShutterFlash' resolved at after_word_index=4" in o)
check("no repair, no reconcile needed",
      "[recipe-repair]" not in o and "[reconcile-overlays]" not in o)

print("\n=== T2: kill test — absent field == empty field byte-identical ===")
p_absent = plan(); p_absent.pop("tight_cut_overlays", None)
out_a, _, _ = run(p_absent)
out_b, _, _ = run(plan(tcos=[]))
check("absent == []", json.dumps(out_a, sort_keys=True, default=str)
      == json.dumps(out_b, sort_keys=True, default=str))

print("\n=== T3: discretionary cap (2) unchanged — third drops with divergence log ===")
out, err, o = run(plan(tcos=[
    {"after_word_index": 2, "type": "ShutterFlash", "why": None},
    {"after_word_index": 4, "type": "NewspaperWipe", "why": None},
    {"after_word_index": 6, "type": "LightLeak", "why": None},
]), removes=(3, 6, 9))
check("no raise", err is None, repr(err))
_res = (out or {}).get("_resolved_tight_cut_overlays") or []
check("exactly 2 resolved", len(_res) == 2, str(_res))
check("cap drop logged", "per-video cap of 2 already reached" in o)

print("\n=== T4: collision — a transition on the boundary wins, TCO dropped ===")
out, err, o = run(plan(
    tcos=[{"after_word_index": 4, "type": "LightLeak", "why": None}],
    transitions=[{"after_word_index": 4, "type": "ShutterFlash"}]))
check("no raise", err is None, repr(err))
check("TCO dropped for the transition", "already has transition" in o, o[-400:])
_res = (out or {}).get("_resolved_tight_cut_overlays") or []
check("boundary carries ONE decoration",
      len([r for r in _res if r.get("after_word_index") == 4]) <= 1)

print("\n=== T5: vision-consistency rule is now FOLLOWABLE — reconcile goes quiet ===")
out, err, o = run(plan(vision="Tight ShutterFlash cuts drive the pace",
                       tcos=[{"after_word_index": 4, "type": "ShutterFlash", "why": None}]))
check("populated array + claiming vision -> NO reconcile",
      err is None and "[reconcile-overlays]" not in o, o[-300:])
out, err, o = run(plan(vision="Tight ShutterFlash cuts drive the pace", tcos=[]))
check("empty array + claiming vision -> detector still fires",
      "[reconcile-overlays] DETECTED vision-claims-empty" in o)

print("\n=== T6: why wire — >12 words truncates, junk coerces to None ===")
out, err, o = run(plan(tcos=[{"after_word_index": 4, "type": "ShutterFlash",
                              "why": "one two three four five six seven eight nine ten eleven twelve thirteen"}]))
_e = (out or {}).get("tight_cut_overlays") or []
check("truncated to 12 words", _e and len((_e[0].get("why") or "").split()) == 12, str(_e))
out, err, o = run(plan(tcos=[{"after_word_index": 4, "type": "ShutterFlash", "why": "   "}]))
_e = (out or {}).get("tight_cut_overlays") or []
check("blank why -> None", _e and _e[0].get("why") is None, str(_e))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL TCO-EMISSION CASES PASS")
