"""SMOKE — the spec arithmetic, as a GRADING instrument. It demands nothing.

WAS smoke_spec_floor.py. Zac's ruling (2026-09-07): the reference rates are a
grading instrument only. They must never reach the agent as a target, appear in
the prompt, or be enforced as a floor at ruling time. The agent places components
where they fit; the rubric asks afterwards whether the result is in the plausible
range. A run that places two zooms because two moments deserved them is correct,
and a rubric that calls it short is the rubric's problem.

WHAT THAT DID TO THIS FILE. Every leg that asserted the floor BINDS is gone —
the contract failure, the shortfall_reasons exit, the ask-once bound, the
end-of-run escalation. What survives is the arithmetic, and it survives because
the grading question is still worth computing: implied counts, the beat-count
cap, the absence of a max(1, ...) floor, and the over/under/absent directions.

The measurements that produced this arithmetic are still the reason it is shaped
this way, so they are kept as the record of WHY, not as a demand:
  round 15/16   identical fixture and brief, text 116% then 81% of reference
  round 20      four of five no-speech fixtures placed ONE family and called it
                an edit — which is why `over` is measured, not only `under`
  round 21      0.2/25s over 20s is 0.16 placements and the answer is ZERO;
                max(1, ...) turned "subtle overlays only" into "at least one"
Reading a swing is the point. Refusing over it is what was removed.

The companion is smoke_rubric_grades_only.py, which asserts the other half: that
none of this reaches the agent.
"""
import ast
import sys

FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)

SRC = open("agentic_editor_app.py", encoding="utf-8").read()
TREE = ast.parse(SRC)


# THE SHIPPED FUNCTION, EXECUTED — not a replay of it.
#
# The first version of this smoke defined its own copy of the arithmetic. Two
# mutations to the real code passed clean, because the test was never reading
# the real code: `if _have + _named_gap < _implied:` became `if False:` and the
# replay did not care. The source-level guards I added alongside were substrings
# satisfied by OTHER occurrences — `_named_gap` still appeared in its assignment,
# `"shortfall_reasons"` still appeared in a setdefault. Eleventh instance of a
# check reading around the thing it is checking.
#
# spec_shortfall is now pure and module-level for exactly this reason.
_ns = {}
_fn = next((n for n in TREE.body
            if isinstance(n, ast.FunctionDef) and n.name == "spec_shortfall"), None)
if _fn is None:
    print("FAIL smoke_spec_grading:")
    print("  - spec_shortfall is not defined at module level — the floor "
          "arithmetic is inline again and can only be replayed, not tested")
    sys.exit(1)
exec(compile(ast.Module([_fn], []), "<s>", "exec"), _ns)
shortfall = _ns["spec_shortfall"]


# ── THE ASK, EXACTLY: text resolved to 10/25s cannot return 7 unexplained ──
# 38.5s at 10/25s implies 15, capped at the 11 beats the source has.
s = shortfall({"text": 10.0}, {"text": 7}, n_beats=11, dur_s=38.5)
ok("text" in s,
   "a brief resolving text to 10/25s came back with 7 rulings and NO shortfall "
   "— the floor does not bind, which is round 16 exactly")
ok(s["text"]["implied"] == 11,
   f"implied {s['text']['implied']}, expected 11 (15 capped at the beat count) "
   f"— an uncapped target is unsatisfiable and livelocks")
ok(s["text"]["still_unexplained"] == 4,
   f"still_unexplained {s['text'].get('still_unexplained')}, expected 4")

# ── NO EXCUSE CHANNEL ────────────────────────────────────────────────────
# The `reasons` argument is gone with the demand. Three legs lived here — naming
# the declined beats satisfied the floor, partial naming left the rest, a blank
# `why` was not a reason. All three tested how an agent DISCHARGES a demand, and
# there is no demand.
_sig = list(__import__("inspect").signature(shortfall).parameters)
ok("reasons" not in _sig,
   f"spec_shortfall still takes an excuse channel: {_sig} — passing it empty "
   f"forever is worse than removing it, because the next reader will fill it")

# ── ruling TO the floor satisfies it ─────────────────────────────────────
ok(shortfall({"text": 10.0}, {"text": 11}, 11, 38.5) == {},
   "ruling to the floor still reported a shortfall")

# ── the cap is load-bearing: never demand more than the source can hold ──
# A 4-beat source ruled 4 is SATISFIED: implied caps at the beat count, so the
# floor can never demand a placement the source has nowhere to put.
ok(shortfall({"text": 10.0}, {"text": 4}, n_beats=4, dur_s=38.5) == {},
   "a 4-beat source ruled 4 still reported a shortfall — the cap is not "
   "holding, and an uncapped floor is unsatisfiable by construction")
