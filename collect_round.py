#!/usr/bin/env python3
"""Score a round from logs that already exist — no launching, no spend.

EXTRACTED 2026-09-07 because the collector lived inline in run_round.sh, so
re-scoring a finished round meant re-running the launcher and paying for five
fixtures again. That is also why the streak re-score had to be done with ad-hoc
greps instead of the real scorer.

  python3 collect_round.py <round-number>
"""
import os, sys, json, re
import re as _re
import reliability_gate as rg

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(2)
_arg = sys.argv[1]
# Accept a ROUND NUMBER (the documented form) or an explicit path. It used to
# accept both by accident and resolve neither correctly — `collect_round.py 30`
# wrote 30/score.json into the cwd rather than scoring round 30. A scorer that
# silently scores the wrong directory is not re-runnable, which is the whole
# reason this was extracted from run_round.sh.
out = _arg if os.path.isdir(_arg) else f"/tmp/fixtures/round{_arg}"
if not os.path.isdir(out):
    print(f"no such round: {out}")
    sys.exit(2)

import json, re, sys, os, importlib.util
# (out is resolved above from a round number or a path — do not rebind it)
spec = importlib.util.spec_from_file_location("rg", "reliability_gate.py")
rg = importlib.util.module_from_spec(spec); spec.loader.exec_module(rg)
res = {}
for name in rg.REQUIRED_SOURCES:
    p = os.path.join(out, f"{name}.log")
    if not os.path.exists(p):
        continue
    t = open(p, encoding="utf-8", errors="ignore").read()
    ok = bool(re.search(r"^  ok +: True", t, re.M))
    kept = re.search(r"kept [\d.]+s of [\d.]+s \(([\d.]+)\)", t)
    pm = re.search(r"PLACEMENT MANIFEST — (\d+) declared", t)
    # READ THE PRODUCER'S VERDICT, DO NOT RE-DERIVE IT.
    #
    # This used to scrape the log for a hardcoded enum of five violation kinds.
    # CONTRACT_FAILURES has SEVEN, and the two it did not know were invisible —
    # round 23 carried 12 spec_shortfall_unresolved across 4 fixtures and scored
    # "all five green". A reader that re-declares the producer's vocabulary
    # falls behind it silently, because a kind it has never heard of looks
    # exactly like a clean run.
    cvm = re.search(r"CONTRACT VIOLATIONS: (\d+)((?:\n\s+- [^\n]*)*)", t)
    if cvm:
        cv_list = [l.strip()[2:] for l in cvm.group(2).split("\n") if l.strip().startswith("- ")]
        if len(cv_list) != int(cvm.group(1)):
            cv_list.append(f"COLLECTOR_MISPARSE: line said {cvm.group(1)}, parsed {len(cv_list)}")
    else:
        # NO LINE AT ALL is not "no violations" — it is a run that never reached
        # its own summary, or a binary predating the line. Absence must never
        # render as success; say so and let the round go red.
        cv_list = ([] if not ok else
                   ["no_contract_verdict: run produced no CONTRACT VIOLATIONS line"])
    res[name] = {"ok": ok,
                 "kept_ratio": float(kept.group(1)) if kept else None,
                 "placements": int(pm.group(1)) if pm else 0,
                 "contract_violations": cv_list}
green, why = rg.round_is_green(res)
json.dump({"result": res, "green": green, "why": why},
          open(os.path.join(out, "score.json"), "w"), indent=1)
