"""CERT — the overlap-exclusion arm (density_variant=6), BOTH halves or neither.

THE EXCLUSION IS ENFORCED TWICE: as prompt text telling the model its
overlapping b-roll will be discarded, and as a code drop in render_multi_clip
that discards it. Changing one half alone is worse than changing neither —
prompt-only leaves the code silently deleting what the model now believes is
allowed; code-only leaves the model still self-censoring. Zac's ruling: together.

CORPUS EVIDENCE: 17 of 70 reference cutaways (24%) sit on a beat that also
carries a card or text placement. The references treat a card over its own
b-roll as ONE thought; our pipeline treats it as a collision.

Offline. Zero network, zero Modal, zero Gemini.
"""
import sys

import handler as H

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"\n       :: {detail}" if detail else ""))


SRC = open("handler.py", encoding="utf-8").read()

print("=== C1: the PROMPT half ===")
check("the old exclusion text still exists as an anchor",
      H._OVERLAP_PROMPT_OLD in SRC)
check("the replacement differs", H._OVERLAP_PROMPT_OLD != H._OVERLAP_PROMPT_NEW)
check("replacement drops 'the pipeline drops any B-roll'",
      "the pipeline drops any B-roll" not in H._OVERLAP_PROMPT_NEW)
check("replacement states the SAME-MOMENT test",
      "same moment" in H._OVERLAP_PROMPT_NEW.lower())
check("replacement carries its evidence (house style)",
      "17 of 70" in H._OVERLAP_PROMPT_NEW)

print("\n=== C2: the CODE half ===")
check("the drop is gated on the arm",
      "if _conflict and not _overlap_arm_on:" in SRC,
      "the code still drops unconditionally — prompt-only arm")
check("the arm flag is READ from edit_plan",
      '(edit_plan or {}).get("_density_variant")' in SRC,
      "render_multi_clip has edit_plan, not input_data")

print("\n=== C3: the two halves CANNOT diverge ===")
check("the variant is CARRIED to the render half",
      'edit_plan["_density_variant"] = str(_dv_ov)' in SRC,
      "the prompt half would apply and the code half would not")
_i = SRC.find("overlap arm: prompt anchor missing")
check("a missing prompt anchor RAISES", _i > 0,
      "the prompt half could silently no-op while the code half changed")
check("the raise names the half-applied hazard",
      "half-applied" in SRC[max(0, _i - 200):_i + 300])

print("\n=== C4: INERT at every other variant ===")
_g = SRC.find("if _dv == 6:")
check("the prompt swap is gated on _dv == 6", _g > 0)
check("the swap sits inside that gate",
      0 < _g < SRC.find("_OVERLAP_PROMPT_OLD, _OVERLAP_PROMPT_NEW, 1)"))
check("the code half compares to '6' explicitly", '== "6"' in SRC)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
