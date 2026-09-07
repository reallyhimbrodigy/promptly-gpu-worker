#!/usr/bin/env python3
"""At what source duration does each reference rate become SATISFIABLE?

THE ARITHMETIC. A rate is per-25s, so the continuous target over a source of
duration D is

    exact = rate * D / 25

and the gate demands the integer  implied = min(n_beats, round(exact)).
Placements are integers; the target is not. Two things can go wrong:

  1. ROUNDS TO ZERO.  exact < 0.5  =>  implied = 0. The family asks for nothing,
     nothing can fall short of it, and the run passes that family by doing
     nothing. This is the hole spec_targets_all_zero was built for.
         threshold:  exact >= 0.5   =>   D_zero = 12.5 / rate

  2. OVERSHOOTS.  Having rounded UP, the run places more than the rate asked
     for. The relative overstatement is (implied - exact) / exact, and its worst
     case at any duration is when exact sits just above a rounding boundary
     n + 0.5, where the error is 0.5 / exact. Requiring that to stay within 20%:
         0.5 / exact <= 0.20   =>   exact >= 2.5   =>   D_fit = 62.5 / rate

D_fit is therefore the minimum duration at which a family can be asked for a
whole number of placements and be within 20% of its own rate NO MATTER where the
duration falls. Below it, the quantisation error alone exceeds the tolerance.
"""
import sys, types
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

FIXTURES = {"product_shot":15.0, "pet_video":18.0, "music":20.0,
            "screen_recording":20.0, "talking_head":38.5}
# Production source_duration, 3,740 jobs, 30 days (video_jobs, non-null, >0)
PROD = {"p10":6.0, "p25":10.1, "p50":19.0, "p75":38.6, "p90":65.3, "max":180.0}

def report(table, name):
    print(f"\n{'='*76}\n{name}\n{'='*76}")
    print(f"{'family':11} {'rate/25s':>9} {'D_zero':>8} {'D_fit':>9}   satisfied by fixtures")
    for fam, rate in sorted(table.items(), key=lambda kv: -kv[1]):
        if rate <= 0:
            print(f"{fam:11} {rate:>9.2f} {'—':>8} {'—':>9}   rate is 0 — absence, not a gap")
            continue
        d_zero = 12.5 / rate
        d_fit  = 62.5 / rate
        okz = [f for f, d in FIXTURES.items() if d >= d_zero]
        okf = [f for f, d in FIXTURES.items() if d >= d_fit]
        note = f"{len(okz)}/5 scoreable, {len(okf)}/5 within 20%"
        print(f"{fam:11} {rate:>9.2f} {d_zero:>7.1f}s {d_fit:>8.1f}s   {note}")
    print(f"\n  D_zero = 12.5/rate  : below this the family implies ZERO — unscoreable")
    print(f"  D_fit  = 62.5/rate  : below this rounding alone can overshoot >20%")

report(A.REFERENCE_PER_25S, "SPEECH corpus reference (REFERENCE_PER_25S)")
report(A.REFERENCE_PER_25S_NOSPEECH, "NO-SPEECH corpus reference (REFERENCE_PER_25S_NOSPEECH)")

print(f"\n{'='*76}\nPER FIXTURE: which speech families are even scoreable?\n{'='*76}")
print(f"{'fixture':18} {'dur':>6}   scoreable (implied>=1)                within 20%")
for f, d in sorted(FIXTURES.items(), key=lambda kv: kv[1]):
    sz = [fam for fam, r in A.REFERENCE_PER_25S.items() if r > 0 and d >= 12.5/r]
    sf = [fam for fam, r in A.REFERENCE_PER_25S.items() if r > 0 and d >= 62.5/r]
    print(f"{f:18} {d:>5.1f}s   {','.join(sorted(sz)) or '—':36} {','.join(sorted(sf)) or '—'}")

print(f"\n{'='*76}\nAGAINST PRODUCTION (3,740 jobs / 30d): what duration is typical?\n{'='*76}")
for k in ("p10","p25","p50","p75","p90","max"):
    d = PROD[k]
    sz = sum(1 for r in A.REFERENCE_PER_25S.values() if r > 0 and d >= 12.5/r)
    sf = sum(1 for r in A.REFERENCE_PER_25S.values() if r > 0 and d >= 62.5/r)
    print(f"  {k:4} = {d:>6.1f}s   {sz}/5 families scoreable   {sf}/5 within 20%")
