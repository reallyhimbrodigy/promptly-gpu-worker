#!/usr/bin/env python3
"""RED proof for smoke_no_undefined_names.py, in a throwaway worktree.

The mutations are the four run-breaking classes the gate exists to catch, plus
the two ways the gate itself goes quiet: a missing linter reported as clean,
and an unclassified warning slipping through un-gated.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

import red_proof_anchor

SMOKE = pathlib.Path("smoke_no_undefined_names.py").resolve()
APPNAME = "agentic_editor_app.py"
_INJECTS = None
MUTATIONS = [
    # THE REAL DEFECT, REPRODUCED: a name read before it is assigned, inside a
    # function body, on a line no check executes.
    ("a name is read before it is assigned, exactly as _k6_total was",
     '    _k6_state, _k6_blind, _k6_total = blind_rebuilds(led.get("turns"))',
     '    _unbound_probe_name += 1\n    _k6_state, _k6_blind, _k6_total = blind_rebuilds(led.get("turns"))',
     "no undefined name", _INJECTS),
    ("a dict literal repeats a key with a different value",
     '                         "beat": _it2.get("beat"),',
     '                         "beat": _it2.get("beat"),\n                         "beat": None,',
     "duplicate key", _INJECTS),
    ("a module-level name is simply undefined",
     "_CACHE_WRITE_MULT, _CACHE_READ_MULT = 1.25, 0.10",
     "_CACHE_WRITE_MULT, _CACHE_READ_MULT = 1.25, _NOT_A_REAL_NAME",
     "no undefined name", _INJECTS),
    # DELETED, NOT KEPT AS A SKIP: "the FATAL list stops covering undefined
    # names" was unprovable as a single mutation. On a clean app there is no
    # undefined name to miss, so removing the key changes nothing — and the
    # property it was reaching for is already proven twice above, by injecting
    # an undefined name and watching the gate fail. A mutation that cannot go
    # red is not a mutation, and printing it as a skip would be the failure
    # wearing the notice.
    # TARGETS THE CLASS THE POPULATION ACTUALLY CONTAINS. The first version
    # removed "imported but unused" from TOLERATED — and pyflakes reports none
    # of those on these four files, so the tolerance was for a class that is
    # not there and removing it changed nothing. A mutation on a tolerance list
    # has to name something the corpus actually emits; the only class these
    # files emit is the f-string one, 3 times.
    ("an unclassified warning slips through un-gated",
     '    "f-string is missing placeholders",', '',
     "outside the declared lists", None),
    ("a missing linter reports the file clean",
     '[sys.executable, "-m", "pyflakes", "--version"]',
     '[sys.executable, "-m", "pyflakes_does_not_exist", "--version"]',
     "pyflakes is available", None),
]
# these mutate the SMOKE, not the app
SMOKE_MUTATIONS = {3, 4}


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="udn_")
_wt = str(pathlib.Path(_tmp) / "wt")
if subprocess.run(["git", "worktree", "add", "--detach", "-q", _wt, "HEAD"],
                  capture_output=True).returncode != 0:
    print("no isolated worktree"); sys.exit(2)
red, harness = 0, []
try:
    shutil.copy(SMOKE, pathlib.Path(_wt) / SMOKE.name)
    APP = pathlib.Path(_wt) / APPNAME
    SMK = pathlib.Path(_wt) / SMOKE.name
    ORIG_APP, ORIG_SMK = APP.read_text(), SMK.read_text()
    rc, out = run(_wt)
    if rc != 0:
        print("BASELINE IS NOT GREEN:\n" + out[-1500:]); sys.exit(2)
    print("baseline: PASS (isolated worktree)\n")
    for i, (label, old, new, expect, precond) in enumerate(MUTATIONS):
        _tgt = SMK if i in SMOKE_MUTATIONS else APP
        _orig = ORIG_SMK if i in SMOKE_MUTATIONS else ORIG_APP
        _mode, _m = red_proof_anchor.apply_one(_tgt.read_text(), old, new)
        if _m is None:
            harness.append(f"{label}: anchor {_mode}")
            print(f"  HARNESS FAILURE  {label}  :: anchor {_mode}"); continue
        if _mode != red_proof_anchor.EXACT:
            print(f"  note             {label}  :: matched {_mode}")
        try:
            ast.parse(_m)
        except SyntaxError as e:
            harness.append(f"{label}: mutant does not parse")
            print(f"  HARNESS FAILURE  {label}  :: does not parse ({e.msg})"); continue
        _tgt.write_text(_m); mrc, mout = run(_wt); _tgt.write_text(_orig)
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
