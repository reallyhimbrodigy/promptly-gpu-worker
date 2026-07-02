"""Recipe repair loop + crossfade-on-tight demotion — offline behavioral tests.

Drives the REAL generate_edit_gemini with three stubs (compute_mechanical_cuts,
_call_gemini_post_cuts, _get_genai_client) so the full post-parse validation
span runs exactly as in production, no network/API needed.

Fixture geometry: 12 words, word i spans [i*0.4, i*0.4+0.35]. Mechanical cuts
remove word 5 → kept indices 0-4,6-11; the splice after kept-idx 4 has a source
gap of word6.start(2.40) - word4.end(1.95) = 0.45s < 0.70s → a TIGHT boundary
at src awi 4. ZoomThrough there exercises the demotion; an invalid
caption_style exercises the re-ask.
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


WORDS = [
    {"word": f"w{i}", "punctuated_word": f"w{i}", "start": round(i * 0.4, 2),
     "end": round(i * 0.4 + 0.35, 2), "confidence": 0.99, "speaker": 0}
    for i in range(12)
]
CUT_PLAN = {"remove_words": [{"word_index": 5}], "notes": "stub", "pacing": "fast"}

def clean_plan(**over):
    p = {
        "caption_style": "Prime", "caption_keywords": ["w1"],
        "transitions": [], "tight_cut_overlays": [],
        "motion_graphics": [], "emphasis_moments": [], "text_overlays": [],
        "broll_clips": [], "sound_effects": [],
        "audio_denoise": False, "outro": "none", "aspect_ratio": "9:16",
    }
    p.update(over)
    return p


class Stub:
    """Scripted _call_gemini_post_cuts: pops plans per call, records post_user."""
    def __init__(self, plans):
        self.plans = list(plans)
        self.post_users = []
    def __call__(self, client, post_sys, post_user, video_part, model):
        self.post_users.append(post_user)
        return copy.deepcopy(self.plans.pop(0))


def run_gen(plans, env_attempts=None):
    stub = Stub(plans)
    saved = {
        "compute_mechanical_cuts": H.compute_mechanical_cuts,
        "_call_gemini_post_cuts": H._call_gemini_post_cuts,
        "_get_genai_client": H._get_genai_client,
    }
    env_saved = os.environ.pop("RECIPE_REPAIR_MAX_ATTEMPTS", None)
    if env_attempts is not None:
        os.environ["RECIPE_REPAIR_MAX_ATTEMPTS"] = env_attempts
    H.compute_mechanical_cuts = lambda words, source_path=None: copy.deepcopy(CUT_PLAN)
    H._call_gemini_post_cuts = stub
    H._get_genai_client = lambda: None
    buf = io.StringIO()
    err = None
    plan = None
    try:
        with contextlib.redirect_stdout(buf):
            plan = H.generate_edit_gemini(
                video_path="/nonexistent.mp4", vibe="test vibe", duration=4.8,
                deepgram_words=copy.deepcopy(WORDS), shot_changes=[],
                vocal_emphasis=[], source_loudness={}, face_positions=[],
                inline_video_bytes=b"fakevideo", premium=False,
            )
    except Exception as e:
        err = e
    finally:
        for k, v in saved.items():
            setattr(H, k, v)
        if env_attempts is not None:
            os.environ.pop("RECIPE_REPAIR_MAX_ATTEMPTS", None)
        if env_saved is not None:
            os.environ["RECIPE_REPAIR_MAX_ATTEMPTS"] = env_saved
    return plan, err, buf.getvalue(), stub


print("=== T1: clean plan → repair loop INERT ===")
plan, err, out, stub = run_gen([clean_plan()])
check("clean plan returns (no raise)", err is None and isinstance(plan, dict), repr(err))
check("zero [recipe-repair] lines", "[recipe-repair]" not in out)
check("zero demote divergence lines", "action=demote" not in out)
check("exactly one Gemini call", len(stub.post_users) == 1)

print("\n=== T2: crossfade on TIGHT boundary → DEMOTED, job lives ===")
plan, err, out, stub = run_gen(
    [clean_plan(transitions=[{"type": "ZoomThrough", "after_word_index": 4}])])
check("demotion does not raise", err is None and isinstance(plan, dict), repr(err))
_ovl = (plan or {}).get("_resolved_tight_cut_overlays") or []
_demoted = [o for o in _ovl if o.get("after_word_index") == 4]
check("overlay appended at the demoted boundary", len(_demoted) == 1, str(_ovl))
check("demoted type is a light rotation type",
      _demoted and _demoted[0]["type"] in ("ShutterFlash", "LightLeak", "NewspaperWipe"),
      str(_demoted))
check("divergence action=demote logged", "action=demote" in out)
check("no transition applied at that boundary", "Transition 'ZoomThrough' applied" not in out)
check("overlay validates against render enum",
      _demoted and _demoted[0]["type"] in H.VALID_TIGHT_CUT_OVERLAYS)
check("no [recipe-repair] re-ask needed (demotion, not raise)", "[recipe-repair]" not in out)

print("\n=== T2b: demote target already decorated → plain drop, no double-decoration ===")
plan, err, out, stub = run_gen(
    [clean_plan(transitions=[{"type": "ZoomThrough", "after_word_index": 4}],
                tight_cut_overlays=[{"type": "ShutterFlash", "after_word_index": 4,
                                     "title": None, "label": None}])])
check("already-decorated does not raise", err is None, repr(err))
_ovl = (plan or {}).get("_resolved_tight_cut_overlays") or []
_at4 = [o for o in _ovl if o.get("after_word_index") == 4]
check("exactly ONE decoration at the boundary", len(_at4) == 1, str(_ovl))
check("kept decoration is Gemini's own overlay", _at4 and _at4[0]["type"] == "ShutterFlash")
check("plain drop logged, no demote divergence",
      "already carries a decoration" in out and "action=demote" not in out)

print("\n=== T3: validation raise → ONE corrective re-ask → clean second pass ===")
plan, err, out, stub = run_gen(
    [clean_plan(caption_style="NotAStyle"), clean_plan()])
check("second pass succeeds", err is None and isinstance(plan, dict), repr(err))
check("exactly two Gemini calls", len(stub.post_users) == 2, str(len(stub.post_users)))
check("[recipe-repair] attempt=1 logged", "[recipe-repair] attempt=1" in out)
check("repair block appended to the re-ask post_user",
      "Re-emit the complete recipe JSON with this corrected:" in stub.post_users[1]
      and "NotAStyle" in stub.post_users[1])
check("first post_user carried NO repair block",
      "Re-emit the complete recipe JSON" not in stub.post_users[0])

print("\n=== T4: exhaustion → RecipeInvalidError, cause chained, classified FIRST ===")
plan, err, out, stub = run_gen(
    [clean_plan(caption_style="NotAStyle"), clean_plan(caption_style="NotAStyle")])
check("exhaustion raises RecipeInvalidError", isinstance(err, H.RecipeInvalidError), repr(err))
check("message carries the sentinel + attempt count",
      err is not None and str(err).startswith("RECIPE_INVALID after 2 attempt(s):"), str(err))
check("__cause__ is the original ValueError", isinstance(getattr(err, "__cause__", None), ValueError))
_cls = H.classify_error(err) if err else {}
check("classify_error → RECIPE_INVALID", _cls.get("error_code") == "RECIPE_INVALID", str(_cls))
# ordering proof: a message that ALSO contains every greedy absorber substring
_grim = H.RecipeInvalidError(
    "RECIPE_INVALID after 1 attempt(s): Gemini broll plan removed all words")
check("RECIPE_INVALID wins over Gemini/broll/removed-all-words absorbers",
      H.classify_error(_grim).get("error_code") == "RECIPE_INVALID",
      str(H.classify_error(_grim)))

print("\n=== T5: kill switch RECIPE_REPAIR_MAX_ATTEMPTS=0 → no re-ask, immediate sentinel ===")
plan, err, out, stub = run_gen([clean_plan(caption_style="NotAStyle")], env_attempts="0")
check("single attempt only", len(stub.post_users) == 1)
check("no [recipe-repair] line", "[recipe-repair]" not in out)
check("raises RecipeInvalidError after 1 attempt",
      isinstance(err, H.RecipeInvalidError) and "after 1 attempt(s)" in str(err), repr(err))
plan, err, out, stub = run_gen(
    [clean_plan(transitions=[{"type": "ZoomThrough", "after_word_index": 4}])], env_attempts="0")
check("demotion still ALWAYS-ON with kill switch", err is None and "action=demote" in out, repr(err))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
print("ALL RECIPE-REPAIR CASES PASS")
