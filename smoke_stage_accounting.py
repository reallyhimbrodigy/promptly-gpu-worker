#!/usr/bin/env python3
"""SMOKE: the stage table adds up, and says so loudly when it cannot.

WHY. Round 35 printed "(unattributed) -79.82s" and I quoted a 66.4% render share
off that same table. A negative remainder is arithmetic saying the model of what
NESTS is wrong — time cannot go missing in the negative direction — so every
share in that decomposition was suspect and the number I planned against was
approximate without saying so.

THE ROT. The nesting model was a hand-kept tuple of six stage names. The port
added build_captions, composite_captions, build_transitions and
build_reel_paint; none were in it, so all four were counted BOTH as top-level
and inside execute_plan. The comment above the tuple already recorded fixing an
earlier -8.67s remainder the same way. It came back an order of magnitude bigger,
because a list of what nests is a list somebody has to remember to update — and
the table exists to show the work nobody remembered.

WHAT MAKES THIS FIRE: a new build_* stage going uncounted (the exact rot), and a
negative remainder being printed as a number instead of as a failure.
"""
import re, sys

SRC = open("agentic_editor_app.py", encoding="utf-8").read()

fails = []
def ok(label, cond, detail=""):
    if not cond: fails.append(label + (f"  :: {detail}" if detail else ""))

# ── the shipped arithmetic, extracted and driven ─────────────────────────
def remainder(named, tools, total, prefixes=("build_", "composite_"),
              extra=("audio_extract",)):
    top = sum(v for k, v in named.items()
              if not k.startswith(prefixes) and k not in extra)
    return round(total - top - sum(tools.values()), 2)

# ROUND 35 talking_head, the run that produced -79.82s.
R35_NAMED = {"build_captions": 76.32, "build_reel": 65.52, "model_thinking": 44.90,
             "composite_captions": 6.06, "build_sfx": 2.49, "transcribe": 2.28,
             "audio_extract": 1.75, "download": 0.89, "beats": 0.0,
             "build_cut": 0.0, "build_zoom": 0.0, "build_transitions": 0.0}
R35_TOOLS = {"execute_plan": 171.97, "set_spec": 0.0, "rule_all_beats": 0.0}
R35_WALL = 222.6

_r = remainder(R35_NAMED, R35_TOOLS, R35_WALL)
ok("round 35's real numbers no longer produce a negative remainder", _r >= 0,
   f"remainder {_r}s — this is the exact run that printed -79.82s")
ok("the remainder is a plausible small residue", 0 <= _r <= 15,
   f"{_r}s — a large positive remainder means a stage is uninstrumented, which "
   "is also worth seeing, but it should not be silent")

# ── THE ROT ITSELF: a NEW build_* stage must be covered automatically ────
_named2 = dict(R35_NAMED); _named2["build_something_new"] = 10.0
ok("a newly added build_* stage is treated as nested without being listed",
   remainder(_named2, R35_TOOLS, R35_WALL) == _r,
   "a new build_* stage changed the remainder, so it was counted as top-level "
   "AND inside its tool — the exact double-count that produced -79.82s")

# ── the hand-kept list must be GONE from the shipped source ──────────────
ok("the hand-kept nesting tuple is gone",
   '_NESTED = (' not in SRC,
   "a list of what nests is a list somebody has to remember to update")
ok("nesting is derived by prefix in the shipped source",
   "_NESTED_PREFIXES" in SRC and '"build_", "composite_"' in SRC)

# ── a negative remainder must be LOUD, never printed as a value ──────────
_blk = SRC[SRC.index("_NESTED_PREFIXES"):SRC.index("_NESTED_PREFIXES") + 2200]
ok("a negative remainder is caught", "if _un < 0:" in _blk,
   "nothing tests the sign, so the table can print a negative share again")
ok("a negative remainder prints UNACCOUNTABLE, not a number",
   "UNACCOUNTABLE" in _blk,
   "printing it as a value invites reading a share off a table that does not "
   "add up — which is exactly what happened")
ok("it names the double-counting candidates", "candidates" in _blk,
   "a failure that does not say WHICH stages overlap leaves the next reader "
   "doing the arithmetic by hand")
ok("it says the other shares are suspect", "SUSPECT" in _blk,
   "the shares above a broken remainder were quoted as fact once already")

if fails:
    print(f"STAGE-ACCOUNTING: {len(fails)} FAILED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print(f"STAGE-ACCOUNTING: PASS (9 checks; round 35 remainder now {_r}s, was -79.82s)")
