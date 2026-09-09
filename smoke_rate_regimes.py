#!/usr/bin/env python3
"""SMOKE: three regimes, and the aggregate that makes sub-unit rates mean anything.

MEASURED 2026-09-07 over 3,740 production jobs and the five fixtures. A rate is
per-25s and placements are integers, so over duration D the continuous target
exact = rate*D/25 must be met by round(exact):

    exact >= 2.5  per_run       worst-case rounding error 0.5/exact <= 20%
    exact >= 0.5  aggregate     expressible, but not scoreable HERE
    else          out_of_scope  round() is 0 — cannot appear on this source

zoom needs a 178.6s source to sit within 20% of 0.35/25s; production's LONGEST
job is 180.0s, and only 0.5% of traffic clears it. The fixtures are not short —
production p50 is 19.0s and they span 15.0-38.5s. sfx and zoom are SUB-UNIT
rates (14 sfx and 6 zooms in a 124-beat corpus): a rarity, not a density.
Scoring a rarity per-run measures which fixture you drew, which is why round 25
reported 'zoom over' on one fixture and 'zoom under' on another in one round.
"""
import sys, types, json, ast, pathlib

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

fails = []
def check(label, cond, detail=""):
    if not cond: fails.append(label + (f"  :: {detail}" if detail else ""))

R = A.REFERENCE_PER_25S
FX = {"product_shot":15.0, "pet_video":18.0, "music":20.0,
      "screen_recording":20.0, "talking_head":38.5}

# ── 1. THE BOUNDARIES, exactly ─────────────────────────────────────────────
# rate 1.0/25s: exact == D/25. So D=62.5 -> 2.5 ; D=12.5 -> 0.5.
check("exact == 2.5 is per_run (inclusive)",   A.rate_regime(1.0, 62.5) == "per_run")
check("just under 2.5 is aggregate",           A.rate_regime(1.0, 62.4) == "aggregate")
check("exact == 0.5 is aggregate (inclusive)", A.rate_regime(1.0, 12.5) == "aggregate")
check("just under 0.5 is out_of_scope",        A.rate_regime(1.0, 12.4) == "out_of_scope")
check("a zero rate is out_of_scope",           A.rate_regime(0.0, 100.0) == "out_of_scope")
check("a bool is not a rate",                  A.rate_regime(True, 100.0) == "out_of_scope")
check("zero duration is out_of_scope",         A.rate_regime(7.28, 0.0) == "out_of_scope")

# ── 2. THE MEASURED CLASSIFICATION — the whole point ───────────────────────
check("zoom is NEVER per_run on any fixture",
      all(A.rate_regime(R["zoom"], d) != "per_run" for d in FX.values()),
      "0.35/25s needs 178.6s; production max is 180.0s")
check("zoom is out_of_scope on every fixture under 35.7s",
      all(A.rate_regime(R["zoom"], d) == "out_of_scope"
          for d in FX.values() if d < 35.7))
check("sfx is out_of_scope at 15.0s and aggregate by 18.0s",
      A.rate_regime(R["sfx"], 15.0) == "out_of_scope"
      and A.rate_regime(R["sfx"], 18.0) == "aggregate")
check("text and cut are per_run on ALL five fixtures",
      all(A.rate_regime(R[f], d) == "per_run" for f in ("text","cut") for d in FX.values()),
      "these are the families a 20s fixture CAN score")
check("card is per_run only on talking_head",
      [f for f, d in FX.items() if A.rate_regime(R["card"], d) == "per_run"] == ["talking_head"])

# ── 3. EXPECTED IS CARRIED UNROUNDED ───────────────────────────────────────
# Rounding per fixture then summing is the error the aggregate exists to undo.
fr = A.family_regimes({"zoom": R["zoom"]}, 20.0)
check("expected is the CONTINUOUS target, not round()",
      abs(fr["zoom"]["expected"] - 0.28) < 0.001,
      f'got {fr["zoom"]["expected"]} — rounding here defeats the aggregate')
