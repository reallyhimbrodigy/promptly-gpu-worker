#!/usr/bin/env python3
"""SMOKE: one ruling pass, one execution pass — enforced in the dispatch.

MEASURED, round 28 talking_head:
  rule -> rule -> cut -> EXEC -> rule -> EXEC -> inspect -> rule -> EXEC
  -> inspect -> rule -> EXEC          15 turns, 88.0s model, 94.9s render

Four executions and five rulings. The loop is induced by the spec floor: the
shortfall is reported, the agent re-rules to close it, and executes again. But
the floor is satisfiable TWO ways and one is always available — rule to it, or
NAME the declined beats. Re-ruling is the expensive way; naming is free and is
what the check asks for.

Collapsing to one pass removes ~7 redundant turns (~41s of model time at the
measured 5.87s/turn) AND turns four renders into one, which is where the
shared-process saving actually lands.

ENFORCED IN THE DISPATCH. "A capability in the schema WILL be used" — telling a
model not to loop is a preference; refusing the call is a property. And the tool
list is part of the cached prefix, so it cannot be withheld mid-run without a
43k-token cache write.

THE ESCAPE HATCH IS NARROW ON PURPOSE. One repair, for a CONTRACT failure only.
A refusal with no repair path makes a broken first render unfixable, which is
worse than the loop. Shortfalls and quality misses do NOT qualify — letting
those re-execute restores the loop through the back door.
"""
import ast, pathlib, sys, types

import sys
import modal_stub                                         # noqa: E402
modal_stub.install()
import agentic_editor_app as A

src = pathlib.Path(A.__file__).read_text()
fails=[]
def check(l,c,d=""):
    if not c: fails.append(l + (f"  :: {d}" if d else ""))

check("a second execute_plan is REFUSED",
      'led["execute_plan_calls"] > 1' in src and '"refused": "one execution pass"' in src,
      "the gate must be in the dispatch, not the prompt")
# WAS: "the refusal tells the agent how to close the shortfall WITHOUT a
# render". That leg asserted a density remedy — retired by the 2026-09-07
# ruling — and it pointed at shortfall_reasons, a schema field now deleted, so
# the instruction had become unfollowable as well as unwanted.
#
# THE POINT IT WAS MAKING SURVIVES: an unsatisfiable refusal burns the turn
# budget, which is what the shortfall livelock did. A refusal must still name
# what IS available. The difference is that the available path is now the
# repair hatch, which exists, rather than a floor to discharge, which does not.
# ANCHORED ON THIS REFUSAL, NOT ON THE FIRST `what_is_available` IN THE FILE.
# There are now TWO refusals that name what is available — the second EXECUTE
# and the second RULING pass — and splitting on the bare field name landed on
# whichever came first. Both say "repair_permitted" and neither says
# "shortfall", so deleting the field from the refusal this smoke exists to
# guard left all three legs GREEN. The execute refusal's own line is unique.
_anchor = '"refused": "one execution pass"'
check("the execute refusal is uniquely locatable",
      src.count(_anchor) == 1,
      "%d copies — a leg anchored on a repeated literal guards nothing"
      % src.count(_anchor))
_refusal = src.split(_anchor)[1][:1500] if src.count(_anchor) == 1 else ""
# AND THE WINDOW MUST NOT BLEED INTO THE NEXT REFUSAL. If it reached the
# second-RULING refusal, "repair_permitted" would be satisfied by the wrong
# one and the leg would be back where it started.
check("the window covers this refusal only",
      _refusal and '"refused": "one ruling pass"' not in _refusal,
      "the window ran past into the second-ruling refusal")
check("the refusal names what is available rather than only saying no",
      '"what_is_available"' in _refusal,
      "a bare refusal costs a turn and teaches the agent nothing")
check("and it points at the repair hatch, which is real",
      "repair_permitted" in _refusal,
      "naming a path that does not exist is worse than naming none")
check("the refusal names NO density remedy",
      "shortfall" not in _refusal,
      "the rubric grades; it must not reappear as the thing a refusal asks for")
check("the refusal is counted, not silent",
      'led["refused_second_execute"]' in src,
      "a gate whose firing nobody can read is not a gate")

# ── the hatch, and its narrowness ──────────────────────────────────────────
check("one repair is permitted", '_exec_repair_ok' in src and '_exec_repair_used' in src)
check("the hatch opens ONLY on a contract failure",
      '_cv_now = _contract_violations(led)' in src
      and 'bool(_cv_now)' in src,
      "opening it on any failure would restore the loop")
check("the repair is single-use",
      'not led.get("_exec_repair_used")' in src,
      "an unbounded hatch is not a hatch")

# ── the gate is on the DISPATCH branch, not merely mentioned ───────────────
tree = ast.parse(src)
found = False
for n in ast.walk(tree):
    if isinstance(n, ast.Compare) and "execute_plan_calls" in ast.dump(n):
        found = True
check("the count is compared in real code, not only in a comment", found,
      "a check that reads source cannot tell code from string content — this "
      "lane has shipped that exact bug")

# ── PRINTED, NOT MERELY LEDGERED ──────────────────────────────────────────
# Round 29 could not answer whether the gate fired: the counter went to the
# ledger and nowhere else, and tool results do not reach the log. Shipped ONE
# COMMIT AFTER the commit that fixed exactly this for placement_effects and
# quoted the law in its own message. Ledgering a signal is not observing it.
check("the execution-pass counters are PRINTED",
      "EXECUTION PASSES:" in src,
      "a gate whose firing leaves no trace cannot be read on the round it runs")
check("a contested refusal is called out by name",
      "CONTESTED" in src,
      "the failure mode of this change is the agent retrying the refused call, "
      "and it has to be visible on the first round rather than inferred from "
      "a cost number three rounds later")

if fails:
    print(f"ONE-EXECUTION-PASS: {len(fails)} FAILED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print("ONE-EXECUTION-PASS: PASS")
