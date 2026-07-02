"""SceneTitle guards — offline behavioral tests (3-stub harness).

Fixture: 20 words, word i spans [i*0.4, i*0.4+0.35].
- remove word 5           -> tight boundary  (gap 0.45s) at src awi 4
- remove words 8,9        -> CUT boundary    (gap 0.85s) at src awi 7  (>=0.70)
- remove words 12..16     -> CUT boundary    (gap 2.05s) at src awi 11
- (for the wide-fit case a separate cut plan removes 10 words -> 4.05s gap)
FilmStrip natural 1.2s needs gap >= 2.4s; SceneTitle 1.8s needs >= 3.6s.
"""
import contextlib
import copy
import io
import sys

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

def words(n):
    return [{"word": f"w{i}", "punctuated_word": f"w{i}", "start": round(i * 0.4, 2),
             "end": round(i * 0.4 + 0.35, 2), "confidence": 0.99, "speaker": 0}
            for i in range(n)]

def clean_plan(**over):
    p = {"caption_style": "Prime", "caption_keywords": [],
         "transitions": [], "tight_cut_overlays": [],
         "motion_graphics": [], "emphasis_moments": [], "text_overlays": [],
         "broll_clips": [], "sound_effects": [],
         "audio_denoise": False, "outro": "none", "aspect_ratio": "9:16"}
    p.update(over)
    return p

def run_gen(plans, cut_plan, n_words=20, env_attempts=None):
    import os
    plans = [copy.deepcopy(p) for p in plans]
    calls = []
    def stub(client, post_sys, post_user, video_part, model):
        calls.append(post_user)
        return copy.deepcopy(plans.pop(0))
    saved = (H.compute_mechanical_cuts, H._call_gemini_post_cuts, H._get_genai_client)
    env_saved = os.environ.pop("RECIPE_REPAIR_MAX_ATTEMPTS", None)
    if env_attempts is not None:
        os.environ["RECIPE_REPAIR_MAX_ATTEMPTS"] = env_attempts
    H.compute_mechanical_cuts = lambda w, source_path=None: copy.deepcopy(cut_plan)
    H._call_gemini_post_cuts = stub
    H._get_genai_client = lambda: None
    buf, err, out_plan = io.StringIO(), None, None
    try:
        with contextlib.redirect_stdout(buf):
            out_plan = H.generate_edit_gemini(
                video_path="/x.mp4", vibe="t", duration=n_words * 0.4,
                deepgram_words=words(n_words), inline_video_bytes=b"x")
    except Exception as e:
        err = e
    finally:
        (H.compute_mechanical_cuts, H._call_gemini_post_cuts, H._get_genai_client) = saved
        os.environ.pop("RECIPE_REPAIR_MAX_ATTEMPTS", None)
        if env_saved is not None:
            os.environ["RECIPE_REPAIR_MAX_ATTEMPTS"] = env_saved
    return out_plan, err, buf.getvalue(), calls

CUTS = {"remove_words": [{"word_index": 5}, {"word_index": 8}, {"word_index": 9},
                          {"word_index": 12}, {"word_index": 13}, {"word_index": 14},
                          {"word_index": 15}, {"word_index": 16}],
        "notes": "stub", "pacing": "fast"}
# kept-space: src4->kept4 (tight), src7->kept6 (0.85s cut), src11->kept9 (2.05s cut)

print("=== T1: title-less SceneTitle transition -> RAISE -> repair net re-asks ===")
plan, err, out, calls = run_gen(
    [clean_plan(transitions=[{"type": "SceneTitle", "after_word_index": 9}]),
     clean_plan()],
    CUTS)
check("net repaired (second pass returns)", err is None and isinstance(plan, dict), repr(err))
check("[recipe-repair] fired with the title message",
      "[recipe-repair] attempt=1" in out and "SceneTitle requires a title" in out)
check("re-ask carries the verbatim error",
      len(calls) == 2 and "SceneTitle requires a title" in calls[1])

print("\n=== T2: unfit FilmStrip (0.85s gap < 2.4s) -> demote_heavy_unfit, job lives ===")
plan, err, out, calls = run_gen(
    [clean_plan(transitions=[{"type": "FilmStrip", "after_word_index": 6,
                               "title": None}])],
    CUTS)
check("no raise", err is None, repr(err))
check("action=demote_heavy_unfit logged", "action=demote_heavy_unfit" in out)
_ovl = [o for o in (plan or {}).get("_resolved_tight_cut_overlays") or []
        if o.get("after_word_index") == 7]
check("light overlay appended at the boundary (src awi 7)", len(_ovl) == 1, str(_ovl))
check("FilmStrip not applied", "Transition 'FilmStrip' applied" not in out)

print("\n=== T3: fit SceneTitle (4.05s gap >= 3.6s) with title -> passes untouched ===")
WIDE = {"remove_words": [{"word_index": i} for i in range(5, 15)],
        "notes": "stub", "pacing": "fast"}   # gap = w15.start - w4.end = 6.0-1.95 = 4.05s
plan, err, out, calls = run_gen(
    [clean_plan(transitions=[{"type": "SceneTitle", "after_word_index": 4,
                               "title": "CHAPTER TWO"}])],
    WIDE)
check("no raise", err is None, repr(err))
check("SceneTitle applied untouched", "Transition 'SceneTitle' applied" in out)
check("no demotion fired", "demote_heavy_unfit" not in out and "action=demote" not in out)

print("\n=== T4: crossfade on LISTED tight boundary keeps action=demote (precedence) ===")
plan, err, out, calls = run_gen(
    [clean_plan(transitions=[{"type": "ZoomThrough", "after_word_index": 4}])],
    CUTS)
check("no raise", err is None, repr(err))
check("plain demote (not heavy_unfit)", "action=demote " in out or 'action=demote\n' in out or "action=demote " in out.replace("action=demote_heavy_unfit",""))
check("no heavy_unfit label", "demote_heavy_unfit" not in out)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL SCENETITLE-GUARD CASES PASS")
