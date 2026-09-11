#!/usr/bin/env python3
"""RED proof for smoke_durable_plan.py. Runs in a THROWAWAY WORKTREE.

The mutations are the ways this design fails QUIETLY: anchoring to the index
after all, dropping what cannot be placed, forcing an entry onto the nearest
beat, and an id that stops distinguishing two rulings on one beat. Every one
produces a plausible plan and a silently different edit on reload.
"""
import ast
import pathlib
import shutil
import subprocess
import sys
import tempfile

SMOKE = pathlib.Path("smoke_durable_plan.py").resolve()
APPNAME = "agentic_editor_app.py"
_INJECTS = None

MUTATIONS = [
    ("the plan anchors to the BEAT INDEX after all",
     '''        _e.update({"src_t0": round(float(_t0), 3),
                   "src_t1": round(float(_t1), 3),''',
     '''        _e.update({"src_t0": float(v.get("beat") or 0),
                   "src_t1": float(v.get("beat") or 0) + 1.0,''',
     "SOURCE span, not the beat index", _INJECTS),
    ("an orphan verdict is DROPPED instead of reported",
     '''            problems.append({"state": PLAN_ORPHAN, "beat": v.get("beat"),
                             "why": "verdict names a beat index the beat list "
                                    "does not contain"})
            continue''',
     '''            continue''',
     "REPORTED, not dropped", _INJECTS),
    ("an unplaceable entry is FORCED onto the nearest beat",
     '''        if _best is None or (_cov / _span) < float(min_overlap):''',
     '''        if _best is None:''',
     # The expectation names the leg that ACTUALLY catches it — the graze
     # case. "not forced onto the nearest" was the wording of the
     # zero-overlap leg, which no floor is needed to satisfy.
     "only GRAZES a beat is REPORTED", _INJECTS),
    ("the id stops distinguishing two rulings on one beat",
     '''    _key = "%.3f|%.3f|%s|%s" % (float(src_t0), float(src_t1),
                                str(family), str(content or ""))''',
     '''    _key = "%.3f|%.3f|%s" % (float(src_t0), float(src_t1), str(family))''',
     "DIFFERENT ids", _INJECTS),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="dplan_")
_wt = str(pathlib.Path(_tmp) / "wt")
_made = subprocess.run(["git", "worktree", "add", "--detach", "-q", _wt, "HEAD"],
                       capture_output=True, text=True).returncode == 0
if not _made:
    print("could not create an isolated worktree"); sys.exit(2)
red, harness = 0, []
try:
    shutil.copy(SMOKE, pathlib.Path(_wt) / SMOKE.name)
    APP = pathlib.Path(_wt) / APPNAME
    ORIG = APP.read_text()
    rc, out = run(_wt)
    if rc != 0:
        print("BASELINE IS NOT GREEN — nothing below means anything:\n" + out[-1500:])
        sys.exit(2)
    print("baseline: PASS (isolated worktree)\n")

    for label, old, new, expect, precond in MUTATIONS:
        txt = APP.read_text()
        n = txt.count(old)
        if n != 1:
            harness.append(f"{label}: anchor {n}x")
            print(f"  HARNESS FAILURE  {label}  :: anchor {n}x")
            continue
        _mutant = txt.replace(old, new, 1)
        try:
            ast.parse(_mutant)
        except SyntaxError as _se:
            harness.append(f"{label}: mutant does not parse")
            print(f"  HARNESS FAILURE  {label}  :: mutant does not parse "
                  f"({_se.msg}) — it never ran")
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
    subprocess.run(["git", "worktree", "remove", "--force", _wt],
                   capture_output=True)
    shutil.rmtree(_tmp, ignore_errors=True)
    print(f"isolated worktree removed: {not pathlib.Path(_wt).exists()}")

print(f"{red}/{len(MUTATIONS)} RED-proven"
      + (f"   HARNESS FAILURES: {harness}" if harness else ""))
sys.exit(0 if red and red == len(MUTATIONS) and not harness else 1)
