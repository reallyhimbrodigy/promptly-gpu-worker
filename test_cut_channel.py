"""Gemini cut channel (cut_refinements) — offline behavioral tests.

3-stub harness. 24 words (0.4s pitch), mechanical pass removes src word 5
(23 kept). video_plan anchors: hook=0, key_moment=10, payoff=15, close=22
(kept space; translated to src by the pipeline before the merge).
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
         for i in range(24)]
CUTS = {"remove_words": [{"word_index": 5}], "notes": "stub", "pacing": "fast"}

def plan(refs=None, **over):
    p = {"video_identity": "x" * 40,
         "video_plan": {"what_happens": "a", "key_moments": [{"word_index": 10}],
                        "arc_segments": [{"start_word_index": 0, "end_word_index": 22,
                                           "position": "hook", "intensity": 0.5}],
                        "editorial_vision": "v", "hook_word_index": 0,
                        "payoff_word_index": 15, "close_word_index": 22},
         "caption_style": "Prime", "caption_keywords": [],
         "transitions": [], "tight_cut_overlays": [], "motion_graphics": [],
         "emphasis_moments": [], "text_overlays": [], "broll_clips": [],
         "sound_effects": [], "caption_position_changes": [],
         "thumbnail_word_index": 1,
         "audio_denoise": False, "outro": "none", "aspect_ratio": "9:16"}
    if refs is not None:
        p["cut_refinements"] = refs
    p.update(over)
    return p

def run(plans, resolved_policy=None):
    seq = [copy.deepcopy(p) for p in (plans if isinstance(plans, list) else [plans])]
    H.compute_mechanical_cuts = lambda w, source_path=None: copy.deepcopy(CUTS)
    H._call_gemini_post_cuts = lambda *a, **k: seq.pop(0)
    H._get_genai_client = lambda: None
    buf, err, out = io.StringIO(), None, None
    try:
        with contextlib.redirect_stdout(buf):
            out = H.generate_edit_gemini(
                video_path="/x.mp4", vibe="t", duration=9.6,
                deepgram_words=copy.deepcopy(WORDS), inline_video_bytes=b"x",
                resolved_policy=resolved_policy)
    except Exception as e:
        err = e
    return out, err, buf.getvalue()

print("=== T1: refinement removes words -> clips rebuilt from the union ===")
out, err, o = run(plan(refs=[{"start_word_index": 2, "end_word_index": 3, "reason": "abandoned start"}]))
check("no raise", err is None, repr(err))
check("[cut-refine] applied", "[cut-refine] kept=[2-3] reason=abandoned start" in o)
check("clip boundary lands at the excision (src 1.55->1.6 splice)",
      any(abs(float(c.get("source_end", 0)) - 0.75) < 0.05 for c in out["cuts"]), str(out["cuts"][:3]))

print("\n=== T2: protected words (payoff) -> range dropped with divergence ===")
out, err, o = run(plan(refs=[{"start_word_index": 14, "end_word_index": 16, "reason": "drag"}]))
check("no raise", err is None, repr(err))
check("drop_protected divergence", "action=drop_protected" in o)
check("nothing applied", "[cut-refine] kept=" not in o)

print("\n=== T3: over 25% cap -> LARGEST ranges dropped first ===")
out, err, o = run(plan(refs=[{"start_word_index": 16, "end_word_index": 21, "reason": "big"},
                              {"start_word_index": 2, "end_word_index": 3, "reason": "small"}]))
check("no raise", err is None, repr(err))
check("over_cap divergence on the large range", "action=over_cap" in o)
check("small range survives", "[cut-refine] kept=[2-3]" in o and "kept=[16-21]" not in o)

print("\n=== T4: kill test — empty/absent cut_refinements byte-identical ===")
out_a, _, _ = run(plan())
out_b, _, _ = run(plan(refs=[]))
check("empty == absent", json.dumps(out_a, sort_keys=True, default=str)
      == json.dumps(out_b, sort_keys=True, default=str))

print("\n=== T5: malformed entry -> RAISE -> repair net corrects ===")
out, err, o = run([plan(refs=[{"start_word_index": "x", "end_word_index": 3, "reason": "r"}]),
                   plan()])
check("net repaired", err is None and isinstance(out, dict), repr(err))
check("[recipe-repair] fired", "[recipe-repair] attempt=1" in o)

print("\n=== T6: EditPolicy filler_trim=off zeroes the channel ===")
class _Pol:
    mode = "deny_list"
    def off_features(self): return ["filler_trim"]
out, err, o = run(plan(refs=[{"start_word_index": 2, "end_word_index": 3, "reason": "r"}]),
                  resolved_policy=_Pol())
check("no raise", err is None, repr(err))
check("channel zeroed with log", "cut_refinement(s) zeroed" in o and "[cut-refine] kept=" not in o)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL CUT-CHANNEL CASES PASS")
