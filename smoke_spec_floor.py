"""SMOKE — the resolved density is a FLOOR: rule to it, or name the gap per beat.

THE DEFECT. set_spec resolves a brief to per-family rates, execute_plan computed
the shortfall, reported it ONCE, and then proceeded — recording
spec_shortfall_unresolved as a ledger note with no power. So a brief resolving
text to 10/25s could come back with 7 and score GREEN.

MEASURED, and this is why it matters more than it sounds: on an identical
fixture and brief, text ran 116% of reference in round 15 and 81% in round 16,
sfx 102% then 0%, zoom 240% then 0%. The harness built everything ruled in both.
The swing is in what gets RULED, and nothing bound it.

SATISFIED TWO WAYS, one of which is always available: rule to the floor, or name
the declined beats in shortfall_reasons. Naming is always possible, so this can
never become the unsatisfiable refusal that burned two 24-turn budgets chasing a
rate the source could not hold.
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
    print("FAIL smoke_spec_floor:")
    print("  - spec_shortfall is not defined at module level — the floor "
          "arithmetic is inline again and can only be replayed, not tested")
    sys.exit(1)
exec(compile(ast.Module([_fn], []), "<s>", "exec"), _ns)
shortfall = _ns["spec_shortfall"]


# ── THE ASK, EXACTLY: text resolved to 10/25s cannot return 7 unexplained ──
# 38.5s at 10/25s implies 15, capped at the 11 beats the source has.
s = shortfall({"text": 10.0}, {"text": 7}, [], n_beats=11, dur_s=38.5)
ok("text" in s,
   "a brief resolving text to 10/25s came back with 7 rulings and NO shortfall "
   "— the floor does not bind, which is round 16 exactly")
ok(s["text"]["implied"] == 11,
   f"implied {s['text']['implied']}, expected 11 (15 capped at the beat count) "
   f"— an uncapped target is unsatisfiable and livelocks")
ok(s["text"]["still_unexplained"] == 4,
   f"still_unexplained {s['text'].get('still_unexplained')}, expected 4")

# ── NAMING THE GAP SATISFIES IT ──────────────────────────────────────────
reasons = [{"beat": b, "family": "text", "why": "no claim to carry"}
           for b in (3, 5, 7, 9)]
ok(shortfall({"text": 10.0}, {"text": 7}, reasons, 11, 38.5) == {},
   "naming the four declined beats did not satisfy the floor — if naming does "
   "not work the refusal is unsatisfiable, and an unsatisfiable refusal is the "
   "livelock that burned two 24-turn budgets")

# ── partial naming leaves the rest unexplained ───────────────────────────
s2 = shortfall({"text": 10.0}, {"text": 7}, reasons[:2], 11, 38.5)
ok(s2.get("text", {}).get("still_unexplained") == 2,
   f"naming 2 of 4 gaps left {s2.get('text', {}).get('still_unexplained')} "
   f"unexplained, expected 2")

# ── an EMPTY reason is not a reason ──────────────────────────────────────
ok(shortfall({"text": 10.0}, {"text": 7},
             [{"beat": b, "family": "text", "why": ""} for b in (3, 5, 7, 9)],
             11, 38.5).get("text", {}).get("still_unexplained") == 4,
   "blank whys satisfied the floor — a gap named without a reason is not named")

# ── ruling TO the floor satisfies it ─────────────────────────────────────
ok(shortfall({"text": 10.0}, {"text": 11}, [], 11, 38.5) == {},
   "ruling to the floor still reported a shortfall")

# ── the cap is load-bearing: never demand more than the source can hold ──
# A 4-beat source ruled 4 is SATISFIED: implied caps at the beat count, so the
# floor can never demand a placement the source has nowhere to put.
ok(shortfall({"text": 10.0}, {"text": 4}, [], n_beats=4, dur_s=38.5) == {},
   "a 4-beat source ruled 4 still reported a shortfall — the cap is not "
   "holding, and an uncapped floor is unsatisfiable by construction")
# and one short of the cap IS reported, so the cap did not silently disable it
ok(shortfall({"text": 10.0}, {"text": 3}, [], n_beats=4, dur_s=38.5)
   .get("text", {}).get("still_unexplained") == 1,
   "capping the target also stopped it reporting a real gap — the cap must "
   "bound the demand, not switch the check off")

# ── AND IT MUST FAIL THE ROUND ───────────────────────────────────────────
_cf = next(n for n in TREE.body
           if isinstance(n, ast.Assign)
           and getattr(n.targets[0], "id", "") == "CONTRACT_FAILURES")
_S = ast.literal_eval(_cf.value.args[0])
ok("spec_shortfall_unresolved" in _S,
   "an unresolved floor is not a CONTRACT failure — it stays a ledger note with "
   "no power, which is what let round 16 score green at 81% of a 10/25s target")

ok('"shortfall_reasons"' in SRC,
   "the schema has no per-beat gap field, so the only way to satisfy the floor "
   "is to rule to it — that is a refusal with one exit, not two")
# The behavioural assertions above already prove named gaps are credited — they
# run the shipped function. A substring guard here would only re-introduce the
# weakness this smoke was rewritten to remove.
_dispatch_calls = [n for n in ast.walk(TREE)
                   if isinstance(n, ast.Call)
                   and getattr(n.func, "id", "") == "spec_shortfall"]
ok(len(_dispatch_calls) >= 1,
   "nothing CALLS spec_shortfall — the pure function exists and the dispatch "
   "computes its own copy, so the tested code is not the running code")

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
_r20 = shortfall({"text": 4.0, "zoom": 0.35}, {"text": 0, "zoom": 3}, [], 4, 20.0)
ok(_r20.get("text", {}).get("direction") == "absent",
   f"text placed 0 against an implied 3 was not flagged: {_r20.get('text')}")
ok(_r20.get("zoom", {}).get("direction") == "over",
   f"zoom placed 3 against an implied 1 was not flagged — overshooting the "
   f"easy family is how a run satisfies a one-sided check: {_r20.get('zoom')}")
# a run that MATCHES its mix says nothing
ok(shortfall({"text": 4.0, "zoom": 0.35}, {"text": 3, "zoom": 1}, [], 4, 20.0) == {},
   "a run that hit its own distribution was reported as a miss")
# UNDER stays strict — any unexplained gap. Adding the over direction must not
# widen the check that already worked: a run one short of every family passing
# is the loosening this repo has been bitten by.
ok(shortfall({"text": 4.0}, {"text": 2}, [], 4, 20.0).get("text", {}).get("direction") == "under",
   "one under the implied count is no longer reported — the over direction was "
   "added by loosening the under one")
# ONE over is rounding, not a miss — and with the max(1,...) floor gone the
# implied count here is genuinely 0, so "one over" is one placement, not two.
# The old fixture used 2 because the floor forced implied to 1; it now reads as
# a real 2x overshoot and is correctly flagged.
ok(shortfall({"zoom": 0.35}, {"zoom": 1}, [], 6, 20.0) == {},
   "a single placement against an implied 0 was flagged — that is rounding, "
   "not the run substituting an easy family")
ok(shortfall({"zoom": 0.35}, {"zoom": 2}, [], 6, 20.0).get("zoom", {}).get("direction") == "over",
   "two placements against an implied 0 were NOT flagged")
# two or more over IS a miss
ok(shortfall({"zoom": 0.35}, {"zoom": 3}, [], 6, 20.0).get("zoom", {}).get("direction") == "over",
   "a 3x overshoot was not flagged")
# ZERO is always a miss even when the implied count is 1 — the case a
# threshold-only rule lets through
ok(shortfall({"sfx": 0.82}, {"sfx": 0}, [], 6, 20.0).get("sfx", {}).get("direction") == "absent",
   "placing NOTHING for a family the spec asked for passed, because 1 - 0 < 2")
# and naming the gap still excuses an absence
ok(shortfall({"sfx": 0.82}, {"sfx": 0},
             [{"beat": 1, "family": "sfx", "why": "no moment lands"}], 6, 20.0) == {},
   "a named gap no longer satisfies the mix — naming must stay a real exit")

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
             {"text": 0, "card": 0, "zoom": 0}, [], 4, 20.0) == {},
   "small rates still demand a placement — max(1, ...) is back, and the gate is "
   "inventing work the brief did not ask for")
# a rate that genuinely implies one still binds
ok(shortfall({"sfx": 0.82}, {"sfx": 0}, [], 6, 20.0).get("sfx", {}).get("implied") == 1,
   "0.82/25s over 20s rounds to 1 and must still be demanded — removing the "
   "floor must not round every small rate away")
# a real ask still binds hard
_ra = shortfall({"text": 4.0}, {"text": 0}, [], 4, 20.0)
ok(_ra.get("text", {}).get("implied") == 3 and _ra["text"]["direction"] == "absent",
   f"text at 4/25s over 20s must imply 3: {_ra.get('text')}")
# OVERSHOOT IS SHARPER, not weaker: 3 placed against a real implied 0
_ov = shortfall({"zoom": 0.35}, {"zoom": 3}, [], 6, 20.0)
ok(_ov.get("zoom", {}).get("implied") == 0 and _ov["zoom"]["direction"] == "over",
   f"a family placed 3 times against an implied ZERO must still be flagged: {_ov.get('zoom')}")

# ══════════════════════════════════════════════════════════════════════════
# ASKING IS BOUNDED; RECORDING IS NOT.
#
# MEASURED, round 19 screen_recording: the agent set text=0.4 and zoom=0.2 per
# 25s, ruled all four beats `none`, built NOTHING — and the round passed this
# leg. spec_family_built_zero fired four times (a warning) while
# spec_shortfall_unresolved (the CONTRACT failure) never fired at all.
#
# Because they were the same variable. The agent is told once, shortfall_told
# fills, and the next rule_all_beats hit `else: led.pop("spec_shortfall")` —
# so execute_plan saw no shortfall. The bound erased the record it was bounding,
# and the only check with the power to fail the round was cleared by the
# mechanism meant to stop it nagging.
# ══════════════════════════════════════════════════════════════════════════
def replay(short_by_call):
    """Replay the shipped bookkeeping across successive rule_all_beats calls."""
    led, told = {}, set()
    seen_asks = []
    for short in short_by_call:
        new_short = {k: v for k, v in short.items() if k not in told}
        told |= set(short)
        if short:
            led["spec_shortfall"] = short
        else:
            led.pop("spec_shortfall", None)
        seen_asks.append(bool(short and new_short))
    return led, seen_asks

SHORT = {"text": {"implied": 1, "ruled": 0}}

# the round-19 sequence: shortfall present on both calls, agent never closes it
led, asks = replay([SHORT, SHORT])
ok(led.get("spec_shortfall") is not None,
   "the shortfall was CLEARED on the second call merely because the agent had "
   "already been told — execute_plan then sees nothing and "
   "spec_shortfall_unresolved can never fire, which is round 19 exactly")
ok(asks == [True, False],
   f"asking is not bounded: {asks} — the agent must be told once, not every call")

# resolved -> cleared. Being told is not resolving; ruling up IS.
led2, asks2 = replay([SHORT, {}])
ok(led2.get("spec_shortfall") is None,
   "a shortfall the agent actually CLOSED was still recorded — the contract "
   "would fail a run that met its own floor")

# three calls, still unresolved, still recorded and still asked only once
led3, asks3 = replay([SHORT, SHORT, SHORT])
ok(led3.get("spec_shortfall") is not None and asks3 == [True, False, False],
   f"over three calls: recorded={led3.get('spec_shortfall') is not None} asks={asks3}")

# and the shipped source must not re-couple them
ok(SRC.count('led.pop("spec_shortfall", None)') == 1,
   "spec_shortfall is popped in more than one place — the bounded ASK is "
   "clearing the persistent RECORD again")
_pi = SRC.index('if _short:\n                    led["spec_shortfall"] = _short')
_ai = SRC.index('out["SPEC_SHORTFALL"] = _new_short')
ok(_pi < _ai, "the record is written after the ask is decided")

# ── AN OUTSTANDING SHORTFALL ESCALATES AT END OF RUN ──────────────────────
# MEASURED, round 22: music finished with spec_shortfall outstanding on sfx and
# pet_video on sfx+zoom, and BOTH scored viol=[]. The escalation lived inside
# execute_plan — report once, fail on the NEXT call — so a shortfall recorded by
# a rule_all_beats that ran AFTER the last execute_plan was never escalated. The
# record was right; nothing read it.
_cfn = next((n for n in TREE.body
             if isinstance(n, ast.FunctionDef) and n.name == "_contract_violations"), None)
ok(_cfn is not None, "_contract_violations is gone")
if _cfn:
    _cns = {"CONTRACT_FAILURES": _S}
    exec(compile(ast.Module([_cfn], []), "<s>", "exec"), _cns)
    _cv = _cns["_contract_violations"]
    _ok_final = {"exists": True, "width": 1080, "height": 1920, "audio": True}
    _v = _cv({"failures": [], "final_inspect": _ok_final,
              "spec_shortfall": {"sfx": {"direction": "absent"}}})
    ok(any("spec_shortfall_unresolved" in x for x in _v),
       "an outstanding shortfall did not become a contract violation at end of "
       "run — it can still be dodged by never calling execute_plan again, which "
       "is round 22 exactly")
    _v2 = _cv({"failures": [], "final_inspect": _ok_final,
               "spec_shortfall": {"sfx": {"direction": "absent"},
                                  "zoom": {"direction": "over"}}})
    ok(any("zoom over" in x for x in _v2),
       f"the direction is not carried into the violation: {_v2}")
    ok(_cv({"failures": [], "final_inspect": _ok_final}) == [],
       "a run that MET its spec was reported as violating it")

if FAIL:
    print("FAIL smoke_spec_floor:")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print("ok smoke_spec_floor — 10/25s cannot return 7 unexplained, naming the "
      "declined beats satisfies it, blank whys do not, capped at the beat count, "
      "and an unresolved floor fails the round")
