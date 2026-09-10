#!/usr/bin/env python3
"""RED proof for smoke_cutaway_across_sources.py, in a throwaway worktree.

Every mutation is a way the address silently resolves to the WRONG MOMENT while
the video still plays: defaulting an ambiguous ref to source 0, bounding every
source by the first one's duration, treating an unknown duration as zero, and
letting True through as t=1.0.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

SMOKE = pathlib.Path("smoke_cutaway_across_sources.py").resolve()
APPNAME = "agentic_editor_app.py"
_INJECTS = None
MUTATIONS = [
    ("an ambiguous bare timestamp DEFAULTS to source 0",
     "        if _n > 1:\n            return (CUTAWAY_REF_BAD, None, None,",
     "        if False:\n            return (CUTAWAY_REF_BAD, None, None,",
     "bare timestamp across MANY sources is REFUSED", _INJECTS),
    ("every source is bounded by the FIRST source's duration",
     '''    _dur = (durations or {}).get(_idx) if isinstance(durations, dict) \\
        else (durations[_idx] if durations and _idx < len(durations) else None)''',
     '''    _dur = (durations or {}).get(0) if isinstance(durations, dict) \\
        else (durations[0] if durations else None)''',
     "SAME 12.4s is OUTSIDE source 1", _INJECTS),
    ("an unknown duration becomes a bound of ZERO",
     '''    if _dur is None:''',
     '''    if False:
        _dur = 0.0
    if _dur is None:''',
     "REFUSES rather than bounding at 0", _INJECTS),
    ("True is accepted as a timestamp",
     "    if isinstance(ref, (int, float)) and not isinstance(ref, bool):",
     "    if isinstance(ref, (int, float)):",
     "True is not a timestamp", _INJECTS),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="cutsrc_")
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
