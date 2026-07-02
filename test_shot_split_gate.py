"""Shot-split gate index-space fix — offline behavioral tests.

The gate used to compare KEPT-space split indices against SOURCE-space emitted
after_word_index values, so any removed word before a shot boundary made the
gate silently miss (splits never happened; the transition dropped as
"lands in the last clip"). Same 3-stub harness as test_recipe_repair.py.

Fixture: 12 words, word i spans [i*0.4, i*0.4+0.35]. Mechanical cuts remove
word 1 (early -> kept/src skew of 1 for everything after). Shot change at
3.55s = source word 8's end = KEPT index 7. A DipToBlack (zero-handle, so the
crossfade-on-tight demotion leaves it alone) emitted at kept index 7
translates to source awi 8 — under the bug the gate compared 7 vs {8} and
missed; fixed, it translates 7->8 and matches.
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

WORDS = [
    {"word": f"w{i}", "punctuated_word": f"w{i}", "start": round(i * 0.4, 2),
     "end": round(i * 0.4 + 0.35, 2), "confidence": 0.99, "speaker": 0}
    for i in range(12)
]
CUT_PLAN = {"remove_words": [{"word_index": 1}], "notes": "stub", "pacing": "fast"}

def clean_plan(**over):
    p = {
        "caption_style": "Prime", "caption_keywords": [],
        "transitions": [], "tight_cut_overlays": [],
        "motion_graphics": [], "emphasis_moments": [], "text_overlays": [],
        "broll_clips": [], "sound_effects": [],
        "audio_denoise": False, "outro": "none", "aspect_ratio": "9:16",
    }
    p.update(over)
    return p

def run_gen(plan, shot_changes):
    saved = (H.compute_mechanical_cuts, H._call_gemini_post_cuts, H._get_genai_client)
    H.compute_mechanical_cuts = lambda w, source_path=None: copy.deepcopy(CUT_PLAN)
    H._call_gemini_post_cuts = lambda *a, **k: copy.deepcopy(plan)
    H._get_genai_client = lambda: None
    buf = io.StringIO()
    err, out_plan = None, None
    try:
        with contextlib.redirect_stdout(buf):
            out_plan = H.generate_edit_gemini(
                video_path="/nonexistent.mp4", vibe="test", duration=4.8,
                deepgram_words=copy.deepcopy(WORDS), shot_changes=shot_changes,
                vocal_emphasis=[], source_loudness={}, face_positions=[],
                inline_video_bytes=b"fake", premium=False,
            )
    except Exception as e:
        err = e
    finally:
        (H.compute_mechanical_cuts, H._call_gemini_post_cuts, H._get_genai_client) = saved
    return out_plan, err, buf.getvalue()

print("=== T1: removed word BEFORE boundary + transition emitted -> gate now FIRES ===")
plan, err, out = run_gen(
    clean_plan(transitions=[{"type": "DipToBlack", "after_word_index": 7}]),
    shot_changes=[3.55])
check("no raise", err is None, repr(err))
_cuts = (plan or {}).get("cuts") or []
_split = [c for c in _cuts if abs(float(c.get("source_end", -1)) - 3.55) < 0.02]
check("clip split at the shot change (source_end==3.55)", len(_split) == 1, str(_cuts))
check("transition applied at the split clip",
      _split and _split[0].get("transition_out") == "DipToBlack", str(_split))
check("'Transition applied' logged (was DROP under the bug)",
      "Transition 'DipToBlack' applied" in out)
check("gate-corrected divergence logged (blast radius visible)",
      "shot_split_gate_corrected" in out)

print("\n=== T2: NO transition emitted -> split correctly HELD (no gate-in) ===")
plan, err, out = run_gen(clean_plan(), shot_changes=[3.55])
check("no raise", err is None, repr(err))
_cuts = (plan or {}).get("cuts") or []
check("no clip boundary at 3.55 (split held)",
      not [c for c in _cuts if abs(float(c.get("source_end", -1)) - 3.55) < 0.02], str(_cuts))
check("no corrected-divergence when outcomes agree", "shot_split_gate_corrected" not in out)

print("\n=== T3: no removed words before boundary -> behavior identical, no divergence ===")
CUT_PLAN = {"remove_words": [], "notes": "stub", "pacing": "fast"}
plan, err, out = run_gen(
    clean_plan(transitions=[{"type": "DipToBlack", "after_word_index": 8}]),
    shot_changes=[3.55])
check("no raise", err is None, repr(err))
check("no corrected-divergence (kept==src, old and new agree)",
      "shot_split_gate_corrected" not in out)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL SHOT-SPLIT-GATE CASES PASS")
