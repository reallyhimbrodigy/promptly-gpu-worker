#!/usr/bin/env python3
"""RED proof for smoke_batch_balance.py, in a throwaway worktree.

The mutations are the ways a batch overcharges or under-informs while still
looking like it works: debiting the whole selection, collapsing PARTIAL into OK,
losing the cap, and treating a negative balance as zero.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

SMOKE = pathlib.Path("smoke_batch_balance.py").resolve()
APPNAME = "agentic_editor_app.py"
_INJECTS = None
MUTATIONS = [
    # AIMED AT THE PARTIAL BRANCH, because that is the only place an
    # overcharge is possible. The first version mutated the OK branch, where
    # `_afford == _n` holds by construction — so `_n * _per` and
    # `_afford * _per` are the SAME VALUE and the edit was semantically
    # vacuous. It changed bytes and could not change behaviour: the vacuity
    # class, in a mutation that declared itself an injection.
    ("a partial batch debits every selected source, not the affordable ones",
     '''    return ("PARTIAL", _afford, _afford * _per,''',
     '''    return ("PARTIAL", _afford, _n * _per,''',
     "debit is never more than the balance", _INJECTS),
    ("PARTIAL collapses into OK",
     '    return ("PARTIAL", _afford, _afford * _per,',
     '    return ("OK", _afford, _afford * _per,',
     "says SIX, before anything dispatches", _INJECTS),
    ("the cap stops being enforced",
     "    if _n > int(max_sources):",
     "    if False:",
     "over the cap is REFUSED", _INJECTS),
    ("a negative balance is treated as zero instead of refused",
     "    if _bal < 0:",
     "    if False:",
     "negative balance is REFUSED", _INJECTS),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="batch_")
_wt = str(pathlib.Path(_tmp) / "wt")
if subprocess.run(["git", "worktree", "add", "--detach", "-q", _wt, "HEAD"],
                  capture_output=True).returncode != 0:
    print("no isolated worktree"); sys.exit(2)
red, harness = 0, []
try:
    shutil.copy(SMOKE, pathlib.Path(_wt) / SMOKE.name)
    APP = pathlib.Path(_wt) / APPNAME
    ORIG = APP.read_text()
    rc, out = run(_wt)
    if rc != 0:
        print("BASELINE IS NOT GREEN:\n" + out[-1200:]); sys.exit(2)
    print("baseline: PASS (isolated worktree)\n")
    for label, old, new, expect, precond in MUTATIONS:
        txt = APP.read_text(); n = txt.count(old)
        if n != 1:
            harness.append(f"{label}: anchor {n}x")
            print(f"  HARNESS FAILURE  {label}  :: anchor {n}x"); continue
        _m = txt.replace(old, new, 1)
        try:
            ast.parse(_m)
        except SyntaxError as e:
            harness.append(f"{label}: mutant does not parse")
            print(f"  HARNESS FAILURE  {label}  :: does not parse ({e.msg})"); continue
        APP.write_text(_m); mrc, mout = run(_wt); APP.write_text(ORIG)
        if mrc == 0:
            print(f"  NOT RED          {label}  :: the mutant PASSED")
            harness.append(f"{label}: mutant passed")
        elif expect not in mout:
            print(f"  WRONG REASON     {label}  :: expected '{expect}'")
            harness.append(f"{label}: wrong reason")
        else:
            red += 1
            print(f"  RED              {label}\n                   caught by: {expect}")
    frc, _ = run(_wt)
    print(f"\nRESTORED exit={frc}")
finally:
    subprocess.run(["git", "worktree", "remove", "--force", _wt], capture_output=True)
    shutil.rmtree(_tmp, ignore_errors=True)
    print(f"isolated worktree removed: {not pathlib.Path(_wt).exists()}")
print(f"{red}/{len(MUTATIONS)} RED-proven"
      + (f"   HARNESS FAILURES: {harness}" if harness else ""))
sys.exit(0 if red and red == len(MUTATIONS) and not harness else 1)
