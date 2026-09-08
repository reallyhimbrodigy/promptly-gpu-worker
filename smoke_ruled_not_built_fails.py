#!/usr/bin/env python3
"""SMOKE: a component the agent ruled and the pipeline dropped fails the round.

ROUND 40 SCORED "all five green" — the first green round — while losing:
    card: ruled 3, built 0     (foreign props: heroNumber where StatCard wants value)
    zoom: ruled 1, built 0     (404 downloading the source)
    sfx:  ruled 3, built 2
The refusals were CORRECT — refusing beats rendering a blank card — but the
refusal emitted names that could not fail a round, so the loss scored green and a
human reading a log line was the only thing that caught it.

NOT THE DENSITY RUBRIC RETURNING. Placing FEWER components is the agent's call
and stays green; that ruling stands and this check must not resurrect it. This
fires only when the agent DID rule something and the pipeline dropped it — plan
and output disagreeing, which is a different claim from a rate being missed.

AND THE REASON TRAVELS. Round 40 lost a zoom to a 404 (pipeline fault) and cards
to foreign props (agent fault) under the SAME NAME, with the violation text
carrying neither. One number, two opposite diagnoses.
"""
import ast
import re
import sys

SRC = open("agentic_editor_app.py", encoding="utf-8").read()
TREE = ast.parse(SRC)
fails = []


def ok(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))


# ── it must be able to fail a round ───────────────────────────────────────
failing = None
for n in TREE.body:
    if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "CONTRACT_FAILURES":
        v = n.value
        failing = ast.literal_eval(v.args[0] if isinstance(v, ast.Call) and v.args else v)
ok("CONTRACT_FAILURES is readable", failing is not None)
ok("ruled_not_built can fail a round", failing and "ruled_not_built" in failing,
   "the agent ruled a component, the pipeline dropped it, and the round is green")

# ── the density ruling must NOT be back ───────────────────────────────────
for banned in ("spec_shortfall_unresolved", "spec_family_built_zero"):
    ok(f"{banned} is NOT a failure", failing is not None and banned not in failing,
       "placing fewer components is the agent's call — the rates grade, they do "
       "not instruct, and this check must not resurrect that")

# ── the reason must travel with the violation ─────────────────────────────
call = None
for n in ast.walk(TREE):
    if (isinstance(n, ast.Call) and getattr(n.func, "id", "") == "fail"
            and n.args and isinstance(n.args[0], ast.Constant)
            and n.args[0].value == "ruled_not_built"):
        call = n
ok("something emits ruled_not_built", call is not None)
if call is not None:
    # THE REASON MUST BE INTERPOLATED, NOT MERELY MENTIONED.
    #
    # The first version of this leg read `"_why" in ast.dump(call)` and PASSED
    # against a mutant that removed the reason from the message while leaving
    # `_why` in the surrounding condition. A presence test is satisfied by the
    # variable being named anywhere in the call — which is exactly the substring
    # trap this repo keeps paying for. So: walk the f-strings in the arguments
    # and require _why inside a FormattedValue, which is the only construct that
    # actually puts its VALUE in the text.
    _interpolated = any(
        isinstance(fv, ast.FormattedValue)
        and any(getattr(nm, "id", "") == "_why" for nm in ast.walk(fv.value))
        for a in call.args for js in ast.walk(a)
        if isinstance(js, ast.JoinedStr) for fv in js.values)
    ok("the violation carries the skip reason", _interpolated,
       "round 40 lost a zoom to a 404 (pipeline fault) and cards to foreign "
       "props (agent fault) under this one name; without the reason the next "
       "reader gets one number and two opposite diagnoses")
    ok("a MISSING reason is stated, not silently omitted",
       "NO SKIP REASON RECORDED" in SRC,
       "an absent reason must read as absent — a violation that simply says "
       "less when it knows less is the quiet-degrade shape")

# ── it must be reachable: the gap it reads has to be populated ────────────
ok("the ruled/built gap is recorded on the ledger",
   re.search(r'"ruled_but_not_built"\s*:', SRC) is not None,
   "the violation reads a gap nothing computes")

if fails:
    print(f"RULED-NOT-BUILT: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("RULED-NOT-BUILT: PASS (fails the round, carries its reason, and the "
      "density ruling stays removed)")