print(f"\nROUND {os.environ.get('PROMPTLY_ROUND') or os.path.basename(out).replace('round','')} GREEN={green}")
print(f"  {why}")
# THE SIGNATURE ON EVERY FIXTURE, not just the one being read closely. A run at
# half the turns and two-thirds the placements of its neighbours is green for
# the wrong reason — it did less, and every gate passes because everything it
# DID do was correct. Printed per fixture so the variance question accumulates
# evidence across rounds instead of being re-litigated from one log at a time.
import re as _re
print()
print(f"  {'fixture':18} {'turns':>6} {'cost':>9} {'placed':>7}  families")
for _n in sorted(res):
    _p = os.path.join(out, f"{_n}.log")
    _t = open(_p, encoding='utf-8', errors='ignore').read() if os.path.exists(_p) else ''
    _m = _re.search(r"RUN SIGNATURE   : turns (\d+)\s+cost \$([\d.]+)\s+placements (\d+)\s+\[([^\]]*)\]", _t)
    if _m:
        print(f"  {_n:18} {_m.group(1):>6} {'$'+_m.group(2):>9} {_m.group(3):>7}  [{_m.group(4)}]")
    else:
        print(f"  {_n:18} {'—':>6} {'—':>9} {'—':>7}  (no signature — run did not reach the summary)")
print()
for n, v in sorted(res.items()):
    print(f"  {n:<18} ok={v['ok']} kept={v['kept_ratio']} placements={v['placements']}"
          + (f" VIOLATIONS={v['contract_violations']}" if v["contract_violations"] else ""))

# ── THE ROUND-LEVEL AGGREGATE ──────────────────────────────────────────────
# Sub-unit families (sfx 0.82/25s, zoom 0.35/25s) cannot be scored per fixture:
# zoom needs a 178.6s source to be within 20% of its own rate and production's
# LONGEST job is 180.0s. Their expectations are summed across the round instead,
# UNROUNDED — rounding per fixture and then summing is the error this undoes.
#
# The same fittability bar applies at round level: an aggregate expectation
# under 2.5 still cannot be judged within 20%, and saying so beats printing a
# number that means nothing.
import json as _json
_agg, _durs = {}, []
for _n in sorted(res):
    _p = os.path.join(out, f"{_n}.log")
    _t2 = open(_p, encoding='utf-8', errors='ignore').read() if os.path.exists(_p) else ''
    _rm = _re.search(r"RATE REGIMES    : (\{.*)", _t2)
    if not _rm:
        continue
    try:
        _blob = _json.loads(_rm.group(1))
    except Exception:
        continue
    _durs.append(_blob.get("dur_s") or 0)
    for _f, _d in (_blob.get("families") or {}).items():
        a = _agg.setdefault(_f, {"expected": 0.0, "actual": 0, "regimes": {},
                                 "rate": _d.get("rate")})
        a["expected"] += float(_d.get("expected") or 0)
        a["actual"] += int(_d.get("actual") or 0)
        a["regimes"][_d.get("regime")] = a["regimes"].get(_d.get("regime"), 0) + 1

if _agg:
    _tot = sum(_durs)
    print()
    print(f"  ROUND AGGREGATE  ({len(_durs)} fixtures, {_tot:.1f}s total)")
    print(f"  {'family':10} {'rate':>6} {'expected':>9} {'actual':>7} {'err':>7}   per-fixture regimes")
    for _f in sorted(_agg, key=lambda k: -(_agg[k]["rate"] or 0)):
        a = _agg[_f]
        _regs = ",".join(f"{k}x{v}" for k, v in sorted(a["regimes"].items()))
        if a["expected"] < 2.5:
            _need = (2.5 / a["expected"]) if a["expected"] > 0 else float('inf')
            _err = "UNSCOREABLE"
            _note = f"  needs ~{_need:.1f} rounds of this corpus"
        else:
            _e = abs(a["actual"] - a["expected"]) / a["expected"] * 100
            _err = f"{_e:.0f}%"
            _note = "  WITHIN 20%" if _e <= 20 else "  OUTSIDE 20%"
        print(f"  {_f:10} {a['rate']:>6.2f} {a['expected']:>9.2f} {a['actual']:>7} "
              f"{_err:>7}   {_regs}{_note}")
    print("  (per_run families are judged per fixture above; aggregate/out_of_scope "
          "families are judged only here)")
