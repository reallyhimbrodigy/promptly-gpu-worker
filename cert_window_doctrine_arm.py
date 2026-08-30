"""CERT — the window-doctrine arm (density_variant=4), both directions.

THE DOCTRINE UNDER TEST. "At most one dominant visual event owns any ~2-second
window" is stated FOUR times in the editorial prompt and framed as the
discipline "everything else in this prompt serves". It is a ceiling with no
floor.

WHY IT IS TESTABLE NOW — corpus evidence, not inference. Ten reference edits,
193 beats: 77% of cards and 83% of text placements share their beat with another
element; 24% of reference cutaways sit on a beat that also carries a card or
text placement. The references treat co-occurrence as normal composition.

THE REPLACEMENT IS A FLOOR, NOT A DELETION — every element in a window must
serve the SAME moment. Two elements on one beat is craft; two moments on one
beat is mud.

BOTH DIRECTIONS:
  INERT  — at every variant except 4 the prompt is BYTE-IDENTICAL. An arm that
           leaks into the control is not an arm.
  ACTIVE — at variant 4 all four statements are replaced, and the ceiling
           language is GONE (not merely supplemented).
  LOUD   — a missing anchor RAISES rather than silently no-opping. A swap that
           cannot find its text is the built-not-wired class, and this repo has
           shipped it twelve times.

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


SWAPS = H._WINDOW_DOCTRINE_SWAPS
SRC = open("handler.py", encoding="utf-8").read()

print("=== C1: the swap table is real and complete ===")
check("four doctrine statements are covered", len(SWAPS) == 4,
      f"got {len(SWAPS)} — the doctrine is stated four times")
for i, (old, new) in enumerate(SWAPS):
    check(f"  swap {i}: the OLD text exists in the prompt source",
          old in SRC, f"anchor missing — the arm would raise at runtime")
    check(f"  swap {i}: old != new", old != new)

print("\n=== C2: the CEILING language is removed, not supplemented ===")
_ceiling = ("at most one dominant visual event owns any",
            "A window holds at most one dominant event",
            "one dominant element owning that beat",
            "A window holds one dominant visual event")
for c in _ceiling:
    _covered = any(c in old for old, _ in SWAPS)
    check(f"ceiling phrase is inside a swap: {c[:46]!r}", _covered,
          "this statement survives variant 4 — the arm is partial")
for _, new in SWAPS:
    check(f"replacement drops 'at most one dominant'",
          "at most one dominant" not in new,
          "the replacement still carries the ceiling")

print("\n=== C3: the replacement is a FLOOR (same-moment), not a deletion ===")
_joined = " ".join(n for _, n in SWAPS)
check("replacement states the same-moment test",
      "SAME moment" in _joined or "one moment together" in _joined
      or "ONE JOB" in _joined,
      "the replacement removed the ceiling without putting a test in its place")
check("replacement keeps a legibility failure mode",
      "DIFFERENT moment" in _joined or "competing" in _joined,
      "nothing now describes what a bad window looks like")

print("\n=== C4: LOUD on a missing anchor (no silent no-op) ===")
_i = SRC.find("window-doctrine arm: anchor missing")
check("a missing anchor RAISES", _i > 0,
      "a swap that cannot find its text would silently no-op")
check("the raise is inside the _dv == 4 branch",
      SRC.rfind("if _dv == 4:", 0, _i) > 0,
      "the guard is not attached to the arm")

print("\n=== C5: INERT at every other variant ===")
# The swap block must be gated. If the gate is absent the control arm carries
# the replacement and the A/B measures nothing.
_blk = SRC.find("for _wd_old, _wd_new in _WINDOW_DOCTRINE_SWAPS:")
_gate = SRC.rfind("if _dv == 4:", 0, _blk)
check("the swap loop is gated behind _dv == 4", _gate > 0 and _blk - _gate < 900,
      "the swap runs unconditionally — every arm gets it")
check("variant 4 is not the default", "_dv = int(density_variant or 0)" in SRC,
      "density_variant no longer defaults to 0")

print("\n=== C6: ZAC'S RULING — ceiling removal AND placement ship together ===")
# The ruling: density is a consequence of correct placement, not a dial. An arm
# that removes the ceiling without supplying placement buys volume without
# composition — the exact failure the ceiling existed to prevent.
_blk = H._WINDOW_ARM_PLACEMENT_BLOCK
check("the arm appends a placement block", len(_blk) > 400)
check("the append is inside the _dv == 4 branch",
      "system_instruction += _WINDOW_ARM_PLACEMENT_BLOCK" in SRC
      and SRC.rfind("if _dv == 4:", 0,
                    SRC.find("system_instruction += _WINDOW_ARM_PLACEMENT_BLOCK")) > 0,
      "placement ships outside the arm — the control would get it too")
for _claim, _needle in (("cards replace the frame", "CARDS REPLACE THE FRAME"),
                        ("text rides the speaker", "TEXT RIDES THE SPEAKER"),
                        ("cutaways layer", "CUTAWAYS ARE THE CORPUS"),
                        ("restraint is a placement", "RESTRAINT IS A PLACEMENT")):
    check(f"  states: {_claim}", _needle in _blk)
# EVIDENCE RIDES THE RULE — validate_deploy pins this house style.
import re as _re
_nums = _re.findall(r"\b\d+ of \d+\b", _blk)
check(f"every rule carries its measurement ({len(_nums)} 'N of M' counts)",
      len(_nums) >= 6,
      "rules without their evidence get cut in a diet and nobody learns why")
# The block SAYS "It is not a target to hit", so a bare substring test for
# "target" fires on the negation. What must be absent is a PRESCRIBED RATE —
# a per-25s figure the model could aim at, which would turn placement back into
# the dial Zac's ruling rejects.
_rate = _re.search(r"\d+(\.\d+)?\s*(per\s*25s|/25s|events?\s*per)", _blk, _re.I)
check("the block prescribes NO density rate (placement, not a dial)",
      _rate is None,
      f"found a rate: {_rate.group(0) if _rate else None} — that is a target")
# Whitespace-tolerant: the block wraps as "It is not a\ntarget to hit."
check("and it says so explicitly",
      _re.search(r"not\s+a\s+target", _blk, _re.I) is not None)

print("\n=== C7: VARIANT 5 — placement only, ceiling INTACT (the separator) ===")
# Variant 4 moved emission the wrong way (emphasis 1.34x / SFX 1.27x up; cards
# 0.74x, cutaways 0.49x, tight overlays 0.24x DOWN). Variant 5 holds the ceiling
# and supplies placement alone, so "the ceiling was not the constraint" can be
# told apart from "placement cannot reach asset-gated families".
check("placement is gated on _dv in (4, 5)", "if _dv in (4, 5):" in SRC,
      "variant 5 does not exist — the separating arm was not built")
_i5 = SRC.find("if _dv in (4, 5):")
_i4 = SRC.find("if _dv == 4:")
check("the DOCTRINE SWAP stays exclusive to variant 4",
      0 < _i4 < _i5,
      "the swap runs for variant 5 too — the arms are not separable")
_swap_i = SRC.find("system_instruction.replace(_wd_old, _wd_new, 1)")
check("the swap sits inside the _dv == 4 block, above the (4,5) guard",
      _i4 < _swap_i < _i5,
      "variant 5 would also remove the ceiling and measure nothing new")
check("placement append is under the (4,5) guard",
      _i5 < SRC.find("system_instruction += _WINDOW_ARM_PLACEMENT_BLOCK"))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
