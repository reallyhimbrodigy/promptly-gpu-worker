import ast
import os, shutil, subprocess, sys
APP="agentic_editor_app.py"; CERT="cert_mg_prop_keys.py"; CAT="knowledge/05_motion_graphics.md"
BAKS={p:"/tmp/_cl_"+os.path.basename(p) for p in (APP,CERT,CAT)}
for p,b in BAKS.items(): shutil.copy(p,b)
env=dict(os.environ,PYTHONPATH=".")
def run(s):
    r=subprocess.run([sys.executable,s],capture_output=True,text=True,env=env)
    return r.returncode, r.stdout+r.stderr
def mut(path,old,new,label,expect,smoke):
    src=open(path,encoding="utf-8").read()
    if src.count(old)!=1:
        print(f"  HARNESS FAILURE [{label}] anchor {src.count(old)}x"); return False
    _mutant=src.replace(old,new,1)
    # A MUTANT THAT DOES NOT PARSE NEVER RAN — it fails the check for a reason
    # unrelated to the property, which is a pass it did not earn.
    # ONLY FOR PYTHON TARGETS. This harness mutates a MARKDOWN catalogue and a
    # JSON index as well as source, and ast.parse on markdown fails every time
    # — my first version of this guard turned a working harness red on its own
    # first run. A rule applied without asking what it is being applied to.
    if str(path).endswith(".py"):
        try: ast.parse(_mutant)
        except SyntaxError as _se:
            print(f"  HARNESS FAILURE [{label}] mutant does not parse: "
                  f"{_se.msg} — it never ran, so it proved nothing"); return False
    open(path,"w",encoding="utf-8").write(_mutant)
    rc,out=run(smoke); shutil.copy(BAKS[path],path)
    ok=rc!=0 and expect in out
    print(f"  {'RED ok ' if ok else 'NOT RED'} [{label}] exit={rc}")
    if not ok: print(f"      expected {expect!r}")
    return ok
for s in (CERT,"smoke_card_choice_retired.py"):
    rc,out=run(s); print(f"BASELINE {s} exit={rc}"); assert rc==0,out
r=[]
# 1. A selectable type loses its Claim line — a component nobody can learn.
r.append(mut(CAT,"**StatCard**","**StatCardX**",
  "a selectable type loses its catalogue entry",
  "every selectable type has a Claim line",CERT))
# 2. The claim index comes back — a table kept alive by its own check.
r.append(mut(APP,"# THE CLAIM INDEX IS RETIRED (2026-09-09).",
  "MG_CLAIM_INDEX = {}\n# THE CLAIM INDEX IS RETIRED (2026-09-09).",
  "the claim index returns with no reader",
  "the claim index is GONE","smoke_card_choice_retired.py"))
for s in (CERT,"smoke_card_choice_retired.py"):
    rc,out=run(s); print(f"RESTORED {s} exit={rc}")
    if rc!=0: print(out); sys.exit(1)
print(f"\n{sum(r)}/{len(r)} RED-proven")
sys.exit(0 if all(r) else 1)
