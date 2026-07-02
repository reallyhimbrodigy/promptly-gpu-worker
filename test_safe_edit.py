"""Safe-edit fallback (zero-fatal ladder Part 2) — offline behavioral tests."""
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

WORDS = [{"word": f"w{i}", "punctuated_word": f"w{i}", "start": round(i * 0.4, 2),
          "end": round(i * 0.4 + 0.35, 2), "confidence": 0.99, "speaker": 0}
         for i in range(20)]
PEAKS = [{"t": 3.1, "score": 0.9}, {"t": 6.2, "score": 0.7}, {"t": 3.3, "score": 0.95}]

def run(gemini_fn, resolved_policy=None, env=None):
    saved_env = {}
    for k, v in (env or {}).items():
        saved_env[k] = os.environ.pop(k, None)
        os.environ[k] = v
    H.compute_mechanical_cuts = lambda w, source_path=None: {
        "remove_words": [{"word_index": 5}], "notes": "stub", "pacing": "fast"}
    H._call_gemini_post_cuts = gemini_fn
    H._get_genai_client = lambda: None
    buf, err, out = io.StringIO(), None, None
    try:
        with contextlib.redirect_stdout(buf):
            out = H.generate_edit_gemini(
                video_path="/x.mp4", vibe="t", duration=8.0,
                deepgram_words=copy.deepcopy(WORDS), vocal_emphasis=PEAKS,
                inline_video_bytes=b"x", resolved_policy=resolved_policy)
    except Exception as e:
        err = e
    finally:
        for k, old in saved_env.items():
            os.environ.pop(k, None)
            if old is not None:
                os.environ[k] = old
    return out, err, buf.getvalue()

SAFE = H.build_safe_recipe(WORDS, vocal_emphasis=PEAKS)
BAD = {**copy.deepcopy(SAFE), "caption_style": "NotAStyle"}

print("=== S1: schema-valid by construction ===")
H.PostCutPlan.model_validate(SAFE)
check("PostCutPlan.model_validate passes", True)
check("0-3 zooms on peaks (spacing-thresholded)", 1 <= len(SAFE["emphasis_moments"]) <= 3)
check("CleanCut, empty decoration arrays",
      SAFE["caption_style"] == "CleanCut" and SAFE["transitions"] == []
      and SAFE["motion_graphics"] == [] and SAFE["broll_clips"] == [])

print("\n=== S2: RECIPE_INVALID exhaustion -> safe edit renders through the normal span ===")
out, err, o = run(lambda *a, **k: copy.deepcopy(BAD))
check("no raise; plan returned", err is None and isinstance(out, dict), repr(err))
check("[safe-edit] engaged + divergence",
      "[safe-edit] engaged reason=RECIPE_INVALID" in o and "action=safe_edit_fallback" in o)
check("safe plan flowed through (notes + style)",
      out.get("notes") == "safe-edit fallback" and out.get("caption_style") == "CleanCut")

print("\n=== S3: transport exhaustion -> safe edit ===")
def _boom(*a, **k): raise RuntimeError("Gemini post-cuts-call degenerate after retry")
out, err, o = run(_boom)
check("no raise", err is None, repr(err))
check("reason=recipe_transport", "reason=recipe_transport:RuntimeError" in o)

print("\n=== S4: EditPolicy honored in safe mode ===")
class _Pol:
    mode = "deny_list"
    def off_features(self): return ["zoom", "captions"]
out, err, o = run(_boom, resolved_policy=_Pol())
check("no raise", err is None, repr(err))
check("zoom off -> no zooms", all(not e.get("zoom_effect") for e in out.get("emphasis_moments") or []))
check("captions off -> style none", out.get("caption_style") == "none")

print("\n=== S5: kill switch restores the terminal raise ===")
out, err, o = run(lambda *a, **k: copy.deepcopy(BAD), env={"SAFE_EDIT_FALLBACK_ENABLED": "0"})
check("RecipeInvalidError raised", isinstance(err, H.RecipeInvalidError), repr(err))
check("no safe-edit lines", "[safe-edit]" not in o)

print("\n=== S6: inertness — clean plan emits zero ladder lines ===")
out, err, o = run(lambda *a, **k: copy.deepcopy(SAFE))
check("no raise", err is None, repr(err))
check("zero [safe-edit]/[budget-shed]/[render-degrade] lines",
      all(t not in o for t in ("[safe-edit]", "[budget-shed]", "[render-degrade]")))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL SAFE-EDIT CASES PASS")
