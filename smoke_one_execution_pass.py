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

_m = types.ModuleType("modal")
class _S:
    def __init__(s,*a,**k): pass
    def __getattr__(s,n): return _S()
    def __call__(s,*a,**k): return _S()
    def function(s,*a,**k): return lambda f: f
    def local_entrypoint(s,*a,**k): return lambda f: f
for _n in ("App","Image","Secret","Volume","Cls","Function"): setattr(_m,_n,_S())
_m.is_local=lambda: True; _m.enable_output=_S()
sys.modules.setdefault("modal", _m)
import agentic_editor_app as A

src = pathlib.Path(A.__file__).read_text()
fails=[]
def check(l,c,d=""):
    if not c: fails.append(l + (f"  :: {d}" if d else ""))

check("a second execute_plan is REFUSED",
      'led["execute_plan_calls"] > 1' in src and '"refused": "one execution pass"' in src,
      "the gate must be in the dispatch, not the prompt")
check("the refusal tells the agent how to close the shortfall WITHOUT a render",
      "close_the_shortfall_by_naming" in src,
      "an unsatisfiable refusal burns the turn budget — that is what the "
      "shortfall livelock did before")
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

if fails:
    print(f"ONE-EXECUTION-PASS: {len(fails)} FAILED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print("ONE-EXECUTION-PASS: PASS")
