import shutil, subprocess, sys
APP="agentic_editor_app.py"; SMOKE="smoke_rubric_grades_only.py"; BAK="/tmp/_rb.py"
shutil.copy(APP,BAK)
def run():
    r=subprocess.run([sys.executable,SMOKE],capture_output=True,text=True)
    return r.returncode,(r.stdout+r.stderr)
def mut(old,new,label,expect):
    src=open(APP).read()
    if src.count(old)!=1: print(f"  HARNESS FAILURE [{label}] anchor {src.count(old)}x"); return False
    open(APP,'w').write(src.replace(old,new,1))
    rc,out=run(); shutil.copy(BAK,APP)
    ok=rc!=0 and expect in out
    print(f"  {'RED ok ' if ok else 'NOT RED'} [{label}] exit={rc}")
    return ok
rc,out=run(); print(f"BASELINE exit={rc}"); assert rc==0, out
r=[]
r.append(mut('    "render_frames_mismatch",','    "spec_shortfall_unresolved",\n    "render_frames_mismatch",',
 "a density floor returns as a contract failure","no longer fails the round"))
r.append(mut('''includes 'text': the words ''','''includes 'text' (corpus rate 7.28 per 25s): the words ''',
 "a rate reappears in a tool description","reaches the agent via the tool schemas"))
r.append(mut('        # NOT a failure. Density below a reference rate is an observation about\n        # the edit, not a defect in it.',
 '        if led.get("spec_shortfall"):\n            fail("x", "rulings fall short of your own spec")',
 "execute_plan refuses on density again","execute_plan refusing on density"))
r.append(mut('''REFERENCE_PER_25S = {
    "text":       7.28,''','''REFERENCE_PER_25S = {}
_UNUSED_RATES = {
    "text":       7.28,''',
 "the grading rates are emptied along with the demand","corpus rates are still defined"))
r.append(mut('''    # Re-derive the artifact promises from the FINAL state only.''',
 '''    if (ledger or {}).get("spec_shortfall"):
        out.append("spec_shortfall_unresolved: below the implied count")
    # Re-derive the artifact promises from the FINAL state only.''',
 "a density violation is emitted straight from the ledger",
 "produces NO contract violation"))
r.append(mut('''                        "executions_used": led["execute_plan_calls"] - 1,''',
 '''                        "close_it": ("If a family is short, call rule_all_beats "
                                     "ONCE more with shortfall_reasons naming "
                                     "the declined beats."),
                        "executions_used": led["execute_plan_calls"] - 1,''',
 "an instruction names a field the schema does not have",
 "names only fields that exist"))
rc,out=run(); print(f"RESTORED exit={rc}")
print(f"\n{sum(r)}/{len(r)} RED-proven")
sys.exit(0 if all(r) and rc==0 else 1)
