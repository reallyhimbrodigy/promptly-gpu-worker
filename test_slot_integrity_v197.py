"""v197 battery: slot-integrity tripwire (fault-injection), degrade semantics,
HardHold schema gates, and item 5's verify-first range-class case."""
import sys

import handler as H
import render_schemas as RS

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

PRE = [(0, 36), (2, 30)]

print("=== T1: FAULT INJECTION — removed slot trips the wire ===")
try:
    H._assert_slot_integrity(PRE, [{"afterClipIndex": 0, "durationInFrames": 36}])
    check("removed slot raises", False)
except RuntimeError as e:
    check("removed slot raises", "SLOT INTEGRITY VIOLATION" in str(e))

print("\n=== T2: FAULT INJECTION — resized slot trips the wire ===")
try:
    H._assert_slot_integrity(PRE, [
        {"afterClipIndex": 0, "durationInFrames": 36},
        {"afterClipIndex": 2, "durationInFrames": 18}])
    check("resized slot raises", False)
except RuntimeError as e:
    check("resized slot raises", "SLOT INTEGRITY VIOLATION" in str(e))

print("\n=== T3: DEGRADE passes — same slots, type changed ===")
try:
    H._assert_slot_integrity(PRE, [
        {"afterClipIndex": 0, "durationInFrames": 36, "type": "HardHold"},
        {"afterClipIndex": 2, "durationInFrames": 30, "type": "ZoomThrough"}])
    check("degrade-only survives", True)
except RuntimeError:
    check("degrade-only survives", False)

print("\n=== T4: schema — HardHold render-legal, recipe-illegal ===")
ok_render = True
try:
    RS.TransitionSpec(afterClipIndex=0, type="HardHold", durationInFrames=36,
                      clipAStartFromFrames=0, clipBStartFromFrames=0,
                      clipAPlaybackRate=1.0, clipBPlaybackRate=1.0)
except Exception as e:
    ok_render = False
check("render input accepts HardHold", ok_render)
check("recipe vocabulary still excludes HardHold",
      "HardHold" not in getattr(RS, "VALID_TRANSITION_TYPES", set())
      and "HardHold" not in str(RS.TransitionType))

print("\n=== T5 (item 5 VERIFY-FIRST): range removal WITH WORDS — does the divider fire? ===")
def W(i, s, e, w="w"):
    return {"word": f"{w}{i}", "punctuated_word": f"{w}{i}", "start": s, "end": e}
# kept w0 [0..1.0]; RANGE removes w1..w2 ([1.1..1.9], real words); kept w3 [2.3..2.9]
words = [W(0, 0.0, 1.0), W(1, 1.1, 1.5, "rm"), W(2, 1.5, 1.9, "rm"), W(3, 2.3, 2.9)]
cuts, removed = H.build_clips_from_words(
    words, [{"after_word_index": 0, "before_word_index": 3, "reason": "restart"}],
    video_duration=10.0)
check("range words entered removed set", removed == {1, 2}, str(removed))
check("release respects removed.start − 75ms (divider FIRES on ranges)",
      cuts[0]["source_end"] <= 1.1 - 0.075 + 1e-6 or cuts[0]["source_end"] <= 1.025 + 1e-6,
      f"src_end={cuts[0]['source_end']}")
check("incoming edge floors at removed END (1.9)",
      cuts[1]["source_start"] >= 1.9 - 0.05 - 1e-6, f"src_start={cuts[1]['source_start']}")

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL V197 SLOT-INTEGRITY CASES PASS")
