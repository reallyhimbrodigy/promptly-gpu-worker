#!/usr/bin/env python3
"""RED proof: the standard must stay in the prefix, and absence must stay spoken."""
import os, shutil, subprocess, sys
APP="agentic_editor_app.py"; BAK="/tmp/_rtk.py"
shutil.copy(APP,BAK); env=dict(os.environ,PYTHONPATH=".")
def run():
    r=subprocess.run([sys.executable,"smoke_ruling_time_knowledge.py"],
                     capture_output=True,text=True,env=env)
    return r.returncode, r.stdout+r.stderr
def mut(old,new,label,expect):
    src=open(APP,encoding="utf-8").read()
    if src.count(old)!=1:
        print(f"  HARNESS FAILURE [{label}] anchor {src.count(old)}x"); return False
    open(APP,"w",encoding="utf-8").write(src.replace(old,new,1))
    rc,out=run(); shutil.copy(BAK,APP)
    ok=rc!=0 and expect in out
    print(f"  {'RED ok ' if ok else 'NOT RED'} [{label}] exit={rc}")
    if not ok: print(f"      expected {expect!r}")
    return ok
rc,out=run(); print(f"BASELINE exit={rc}"); assert rc==0,out
r=[]

# 1. The standard stops reaching the prefix — read_knowledge again.
r.append(mut('                + "\\n\\n" + ruling_time_knowledge())',
             '                )',
             "the standard stops being injected into the system block",
             "ruling_time_knowledge is CALLED into the system block"))

# 2. A CATALOGUE is added — 9,168 tokens of lookup material on every run.
r.append(mut('_RULING_TIME_DOCS = ("02_intent_standard.md",',
             '_RULING_TIME_DOCS = ("05_motion_graphics.md", "02_intent_standard.md",',
             "a catalogue is pulled into the prefix",
             "05_motion_graphics.md stays on disk"))

# 3. A MISSING document shrinks the block silently instead of saying so.
r.append(mut('        _head += ("\\n  (MISSING and not read: %s — the standard below is "',
             '        _head += ("" if True else "\\n  (MISSING and not read: %s — the standard below is "',
             "a missing document is no longer named",
             "a missing document is NAMED, not silently dropped"))

# 4. Total failure returns an empty block rather than saying UNAVAILABLE.
r.append(mut('        return ("EDITORIAL STANDARD: UNAVAILABLE — none of %s could be read. You "',
             '        return ("" if True else "EDITORIAL STANDARD: UNAVAILABLE — none of %s could be read. You "',
             "a total failure returns silence",
             "a total failure says UNAVAILABLE, never an empty string"))

# 5. The intent standard is dropped — the one document that IS the standard.
r.append(mut('_RULING_TIME_DOCS = ("02_intent_standard.md",\n',
             '_RULING_TIME_DOCS = (\n',
             "the intent standard is dropped from the set",
             "02_intent_standard.md is included"))

# 6. THE SWITCH DEFAULTS TO OFF — an unset flag ships a darker prefix, which is
#    the nine-dark-features class this repo has paid for repeatedly.
r.append(mut('    return str(os.environ.get("PROMPTLY_DISABLE_" + name.upper(), "")).strip() != "1"',
             '    return str(os.environ.get("PROMPTLY_ENABLE_" + name.upper(), "")).strip() == "1"',
             "the switch defaults to OFF instead of ON",
             "unset means ON"))
# 7. A truthy-looking value removes it, so '0' or 'false' silently strips the
#    prefix — the classic flag-parsing defect.
r.append(mut('.strip() != "1"', '.strip() == ""',
             "any non-empty value removes the material",
             "only the literal '1' disables it"))
# 8. A removal stops declaring itself and reads as a missing document.
r.append(mut('        return ("EDITORIAL STANDARD: REMOVED for this run "',
             '        return ("EDITORIAL STANDARD: UNAVAILABLE — none of it could be read. "\n                "" if False else "x" if False else "EDITORIAL STANDARD: REMOVED_ for this run "',
             "a deliberate removal reads as a missing document",
             "a removal SAYS it is deliberate"))
rc,out=run(); print(f"RESTORED exit={rc}")
print(f"\n{sum(r)}/{len(r)} RED-proven")
sys.exit(0 if all(r) and rc==0 else 1)