tot = sum(FX.values())
check("summed unrounded, zoom over the round is 1.56 not 0",
      abs(R["zoom"] * tot / 25.0 - 1.561) < 0.01)
check("and 1.56 is still UNSCOREABLE at round level (<2.5)",
      R["zoom"] * tot / 25.0 < 2.5,
      "one round of this corpus cannot judge zoom either — say so, do not print a number")
check("sfx DOES become scoreable at round level",
      R["sfx"] * tot / 25.0 >= 2.5)

# ── 4. PER-RUN SCORING TOUCHES PER-RUN FAMILIES ONLY ───────────────────────
src = pathlib.Path(A.__file__).read_text()
# READ THE COMPREHENSION, NOT ITS PUNCTUATION. This greped
# "and str(k) in _per_run_fams" and broke when an unrelated clause was removed
# from the same comprehension — the restriction was intact, the word `and` was
# not. A check that fails on incidental syntax is a check that will be deleted
# by whoever it interrupts.
_asn = next((n for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Assign)
             and any(getattr(t, "id", "") == "_spec_t" for t in n.targets)), None)
check("_spec_t is built by a comprehension", isinstance(getattr(_asn, "value", None),
                                                        ast.DictComp))
check("_spec_t is restricted to per-run families",
      _asn is not None and "_per_run_fams" in {
          n.id for g in _asn.value.generators for c in g.ifs
          for n in ast.walk(c) if isinstance(n, ast.Name)},
      "a per-run verdict on a sub-unit family is quantisation, not behaviour")
check("the regimes are recorded on the ledger for the round to sum",
      'led["rate_regimes"] = family_regimes(' in src)

# ── 5. spec_implies_nothing SEES IN-SCOPE FAMILIES ONLY ────────────────────
# Predicted before building: judging "did the spec ask for anything?" over
# families that CANNOT be asked for here would fire on correct behaviour.
tree = ast.parse(src)
calls = [n for n in ast.walk(tree)
         if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "spec_implies_nothing"]
check("spec_implies_nothing is called", len(calls) >= 1)
for c in calls:
    a0 = c.args[0] if c.args else None
    check("it is not passed the shortfall-filtered _spec_t",
          not (isinstance(a0, ast.Name) and a0.id == "_spec_t"))
    check("it is passed the SCOPED target set",
          isinstance(a0, ast.Name) and a0.id == "_scoped_t",
          ast.dump(a0)[:100] if a0 else "none")
check("out_of_scope families are excluded from the scoped set",
      'if d["regime"] != REGIME_OUT_OF_SCOPE' in src)

# ── 6. THE LINE, AND A READER THAT OWNS NO VOCABULARY ──────────────────────
check("the RATE REGIMES line is emitted", "RATE REGIMES    : " in src)
# THE COLLECTOR NOW LIVES IN ONE PLACE. This read run_round.sh, which
# carried a 113-line inline COPY of collect_round.py; the copy is gone, so
# reading the runner tested a scorer that no longer exists there. Pinning a
# check to the duplicate rather than the real thing is how both copies came
# to resolve fixtures from a hardcoded v1 tuple with every smoke green.
runner = pathlib.Path(__file__).with_name("collect_round.py").read_text()
check("the collector parses that line", "RATE REGIMES" in runner)
code = "\n".join(l for l in runner.split("\n") if not l.strip().startswith("#"))
for fam in ("zoom", "sfx", "card"):
    check(f"the collector does not hardcode the family `{fam}`",
          f'"{fam}"' not in code and f"'{fam}'" not in code,
          "the producer names its families; a reader with its own list drifts")
check("an under-2.5 aggregate is reported UNSCOREABLE, not as a number",
      "UNSCOREABLE" in runner)

if fails:
    print(f"RATE-REGIMES: {len(fails)} FAILED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print("RATE-REGIMES: PASS")
