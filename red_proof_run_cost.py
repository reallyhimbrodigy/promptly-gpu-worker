#!/usr/bin/env python3
"""RED proof for smoke_run_cost.py, in a throwaway worktree.

The mutations are the three ways a cost figure lies — a rate drifting off its
source, a partial total presented as a total, a stage split built on a wrong
model of what nests — plus the two ways the number goes quiet.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

import red_proof_anchor

SMOKE = pathlib.Path("smoke_run_cost.py").resolve()
APPNAME = "agentic_editor_app.py"
_INJECTS = None
MUTATIONS = [
    ("a token rate drifts off its source",
     '"claude-haiku-4-5": {"in": 1.00, "out": 5.00,',
     '"claude-haiku-4-5": {"in": 1.00, "out": 4.00,',
     "hand-computed figure", _INJECTS),
    ("the cache-read multiplier drifts",
     "_CACHE_WRITE_MULT, _CACHE_READ_MULT = 1.25, 0.10",
     "_CACHE_WRITE_MULT, _CACHE_READ_MULT = 1.25, 1.00",
     "hand-computed figure", _INJECTS),
    ("the container rate drifts",
     "_MODAL_CPU_USD_PER_CORE_S = 0.0000375",
     "_MODAL_CPU_USD_PER_CORE_S = 0.000075",
     "container rate matches", _INJECTS),
    ("an unpriced model is silently skipped and the total reads complete",
     '    if _unpriced:\n        return ("ABSENT", None,',
     '    if False:\n        return ("ABSENT", None,',
     "ABSENT, not partial", _INJECTS),
    ("a missing wall clock prices the container at $0 instead of ABSENT",
     '    _cstate = "MEASURED" if _w > 0 else "ABSENT"',
     '    _cstate = "MEASURED"',
     "ABSENT container, never $0", _INJECTS),
    ("an ABSENT model cost stops blocking the total",
     '    _total = (round(_container + _model, 6)\n'
     '              if _cstate == "MEASURED" and _mstate == "MEASURED" else None)',
     '    _total = (round(_container + (_model or 0), 6)\n'
     '              if _cstate == "MEASURED" else None)',
     "makes the TOTAL absent", _INJECTS),
    ("the nesting check stops firing and a wrong model prints shares",
     "        elif _parent and _nest_sum > _parent + 0.5:",
     "        elif False:",
     "INCOHERENT, not a share", _INJECTS),
    ("top-level stages may exceed the run — the negative remainder returns",
     "        if _top_sum > _w + 0.5:",
     "        if False:",
     "negative-remainder defect", _INJECTS),
    ("a rate loses its provenance",
     '"src": "agentic_editor_app.py:~3487, measured 2026-09"',
     '"src": ""',
     "carries an in-repo source", _INJECTS),
    ("the container estimate stops saying the dashboard is authoritative",
     '"x $%s/GiB-s); MODAL DASHBOARD IS AUTHORITATIVE"',
     '"x $%s/GiB-s)"',
     "dashboard authoritative", _INJECTS),
    ("the cost stops being printed against its law",
     '"(%s)  vs the $0.10/job law%s"', '"(%s)%s"',
     "PRINTED beside the law", _INJECTS),
    ("the ledger takes a local figure instead of run_cost",
     '    led["cost_usd"] = _cost["total_usd"]',
     '    led["cost_usd"] = 0.0',
     "comes from run_cost", _INJECTS),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="cost_")
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
        print("BASELINE IS NOT GREEN:\n" + out[-1500:]); sys.exit(2)
    print("baseline: PASS (isolated worktree)\n")
    for label, old, new, expect, precond in MUTATIONS:
        txt = APP.read_text()
        _mode, _m = red_proof_anchor.apply_one(txt, old, new)
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