# and one short of the cap IS reported, so the cap did not silently disable it
ok(shortfall({"text": 10.0}, {"text": 3}, n_beats=4, dur_s=38.5)
   .get("text", {}).get("still_unexplained") == 1,
   "capping the target also stopped it reporting a real gap — the cap must "
   "bound the demand, not switch the check off")

# ── AND IT MUST FAIL NOTHING ─────────────────────────────────────────────
# THE INVERSION. This block asserted the opposite until the ruling: that an
# unresolved shortfall was a CONTRACT failure, and that the schema carried a
# shortfall_reasons field so the demand had a second exit. Both are now defects.
_cf = next(n for n in TREE.body
           if isinstance(n, ast.Assign)
           and getattr(n.targets[0], "id", "") == "CONTRACT_FAILURES")
_S = ast.literal_eval(_cf.value.args[0])
for _k in ("spec_shortfall_unresolved", "spec_family_built_zero",
           "spec_targets_all_zero", "spec_shortfall_accepted"):
    ok(_k not in _S,
       f"{_k} still fails the round — density below a reference rate is an "
       f"observation about the edit, not a defect in it")
# Non-vacuous: the set must still carry the failures that are about the OUTPUT.
ok({"wrong_resolution", "no_output", "placement_inert"} <= _S,
   f"CONTRACT_FAILURES has been emptied, not narrowed: {sorted(_S)}")

# ── STILL CALLED, AND STILL RECORDED ─────────────────────────────────────
# Retiring the demand must not retire the measurement. A grading instrument
# nobody calls and nobody records is the "ledgering is not observing" defect
# wearing a rubric's clothes.
_dispatch_calls = [n for n in ast.walk(TREE)
                   if isinstance(n, ast.Call)
                   and getattr(n.func, "id", "") == "spec_shortfall"]
ok(len(_dispatch_calls) >= 1,
   "nothing CALLS spec_shortfall — the pure function exists and the grading "
   "question is never actually asked")
ok('led["spec_shortfall"] = _short' in SRC,
   "the grade is computed and dropped on the floor")
ok("FAMILY MIX" in SRC,
   "the density is not REPORTED anywhere — a grade nobody reads is not a grade")

# ══════════════════════════════════════════════════════════════════════════
# THE SPEC IS A MIX, NOT A FLOOR PER FAMILY.
#
# MEASURED, round 20: four of five fixtures came back [zoom=3], [sfx=2 zoom=3],
# [zoom=1], [zoom=1] — every no-speech fixture placing one family and calling it
# an edit, with all five green. Only the UNDER direction was ever checked, so a
# run that placed 3 zooms against an implied 1 and ZERO text against an implied
# 3 satisfied the check by overshooting the family it found easy.
# ══════════════════════════════════════════════════════════════════════════
# the exact round-20 screen_recording shape
_r20 = shortfall({"text": 4.0, "zoom": 0.35}, {"text": 0, "zoom": 3}, 4, 20.0)
ok(_r20.get("text", {}).get("direction") == "absent",
   f"text placed 0 against an implied 3 was not flagged: {_r20.get('text')}")
ok(_r20.get("zoom", {}).get("direction") == "over",
   f"zoom placed 3 against an implied 1 was not flagged — overshooting the "
   f"easy family is how a run satisfies a one-sided check: {_r20.get('zoom')}")
# a run that MATCHES its mix says nothing
ok(shortfall({"text": 4.0, "zoom": 0.35}, {"text": 3, "zoom": 1}, 4, 20.0) == {},
   "a run that hit its own distribution was reported as a miss")
# UNDER stays strict — any unexplained gap. Adding the over direction must not
# widen the check that already worked: a run one short of every family passing
# is the loosening this repo has been bitten by.
ok(shortfall({"text": 4.0}, {"text": 2}, 4, 20.0).get("text", {}).get("direction") == "under",
   "one under the implied count is no longer reported — the over direction was "
   "added by loosening the under one")
# ONE over is rounding, not a miss — and with the max(1,...) floor gone the
# implied count here is genuinely 0, so "one over" is one placement, not two.
# The old fixture used 2 because the floor forced implied to 1; it now reads as
# a real 2x overshoot and is correctly flagged.
ok(shortfall({"zoom": 0.35}, {"zoom": 1}, 6, 20.0) == {},
   "a single placement against an implied 0 was flagged — that is rounding, "
   "not the run substituting an easy family")
ok(shortfall({"zoom": 0.35}, {"zoom": 2}, 6, 20.0).get("zoom", {}).get("direction") == "over",
   "two placements against an implied 0 were NOT flagged")
# two or more over IS a miss
ok(shortfall({"zoom": 0.35}, {"zoom": 3}, 6, 20.0).get("zoom", {}).get("direction") == "over",
   "a 3x overshoot was not flagged")
