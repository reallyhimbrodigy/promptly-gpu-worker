"""Directive #8 Parts 4+5: variety telemetry, orphan cascade, eval TCO partners."""
import contextlib
import io
import sys
import textwrap

import handler as H
import recipe_eval

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

print("=== V1: _vocab_markers from a synthetic plan ===")
PLAN = {
    "caption_style": "Prime",
    "motion_graphics": [{"type": "StatCard"}, {"type": "IconLabel"}, {"type": "StatCard"}],
    "emphasis_moments": [{"zoom_effect": {"type": "SnapReframe"}},
                          {"zoom_effect": {"type": "SmoothPush"}},
                          {"zoom_effect": None}],
    "sound_effects": [{"sound": "boom"}, {"sound": "pop"}, {"sound": "boom"}],
    "_resolved_tight_cut_overlays": [{"type": "ShutterFlash", "after_word_index": 16},
                                      {"type": "LightLeak", "after_word_index": 99}],
    "transitions": [{"type": "DipToBlack"}],
    "broll_clips": [{"keyword": "k1"}, {"keyword": "k2"}],
}
v = H._vocab_markers(PLAN)
check("caption_style carried", v.get("caption_style") == "Prime")
check("mg_types sorted-unique", v.get("mg_types") == ["IconLabel", "StatCard"])
check("zoom_types from emphasis (None skipped)", v.get("zoom_types") == ["SmoothPush", "SnapReframe"])
check("sfx unique", v.get("sfx") == ["boom", "pop"])
check("tco_types from RESOLVED overlays", v.get("tco_types") == ["LightLeak", "ShutterFlash"])
check("transition_types", v.get("transition_types") == ["DipToBlack"])
check("broll_count", v.get("broll_count") == 2)
check("junk-safe", isinstance(H._vocab_markers(None), dict) and H._vocab_markers(None).get("broll_count") == 0)

print("\n=== V2: complete write carries result.vocab (wire pin) ===")
src = open("handler.py").read()
_c = src.find('status="completed", phase="Done"')
check("vocab in the complete terminal write",
      '"vocab": _vocab_markers(edit_plan)' in src[_c:_c + 700])

print("\n=== O1: orphan cascade — the REAL fix-1 block, extracted + exec'd ===")
lines = src.split("\n")
starts = [i for i, l in enumerate(lines) if "[fix-1 → orphan cascade" in l]
check("cascade block present exactly once", len(starts) == 1)
s = starts[0]
e = s
while "continue" not in lines[e]:
    e += 1
    assert e - s < 30, "cascade block end not found"
block = textwrap.dedent("\n".join(lines[s:e + 1]))

def run_cascade(covered):
    ns = {"_record_divergence": H._record_divergence, "print": print}
    committed = []
    code = ("for _sfx in [{'word': 'boom-word'}]:\n"
            "    _sfx_wi = 7\n"
            "    _sound_style = 'boom'\n"
            "    _sfx_covered_words = " + repr(covered) + "\n"
            + textwrap.indent(block, "    ")
            + "\n    committed.append(_sfx_wi)\n")
    ns["committed"] = committed
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(code, "<fix-1-block>", "exec"), ns)
    return committed, buf.getvalue()

committed, o = run_cascade(set())
check("orphan DROPPED (not committed)", committed == [], str(committed))
check("orphan cascade log line", "orphan cascade: boom word 7" in o and "DROPPED" in o)
check("[divergence] action=orphan_cascade_drop", "orphan_cascade_drop" in o and "[divergence]" in o)
committed, o = run_cascade({7})
check("partnered SFX commits normally, zero cascade lines",
      committed == [7] and "orphan" not in o)

print("\n=== O2: recipe_eval counts TCOs as visual partners ===")
words = [{"word": f"w{i}", "start": i * 0.4, "end": i * 0.4 + 0.35} for i in range(30)]
def eval_plan(with_tco):
    p = {"video_plan": {"what_happens": "a", "key_moments": [],
                        "arc_segments": [{"start_word_index": 0, "end_word_index": 29,
                                           "position": "hook", "intensity": 0.5}],
                        "editorial_vision": "v", "hook_word_index": 0,
                        "payoff_word_index": 20, "close_word_index": 29},
         "caption_style": "CleanCut", "caption_keywords": [],
         "transitions": [], "motion_graphics": [], "emphasis_moments": [],
         "text_overlays": [], "broll_clips": [],
         "sound_effects": [{"sound": "shutter", "word_index": 16},
                            {"sound": "whoosh", "word_index": 17}],
         "tight_cut_overlays": ([{"type": "ShutterFlash", "after_word_index": 16}]
                                 if with_tco else []),
        }
    return recipe_eval.evaluate_recipe(p, words, [], 12.0, tight_boundaries=[16])
rep = eval_plan(True)
partner_fails = [f for f in rep.failures if f[0] == "sfx-partner"]
check("TCO-partnered SFX (both flanking words) no longer FAIL",
      partner_fails == [], str(partner_fails))
rep = eval_plan(False)
partner_fails = [f for f in rep.failures if f[0] == "sfx-partner"]
check("orphan SFX still FAILs without the TCO", len(partner_fails) == 2, str(partner_fails))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL VOCAB+ORPHAN CASES PASS")
