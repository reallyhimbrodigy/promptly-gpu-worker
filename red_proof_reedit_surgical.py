#!/usr/bin/env python3
"""RED proof for smoke_reedit_surgical.py, in a throwaway worktree.

The mutations are the ways a re-edit stops being surgical while still producing
a video that looks right: the allow-list stops refusing, an empty scope becomes
a free hand, the prior plan is not loaded at all, and a lost prior ruling stops
being loud.
"""
import ast
import pathlib
import shutil
import subprocess
import sys
import tempfile

SMOKE = pathlib.Path("smoke_reedit_surgical.py").resolve()
APPNAME = "agentic_editor_app.py"
_INJECTS = None

MUTATIONS = [
    # Now aimed at the SHIPPED function rather than at the dispatch that used
    # to inline it — the mutations that passed did so because the smoke drove a
    # copy.
    ("the allow-list stops refusing out-of-scope rulings",
     """        if _b in _t:""",
     """        if True:""",
     "a ruling outside the declared scope is REFUSED", _INJECTS),
    ("an empty scope becomes a free hand",
     """    _t = set(targets or ())""",
     """    _t = set(targets or ()) or {v.get("beat") for v in (prior or [])}""",
     "with NO scope declared, nothing changes at all", _INJECTS),
    ("the prior plan is never loaded",
     '''        _prior, _prior_probs = plan_onto_beats(prior_plan, _beats)''',
     '''        _prior, _prior_probs = [], []''',
     "the plan is loaded onto beats", _INJECTS),
    ("a lost prior ruling stops being loud",
     '''            fail("reedit_prior_lost",''',
     '''            _silently_ignore("reedit_prior_lost",''',
     "a lost prior ruling fails loudly", _INJECTS),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="reedit_")
_wt = str(pathlib.Path(_tmp) / "wt")
if subprocess.run(["git", "worktree", "add", "--detach", "-q", _wt, "HEAD"],
                  capture_output=True).returncode != 0:
    print("could not create an isolated worktree"); sys.exit(2)
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
        txt = APP.read_text()
        n = txt.count(old)
        if n != 1:
            harness.append(f"{label}: anchor {n}x")
            print(f"  HARNESS FAILURE  {label}  :: anchor {n}x"); continue
        _mutant = txt.replace(old, new, 1)
        try:
            ast.parse(_mutant)
        except SyntaxError as _se:
            harness.append(f"{label}: mutant does not parse")
            print(f"  HARNESS FAILURE  {label}  :: does not parse ({_se.msg})")
            continue
        APP.write_text(_mutant)
        mrc, mout = run(_wt)
        APP.write_text(ORIG)
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
