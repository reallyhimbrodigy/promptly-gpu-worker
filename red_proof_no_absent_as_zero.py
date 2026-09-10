#!/usr/bin/env python3
"""RED proof: the absent-as-zero prohibition must fire on a NEW instance."""
import ast
import os, shutil, subprocess, sys
APP="agentic_editor_app.py"; _ORIG_SRC = {}   # IN MEMORY, never a file
_ORIG_SRC.setdefault(APP, open(APP, encoding="utf-8").read()); env=dict(os.environ,PYTHONPATH=".")
def run():
    r=subprocess.run([sys.executable,"smoke_no_absent_as_zero.py"],
                     capture_output=True,text=True,env=env)
    return r.returncode, r.stdout+r.stderr
def mut(old,new,label,expect):
    src=open(APP,encoding="utf-8").read()
    if src.count(old)!=1:
        print(f"  HARNESS FAILURE [{label}] anchor {src.count(old)}x"); return False
    _mutant=src.replace(old,new,1)
    # A MUTANT THAT DOES NOT PARSE NEVER RAN — it fails the check for a reason
    # unrelated to the property, which is a pass it did not earn.
    try: ast.parse(_mutant)
    except SyntaxError as _se:
        print(f"  HARNESS FAILURE [{label}] mutant does not parse: {_se.msg}"); return False
    open(APP,"w",encoding="utf-8").write(_mutant)
    rc,out=run(); open(APP, "w", encoding="utf-8").write(_ORIG_SRC[APP])
    ok=rc!=0 and expect in out
    print(f"  {'RED ok ' if ok else 'NOT RED'} [{label}] exit={rc}")
    if not ok: print(f"      expected {expect!r}")
    return ok
rc,out=run(); print(f"BASELINE exit={rc}"); assert rc==0,out
r=[]

# 1. A NEW key defaults to 0 inside a report — the paint_ms defect, fresh.
r.append(mut('        _nb_s = "? (NOT RECORDED)" if _nb is None else str(_nb)',
             '        _nb_s = str((r.get("ledger") or {}).get("brand_new_metric") or 0)',
             "a new key defaults to 0 inside a report",
             "no NEW `.get(...) or 0` reaches a report"))

# 2. THE FIXED DENOMINATOR REGRESSES — the line carrying a distribution to Zac.
r.append(mut('        _tot = (r.get("ledger") or {}).get("cut_boundaries_total")\n'
             '        _tot_s = "?" if _tot is None else str(_tot)',
             '        _tot_s = str((r.get("ledger") or {}).get("cut_boundaries_total") or 0)',
             "the cut denominator defaults to 0 again",
             "cut_boundaries_total is not defaulted to 0 in a report"))

rc,out=run(); print(f"RESTORED exit={rc}")
print(f"\n{sum(r)}/{len(r)} RED-proven")
# A HARNESS WITH NO LEGS MUST NOT EXIT 0. all([]) is True and 0 == 0 is
# True, so every red proof in this repo reported success on an empty leg
# list — the empty-set rule, sixteen times, inside the instruments built
# to catch exactly this. A suite PASS has to mean "ran and passed", not
# "did not run".
sys.exit(0 if r and all(r) and rc == 0 else 1)