# ZERO is always a miss even when the implied count is 1 — the case a
# threshold-only rule lets through
ok(shortfall({"sfx": 0.82}, {"sfx": 0}, 6, 20.0).get("sfx", {}).get("direction") == "absent",
   "placing NOTHING for a family the spec asked for passed, because 1 - 0 < 2")
# NO LEG HERE for "naming the gap excuses the absence". An absence is now
# REPORTED, full stop; there is nothing to excuse it to.

# ══════════════════════════════════════════════════════════════════════════
# A RATE IS A RATE — NO max(1, ...) FLOOR.
#
# 0.2/25s over a 20s source is 0.16 placements and the correct answer is ZERO.
# Forcing it to one made the gate invent work the brief never asked for:
# "subtle overlays only" became "at least one overlay", and screen_recording
# spent rounds 19, 20 and 21 declining a target it should never have been given,
# with per-beat reasoning that was sound every time.
#
# It also turned accept_shortfall into a ROUTINE exit rather than the exception
# it was meant to be — the agent had to argue its way out of a demand the
# arithmetic invented.
# ══════════════════════════════════════════════════════════════════════════
# the exact round-21 screen_recording spec: three small rates, nothing placed
ok(shortfall({"text": 0.2, "card": 0.1, "zoom": 0.2},
             {"text": 0, "card": 0, "zoom": 0}, 4, 20.0) == {},
   "small rates still demand a placement — max(1, ...) is back, and the gate is "
   "inventing work the brief did not ask for")
# a rate that genuinely implies one still binds
ok(shortfall({"sfx": 0.82}, {"sfx": 0}, 6, 20.0).get("sfx", {}).get("implied") == 1,
   "0.82/25s over 20s rounds to 1 and must still be demanded — removing the "
   "floor must not round every small rate away")
# a real ask still binds hard
_ra = shortfall({"text": 4.0}, {"text": 0}, 4, 20.0)
ok(_ra.get("text", {}).get("implied") == 3 and _ra["text"]["direction"] == "absent",
   f"text at 4/25s over 20s must imply 3: {_ra.get('text')}")
# OVERSHOOT IS SHARPER, not weaker: 3 placed against a real implied 0
_ov = shortfall({"zoom": 0.35}, {"zoom": 3}, 6, 20.0)
ok(_ov.get("zoom", {}).get("implied") == 0 and _ov["zoom"]["direction"] == "over",
   f"a family placed 3 times against an implied ZERO must still be flagged: {_ov.get('zoom')}")

# ══════════════════════════════════════════════════════════════════════════
# RETIRED WITH THE FLOOR: the ask-once bound and the end-of-run escalation.
#
# Both were real fixes to real defects — round 19's bounded ask erased the very
# record it was bounding, and round 22 finished with a shortfall outstanding and
# scored viol=[]. Both defects were about a DEMAND that nagged and a demand that
# could be dodged. With nothing demanded there is nothing to nag about and
# nothing to dodge, so the mechanisms are gone and their tests with them.
#
# Kept as one assertion, because the machinery leaving must actually leave:
# READ IDENTIFIERS AND STRING LITERALS, NOT THE FILE TEXT. The first version
# greped SRC and failed on the COMMENT directly above the pop — the one that
# explains why shortfall_told was a defect. Tenth instance of a check reading
# around the thing it checks, and the second one in this file's own history.
_LIVE = ({n.id for n in ast.walk(TREE) if isinstance(n, ast.Name)}
         | {n.attr for n in ast.walk(TREE) if isinstance(n, ast.Attribute)}
         | {n.value for n in ast.walk(TREE)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)})
ok("shortfall_told" not in _LIVE,
   "the ask-once bookkeeping is still in the dispatch — it exists only to stop "
   "a demand nagging, and there is no demand")
# NOT asserted: that led.pop("spec_shortfall") is gone. My first version did,
# and it was wrong — the pop is the GRADE being kept current when the latest
# ruling has no shortfall, which is correct bookkeeping. What made it a defect
# was sharing a variable with the ask; the ask is what had to go.
ok(SRC.count('led.pop("spec_shortfall", None)') == 1,
   "the grade is cleared in more than one place")
ok("SPEC_SHORTFALL" not in _LIVE and "fix_shortfall" not in _LIVE,
   "the shortfall is still returned to the agent — that is the demand itself, "
   "whatever the surrounding words say")

if FAIL:
    print("FAIL smoke_spec_grading:")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print("ok smoke_spec_grading — the arithmetic grades (implied counts capped at "
      "the beat count, no max(1,...) floor, over/under/absent all measured), it "
      "is called and recorded, and it demands nothing of the agent")
