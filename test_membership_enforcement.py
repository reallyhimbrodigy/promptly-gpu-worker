"""Transition membership enforcement + boundary-coverage telemetry — offline.

Fixture: 20 words (0.4s pitch). remove word 5 -> TIGHT boundary at src awi 4
(0.45s gap); remove words 8,9 -> CUT boundary at src awi 7 (0.85s gap).
Word src 12 (kept-idx 9, mid-clip, no removal around it) is in NEITHER list.
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

def words(n=20):
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

CUTS = {"remove_words": [{"word_index": 5}, {"word_index": 8}, {"word_index": 9}],
        "notes": "stub", "pacing": "fast"}
# kept-space: src4->kept4 (TIGHT list), src7->kept6 (CUT list), src12->kept9 (NEITHER)

def run_gen(plan, cut_plan=CUTS):
    saved = (H.compute_mechanical_cuts, H._call_gemini_post_cuts, H._get_genai_client)
    H.compute_mechanical_cuts = lambda w, source_path=None: copy.deepcopy(cut_plan)
    H._call_gemini_post_cuts = lambda *a, **k: copy.deepcopy(plan)
    H._get_genai_client = lambda: None
    buf, err, out_plan = io.StringIO(), None, None
    try:
        with contextlib.redirect_stdout(buf):
            out_plan = H.generate_edit_gemini(
                video_path="/x.mp4", vibe="t", duration=8.0,
                deepgram_words=words(), inline_video_bytes=b"x")
    except Exception as e:
        err = e
    finally:
        (H.compute_mechanical_cuts, H._call_gemini_post_cuts, H._get_genai_client) = saved
    return out_plan, err, buf.getvalue()

print("=== T1: member crossfade at a CUT boundary (kept 6 -> src 7) passes ===")
plan, err, out = run_gen(clean_plan(transitions=[{"type": "ZoomThrough", "after_word_index": 6}]))
check("no raise", err is None, repr(err))
check("transition applied", "Transition 'ZoomThrough' applied" in out)
check("no nonmember demotion", "demote_nonmember" not in out)

print("\n=== T2: NON-member crossfade (kept 9 -> src 11, in neither list) demotes ===")
plan, err, out = run_gen(clean_plan(transitions=[{"type": "ZoomThrough", "after_word_index": 9}]))
check("no raise", err is None, repr(err))
check("action=demote_nonmember logged", "action=demote_nonmember" in out)
_ovl = [o for o in (plan or {}).get("_resolved_tight_cut_overlays") or []
        if o.get("after_word_index") == 12]
check("light overlay at the demoted awi (kept 9 -> src 12)", len(_ovl) == 1, str(_ovl))
check("transition not applied", "Transition 'ZoomThrough' applied" not in out)

print("\n=== T3: NON-member zero-handle (DipToBlack at src 12) demotes too ===")
plan, err, out = run_gen(clean_plan(transitions=[{"type": "DipToBlack", "after_word_index": 9}]))
check("no raise", err is None, repr(err))
check("action=demote_nonmember logged", "action=demote_nonmember" in out)

print("\n=== T4: member zero-handle at the TIGHT boundary (kept 4 -> src 4) passes ===")
plan, err, out = run_gen(clean_plan(transitions=[{"type": "DipToBlack", "after_word_index": 4}]))
check("no raise", err is None, repr(err))
check("no nonmember demotion", "demote_nonmember" not in out)
check("transition applied", "Transition 'DipToBlack' applied" in out)

print("\n=== T5: boundary-coverage telemetry fires + summary present ===")
plan, err, out = run_gen(clean_plan())
check("no raise", err is None, repr(err))
check("coverage summary line", "[boundary-coverage] splices=" in out, out[-400:])
# The two mechanical splices both map to detector lists -> missing=0 here
check("both splices covered (cut+tight)", "cut=1 tight=1 missing=0" in out, out[-400:])

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL MEMBERSHIP-ENFORCEMENT CASES PASS")
