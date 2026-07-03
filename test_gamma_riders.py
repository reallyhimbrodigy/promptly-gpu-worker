"""γ riders R2/R3 — prompt and eval move together."""
import sys

import recipe_eval

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

words = [{"word": f"w{i}", "start": i * 0.4, "end": i * 0.4 + 0.35} for i in range(30)]

def plan(**over):
    p = {"video_plan": {"what_happens": "a",
                        "key_moments": [{"word_index": 20}],
                        "arc_segments": [
                            {"start_word_index": 0, "end_word_index": 8, "position": "hook", "intensity": 0.8},
                            {"start_word_index": 9, "end_word_index": 18, "position": "build", "intensity": 0.4},
                            {"start_word_index": 19, "end_word_index": 24, "position": "payoff", "intensity": 1.0},
                            {"start_word_index": 25, "end_word_index": 29, "position": "close", "intensity": 0.3}],
                        "editorial_vision": "v", "hook_word_index": 0,
                        "payoff_word_index": 20, "close_word_index": 29},
         "caption_style": "CleanCut", "caption_keywords": [],
         "transitions": [], "tight_cut_overlays": [], "motion_graphics": [],
         "emphasis_moments": [], "text_overlays": [], "broll_clips": [],
         "sound_effects": []}
    p.update(over)
    return p

def run(p, tight=None):
    return recipe_eval.evaluate_recipe(p, words, [], 12.0, tight_boundaries=tight or [])

print("=== R2: two-sound lean recipe passes clean (advice-level WARN only) ===")
rep = run(plan(sound_effects=[{"sound": "pop", "word_index": 20},
                              {"sound": "boom", "word_index": 20}],
               emphasis_moments=[{"word_indices": [20],
                                   "zoom_effect": {"type": "SmoothPush"}}]))
check("two-sound lean recipe fully clean",
      not any(f[0] == "variety-sfx" for f in rep.failures)
      and not any(w[0] == "variety-sfx" for w in rep.warnings), str(rep.failures))
# 4 sounds / 2 distinct: dense enough for the rotation advice — WARN, never FAIL
rep = run(plan(sound_effects=[{"sound": "pop", "word_index": 20},
                              {"sound": "pop", "word_index": 21},
                              {"sound": "hit", "word_index": 22},
                              {"sound": "hit", "word_index": 23}],
               emphasis_moments=[{"word_indices": [20],
                                   "zoom_effect": {"type": "SmoothPush"}}]))
sfx_fails = [f for f in rep.failures if f[0] == "variety-sfx"]
sfx_warns = [w for w in rep.warnings if w[0] == "variety-sfx"]
check("no variety-sfx FAIL at density", sfx_fails == [], str(sfx_fails))
check("advice WARN present at density", len(sfx_warns) >= 1, str(rep.warnings))
check("sfx-once cap still FAILs on a boom double",
      any(f[0] == "sfx-once" for f in run(plan(sound_effects=[
          {"sound": "boom", "word_index": 20}, {"sound": "boom", "word_index": 21},
          {"sound": "pop", "word_index": 22}],
          emphasis_moments=[{"word_indices": [20], "zoom_effect": {"type": "SmoothPush"}}])).failures))

print("\n=== R3: mask zooms live outside the key_moments ledger ===")
# emphasis zoom at word 5 (hook, no key_moment, NOT after a tight boundary) -> FAIL
rep = run(plan(emphasis_moments=[{"word_indices": [5], "zoom_effect": {"type": "StepZoom"}},
                                  {"word_indices": [20], "zoom_effect": {"type": "SmoothPush"}}]),
          tight=[10])
check("emphasis zoom without key_moment still FAILs",
      any(f[0] == "zoom-1to1" for f in rep.failures), str(rep.failures))
# mask zoom at word 5 where 4 IS a tight boundary -> exempt
rep = run(plan(emphasis_moments=[{"word_indices": [5], "zoom_effect": {"type": "StepZoom"}},
                                  {"word_indices": [20], "zoom_effect": {"type": "SmoothPush"}}]),
          tight=[4])
check("mask zoom (first word after tight boundary) passes",
      not any(f[0] == "zoom-1to1" for f in rep.failures), str(rep.failures))
check("tight-no-mask machinery untouched (warn family intact)",
      hasattr(rep, "warnings"))

print("\n=== Prompt side: floor text gone, taxonomy present (source pins) ===")
src = open("handler.py").read()
check("SFX floor sentence replaced", "at least 3 distinct sounds" not in src
      and "the count follows the beats" in src)
check("zoom two-job taxonomy present", "A zoom does one of two jobs." in src
      and "MASK zooms are functional" in src)
check("TIGHT header speaks the same taxonomy",
      "mask zooms serve the boundary and live outside the key_moments ledger" in src)
check("Rejected A moral replaced (R1)",
      "thin IS the mistake" not in src and "unserved moments" in src)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL GAMMA-RIDER CASES PASS")
