#!/usr/bin/env python3
"""A run says what it cost, and says ABSENT when it cannot.

WHY THIS EXISTS. The ledger carried `tokens` and `wall_s` and no dollar figure,
so the one path this lane has built has never been priced against the $0.10/job
law it is held to. The capability router cannot choose between paths it cannot
price; neither can we.

THE THREE WAYS A COST FIGURE LIES, each closed by a leg below:
  * a rate typed from memory — the stale-identifier defect with a decimal
    point. Every rate here carries an in-repo source and a date.
  * a PARTIAL total that reads as a total. An unpriced model makes the whole
    figure ABSENT and names itself.
  * a per-stage split built on a wrong model of what nests, which produces the
    negative remainder this repo has already paid for. The nesting is asserted
    and reports INCOHERENT rather than a share.

RED-proven by red_proof_run_cost.py.
"""
import ast
import pathlib
import sys

import modal_stub                                              # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                 # noqa: E402

src = pathlib.Path("agentic_editor_app.py").read_text()
tree = ast.parse(src)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


# ── THE ARITHMETIC, AGAINST A HAND-COMPUTED FIGURE ──────────────────────────
# Haiku at $1/$5 per MTok, cache_write 1.25x in, cache_read 0.1x in:
#   1e6*1 + 1e6*5 + 1e6*1.25 + 1e6*0.10  =  $7.35 for a million of each
_T = {"claude-haiku-4-5": {"in": 1e6, "out": 1e6, "cache_write": 1e6,
                           "cache_read": 1e6}}
_st, _usd, _d = A.model_usd(_T)
check("the token arithmetic matches a hand-computed figure",
      _st == "MEASURED" and abs(_usd - 7.35) < 1e-6, f"{_st} {_usd}")
# cpu=8, mem=16GiB: 8*0.0000375 + 16*0.00000667 = 0.00040672 per second
check("the container rate matches a hand-computed figure",
      abs(A.container_usd_per_s(8, 16384) - 0.00040672) < 1e-9,
      str(A.container_usd_per_s(8, 16384)))

# ── A PARTIAL TOTAL IS THE WORST OUTCOME ────────────────────────────────────
_mix = {"claude-haiku-4-5": {"in": 1e6}, "some-new-model": {"in": 1e6}}
_st2, _usd2, _d2 = A.model_usd(_mix)
check("an unpriced model makes the figure ABSENT, not partial",
      _st2 == "ABSENT" and _usd2 is None, f"{_st2} {_usd2}")
check("and it NAMES the model it could not price",
      "some-new-model" in (_d2.get("why") or ""), str(_d2))
check("no tokens at all is ABSENT, never zero",
      A.model_usd({})[0] == "ABSENT" and A.model_usd(None)[0] == "ABSENT")
_rc = A.run_cost({"tokens_by_model": _mix}, 100.0)
check("an ABSENT model cost makes the TOTAL absent — a container-only figure "
      "labelled 'total' is a lie",
      _rc["total_usd"] is None and _rc["state"] == "ABSENT")
check("but the container half is still reported, because it IS known",
      _rc["container_usd"] is not None and _rc["container_state"] == "MEASURED")
check("a run with no wall clock reports an ABSENT container, never $0",
      A.run_cost({"tokens_by_model": _T}, 0)["container_state"] == "ABSENT"
      and A.run_cost({"tokens_by_model": _T}, None)["container_usd"] is None)

# ── EVERY RATE CARRIES ITS SOURCE ───────────────────────────────────────────
check("every model rate carries an in-repo source and a date",
      all(r.get("src") and any(ch.isdigit() for ch in r["src"])
          for r in A._MODEL_USD_PER_MTOK.values()),
      str({k: v.get("src") for k, v in A._MODEL_USD_PER_MTOK.items()}))
check("the container figure is labelled an estimate with the dashboard "
      "authoritative",
      "DASHBOARD IS AUTHORITATIVE" in _rc["rate_note"])

