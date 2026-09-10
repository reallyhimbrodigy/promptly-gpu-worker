import os, shutil, subprocess, sys
APP="agentic_editor_app.py"; CERT="cert_mg_prop_keys.py"; CAT="knowledge/05_motion_graphics.md"
# BACKUP IN MEMORY, NEVER A SHARED FILE — see red_proof_alpha_state.py for
# the full note. A "/tmp/..." backup path is shared across every branch and
# worktree on this machine; Builder-2 watched one silently restore another
# branch's app over their working copy and then print 19/19 RED-proven.
_ORIG={p: open(p, encoding="utf-8").read() for p in (APP,CERT,CAT)}
for p,b in _ORIG.items(): shutil.copy(p,b)
env=dict(os.environ,PYTHONPATH=".")
def run(s):
    r=subprocess.run([sys.executable,s],capture_output=True,text=True,env=env)
    return r.returncode, r.stdout+r.stderr
def mut(path,old,new,label,expect,smoke):
    src=open(path,encoding="utf-8").read()
    if src.count(old)!=1:
        print(f"  HARNESS FAILURE [{label}] anchor {src.count(old)}x"); return False
    open(path,"w",encoding="utf-8").write(src.replace(old,new,1))
    rc,out=run(smoke); open(path, "w", encoding="utf-8").write(_ORIG[path])
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
# A FLOOR, BECAUSE all([]) IS TRUE. A red proof whose mutation list is
# emptied — by a bad merge, a botched refactor, a commented-out block —
# reports SUCCESS. An instrument built to prove a check CAN FAIL,
# rendering its own absence as success. Found in 10 of 11 here and 16 of
# 16 on Builder-2's tree: 26 of 27 across both.
sys.exit(0 if r and all(r) else 1)
