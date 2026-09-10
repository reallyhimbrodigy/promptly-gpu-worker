#!/usr/bin/env python3
"""RED proof for smoke_agentic_endpoint.py, in a throwaway worktree.

The mutations are the ways this endpoint becomes useless while still looking
wired: blocking instead of spawning, accepting a wrong-shaped plan, dropping the
re-edit payload on the floor, and reporting every run as an edit.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

SMOKE = pathlib.Path("smoke_agentic_endpoint.py").resolve()
APPNAME = "agentic_editor_app.py"
_INJECTS = None
MUTATIONS = [
    ("it blocks on the edit instead of spawning",
     "    _fc = edit.spawn(", "    _fc = edit.remote(",
     "SPAWNS the edit rather than calling it", _INJECTS),
    ("a wrong-shaped prior_plan is accepted",
     "    if _plan is not None and not isinstance(_plan, list):",
     "    if False:",
     "wrong TYPE is refused, not coerced", _INJECTS),
    ("the instruction is dropped on the floor",
     '        instruction=_b.get("instruction") or "",', "",
     "instruction is forwarded", _INJECTS),
    ("every run reports as an edit",
     '''    return {"spawned": True, "call_id": _fc.object_id,
            "job_id": _b.get("job_id"),
            "mode": "reedit" if _plan else "edit"}''',
     '''    return {"spawned": True, "call_id": _fc.object_id,
            "job_id": _b.get("job_id")}''',
     "whether this was an edit or a reedit", _INJECTS),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="agep_")
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
