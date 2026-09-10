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

# ── THE DISPATCH PATH ───────────────────────────────────────────────────────
# Pricing alone is a number on a screen. What matters is that the batch never
# STARTS a run it cannot finish, and that each job carries its own debit so each
# refunds independently.
for _n2 in tree.body:
    if isinstance(_n2, ast.FunctionDef) and _n2.name == "batch_dispatch_plan":
        exec(compile(ast.Module([_n2], []), "<c>", "exec"), _ns)
check("batch_dispatch_plan is module-level and pure",
      "batch_dispatch_plan" in _ns)
_bd = _ns.get("batch_dispatch_plan")
if _bd:
    _S = ["s%d.mp4" % i for i in range(10)]
    _v, _j, _h, _w = _bd(_S, 100)
    check("a covered batch dispatches every source", _v == "OK"
          and len(_j) == 10 and not _h, f"{_v} {len(_j)} {len(_h)}")
    check("EACH JOB CARRIES ITS OWN DEBIT so each refunds independently",
          all(x["credits"] == 10 for x in _j)
          and sum(x["credits"] for x in _j) == 100,
          "one debit for ten jobs cannot be partially refunded when job seven "
          "is lost")
    _v6, _j6, _h6, _w6 = _bd(_S, 60)
    check("60 credits DISPATCHES SIX AND HOLDS FOUR",
          (_v6, len(_j6), len(_h6)) == ("PARTIAL", 6, 4),
          f"{_v6} dispatch={len(_j6)} held={len(_h6)}")
    check("the held four are NAMED, not silently dropped",
          _h6 == _S[6:], f"{_h6}")
    check("the batch never debits more than the balance",
          sum(x["credits"] for x in _j6) == 60)
    check("a batch that covers nothing dispatches NOTHING",
          _bd(_S, 5)[0] == "NONE" and not _bd(_S, 5)[1]
          and len(_bd(_S, 5)[2]) == 10,
          "a run started that cannot finish is the failure this prevents")
    check("an over-cap selection dispatches nothing and holds everything",
          _bd(["x"] * 11, 500)[0] == "REFUSED" and not _bd(["x"] * 11, 500)[1])
    check("job indices are stable and contiguous",
          [x["index"] for x in _j6] == list(range(6)))

print()
if fails:
    print("BATCH-BALANCE: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("BATCH-BALANCE: PASS — four states, priced before dispatch, 60 credits "
      "against 10 sources answers SIX with the shortfall named")
