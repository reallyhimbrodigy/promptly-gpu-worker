#!/usr/bin/env python3
"""A batch is priced BEFORE any dispatch, so a shortfall is a sentence not four failures.

THE FAILURE THIS PREVENTS. A user with 60 credits selects ten sources: six
render, four fail. Those four are not failures — they are arithmetic nobody did
— and the user paid attention to ten things and got six with no explanation.
This lane's law is fail loudly to us and never to the user; a silent partial
batch fails to the user in the most confusing way available.

So `plan_batch` is a PURE decision returned to the caller, not a check performed
at dispatch time when three jobs are already running. It answers with a state
and BOTH numbers: how many are affordable, and what they cost.

    OK        every selected source is affordable
    PARTIAL   some are — `affordable` says how many, and the caller ASKS before
              dispatching any of them
    NONE      the balance covers zero jobs
    REFUSED   the selection itself is invalid: empty, over the cap, or not
              numbers

FOUR STATES, NOT A BOOLEAN. "Can they afford it" collapses PARTIAL into False
and NONE into False, and those need different sentences — one offers six jobs,
the other says how many credits are missing.

RED-proven by red_proof_batch_balance.py.
"""
import ast
import pathlib
import sys

src = pathlib.Path("agentic_editor_app.py").read_text()
tree = ast.parse(src)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


_ns = {}
for _n in tree.body:
    if isinstance(_n, ast.Assign) and any(
            getattr(_x, "id", "") in ("MULTI_UPLOAD_MAX", "CREDITS_PER_JOB")
            for _t in _n.targets for _x in ast.walk(_t)):
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
    if isinstance(_n, ast.FunctionDef) and _n.name == "plan_batch":
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
check("plan_batch is module-level and pure (a test can drive it)",
      "plan_batch" in _ns)
if "plan_batch" not in _ns:
    print("\nBATCH-BALANCE: FAIL"); sys.exit(1)
f = _ns["plan_batch"]
check("the cap and the per-job price are named constants",
      _ns.get("MULTI_UPLOAD_MAX") == 10 and _ns.get("CREDITS_PER_JOB") == 10,
      f"cap={_ns.get('MULTI_UPLOAD_MAX')} per_job={_ns.get('CREDITS_PER_JOB')}")

# ── THE CASE IN THE REQUIREMENT ─────────────────────────────────────────────
_v, _a, _d, _w = f(10, 60)
check("60 credits against 10 sources says SIX, before anything dispatches",
      (_v, _a, _d) == ("PARTIAL", 6, 60),
      f"{_v} afford={_a} debit={_d} — this is the sentence that replaces four "
      f"silent failures")
check("and the shortfall names what is missing", "40 more credits" in _w, _w)

# ── the other three states ──────────────────────────────────────────────────
check("a covered batch is OK and debits exactly its cost",
      f(10, 100)[:3] == ("OK", 10, 100), f"{f(10, 100)}")
check("a balance under one job is NONE, not PARTIAL",
      f(10, 5)[:3] == ("NONE", 0, 0), f"{f(10, 5)}")
check("NONE says how many credits ONE job needs", "10 needed" in f(10, 5)[3],
      f(10, 5)[3])
check("an empty selection is REFUSED", f(0, 100)[0] == "REFUSED")
check("over the cap is REFUSED and names the cap",
      f(11, 500)[0] == "REFUSED" and "cap is 10" in f(11, 500)[3],
      f"{f(11, 500)}")
check("a negative balance is REFUSED, not treated as zero",
      f(3, -10)[0] == "REFUSED", f"{f(3, -10)}")
check("non-numeric input is REFUSED rather than raising",
      f("ten", 100)[0] == "REFUSED" and f(3, None)[0] == "REFUSED")

# ── the arithmetic itself ───────────────────────────────────────────────────
check("debit is never more than the balance",
      all(f(n, b)[2] <= b for n in range(1, 11) for b in (0, 5, 35, 60, 100)),
      "a batch that debits more than the user has is the overdraft this "
      "function exists to make impossible")
check("affordable never exceeds what was selected",
      all(f(n, 1000)[1] <= n for n in range(1, 11)))
check("exactly one boundary: 9 credits is NONE, 10 is OK",
      f(1, 9)[0] == "NONE" and f(1, 10)[0] == "OK",
      f"{f(1, 9)[0]} / {f(1, 10)[0]}")

print()
if fails:
    print("BATCH-BALANCE: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("BATCH-BALANCE: PASS — four states, priced before dispatch, 60 credits "
      "against 10 sources answers SIX with the shortfall named")
