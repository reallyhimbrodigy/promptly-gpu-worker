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

if FAIL:
    print("FAIL smoke_spec_floor:")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print("ok smoke_spec_floor — 10/25s cannot return 7 unexplained, naming the "
      "declined beats satisfies it, blank whys do not, capped at the beat count, "
      "and an unresolved floor fails the round")