# ── THE NESTING IS ASSERTED, NOT ASSUMED ────────────────────────────────────
_good = {"tokens_by_model": _T, "wall_by_stage": {
    "download": 1.0, "model_thinking": 10.0, "tool:execute_plan": 80.0,
    "build_zoom": 40.0, "build_sfx": 5.0}}
_g = A.run_cost(_good, 100.0)
check("a coherent stage model is attributed", _g["stage_state"] == "MEASURED")
check("nested stages are labelled with their parent, not summed as peers",
      _g["by_stage_container_only"]["build_zoom"]["nests_in"] == "tool:execute_plan"
      and _g["by_stage_container_only"]["download"]["nests_in"] is None)
check("the unattributed remainder is present and NOT negative",
      _g["by_stage_container_only"]["(unattributed)"]["s"] >= 0)
_bad = {"tokens_by_model": _T, "wall_by_stage": {
    "download": 1.0, "model_thinking": 10.0, "tool:execute_plan": 80.0,
    "build_zoom": 400.0}}
_b = A.run_cost(_bad, 100.0)
check("a nested sum larger than its parent reports INCOHERENT, not a share",
      _b["stage_state"] == "INCOHERENT" and not _b["by_stage_container_only"],
      str(_b["stage_why"]))
_over = {"tokens_by_model": _T,
         "wall_by_stage": {"download": 90.0, "model_thinking": 90.0}}
check("top-level stages exceeding the run reports INCOHERENT — this is the "
      "negative-remainder defect, refused before it can print",
      A.run_cost(_over, 100.0)["stage_state"] == "INCOHERENT")
check("the model loop is NOT attributed to a build stage",
      "NOT attributable" in src and "container only" in src)

# ── IT IS WIRED, LEDGERED AND PRINTED ───────────────────────────────────────
# RESOLVE THE BINDING. The first draft asked whether a cost_usd assignment
# existed AND whether run_cost was called anywhere — both survive
# `led["cost_usd"] = 0.0`, because the call still happens one line below for a
# different key. One hop of indirection is still scope.
_cu = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
       and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
               and t.slice.value == "cost_usd" for t in n.targets)]
check("cost_usd reaches the ledger", bool(_cu))
_rc_names = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
             and isinstance(n.value, ast.Call)
             and getattr(n.value.func, "id", "") == "run_cost"
             for t in n.targets if isinstance(t, ast.Name)}
check("the ledger value comes from run_cost, not a local computation",
      bool(_rc_names) and any(
          any(isinstance(x, ast.Name) and x.id in _rc_names
              for x in ast.walk(a_.value)) for a_ in _cu),
      f"cost_usd must read the value bound from run_cost ({sorted(_rc_names)})")
_p = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
      and getattr(n.func, "id", "") == "print"
      and any(isinstance(x, ast.Constant) and isinstance(x.value, str)
              and "COST  " in x.value for x in ast.walk(n))]
check("and is PRINTED beside the law it is judged against", bool(_p)
      and any("0.10/job" in ast.unparse(n) for n in _p),
      "a cost with no law beside it is a number nobody acts on")

# ── A STAGE TIMER IS A SUM ACROSS REPEATED CALLS ────────────────────────────
# Round 58 talking_head ran execute_plan twice and every stage under it roughly
# doubled on IDENTICAL work. A reader scoping an optimisation against
# build_alpha_layer's 91.2s would be sizing two builds as one.
check("the stage line declares how many execute_plan calls it sums",
      "SUM ACROSS" in src and "not \n"[0:0] + "per-build figures" in src)
check("and it only says so when there was more than one",
      any(isinstance(n, ast.Compare) and "_k6_total" in ast.unparse(n)
          for n in ast.walk(tree)))
check("a repeat build is reported with what it cost, not just counted",
      "REPEAT BUILDS" in src and "one FEWER placement" in src)

print()
if fails:
    print("RUN-COST: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("RUN-COST: PASS — sourced rates, ABSENT never partial, nesting asserted "
      "rather than assumed, printed against the $0.10 law")
