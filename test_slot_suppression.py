"""v196.1 interim slot suppression battery: the kill is total, logged, and
leaves everything else untouched."""
import contextlib
import io
import sys

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

print("=== S1: slot-heavy plan (98869728 profile) — every slot dies ===")
cuts = [{"source_start": i * 2.0, "source_end": i * 2.0 + 1.5,
         "transition_out": t} for i, t in enumerate(
        ["CardSwipe", "SlideOver", "ZoomThrough", "StepPush",
         "CrossfadeZoom", "SlideOver", "ZoomThrough", "CardSwipe", "none"])]
plan = {"transitions": [{"type": "CardSwipe", "after_word_index": 1}] * 8,
        "tight_cut_overlays": [{"type": "ShutterFlash"}],
        "_resolved_tight_cut_overlays": [{"type": "ShutterFlash"}],
        "sound_effects": [{"sfx": "whoosh_slow", "word_index": 3}],
        "caption_style": "Gadzhi"}
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    n = H._suppress_transition_slots(cuts, plan)
check("all 8 cut slots + 8 plan transitions + 2 TCOs suppressed", n == 18, f"n={n}")
check("every transition_out now none",
      all(c["transition_out"] == "none" for c in cuts))
check("plan transitions emptied", plan["transitions"] == [] and
      plan["tight_cut_overlays"] == [] and plan["_resolved_tight_cut_overlays"] == [])
check("SFX KEPT (serve the word at the bare cut)",
      len(plan["sound_effects"]) == 1)
check("caption style untouched", plan["caption_style"] == "Gadzhi")
check("divergence line logged with counts",
      "interim_slot_suppression" in buf.getvalue()
      and '"cut_slots":8' in buf.getvalue().replace(" ", ""), buf.getvalue()[-200:])

print("\n=== S2: transition-free plan — sanitizer is a silent no-op ===")
cuts2 = [{"source_start": 0.0, "source_end": 2.0, "transition_out": "none"}]
plan2 = {"transitions": [], "tight_cut_overlays": []}
buf2 = io.StringIO()
with contextlib.redirect_stdout(buf2):
    n2 = H._suppress_transition_slots(cuts2, plan2)
check("no-op count zero", n2 == 0)
check("no divergence emitted", "interim_slot_suppression" not in buf2.getvalue())

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL SLOT-SUPPRESSION CASES PASS")
