#!/usr/bin/env python3
"""RED proof for judge_placements.py's self-test, in a throwaway worktree.

The file under mutation IS the file that runs — the self-test lives in the
judge. The mutations are the ways the sheet judges the wrong moment: a shared
boundary handed back to the beat that ENDS there (two thirds of real
placements), a beat end with a gap after it left unmatched, BUILT BUT NOT
RULED silenced, and the output clock passed off as the source clock.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

TARGET = "judge_placements.py"
_INJECTS = None
MUTATIONS = [
    ("a shared boundary goes back to the beat that ENDS there (closed interval, first match)",
     "        if _f(b.get(\"t_start\")) <= src_t < _f(b.get(\"t_end\")):\n            return b",
     "        if _f(b.get(\"t_start\")) <= src_t <= _f(b.get(\"t_end\")):\n            return b",
     "belongs to the beat that STARTS there", _INJECTS),
    ("a beat end with a gap after it is left unmatched",
     "        if abs(src_t - _f(b.get(\"t_end\"))) < 1e-6:\n            return b",
     "        if False:\n            return b",
     "belongs to the beat that ENDS there", _INJECTS),
    ("BUILT BUT NOT RULED is silenced",
     "            _unruled = not _match", "            _unruled = False",
     "BUILT BUT NOT RULED fired 0 time(s)", _INJECTS),
    ("the output clock is passed off as the source clock",
     "        if _f(t_out) <= _acc + _len:\n            return (MAPPED, _a + (_f(t_out) - _acc))",
     "        if _f(t_out) <= _acc + _len:\n            return (MAPPED, _f(t_out))",
     "maps into it", _INJECTS),
    ("the boundary snap is removed — a float 1e-16 below a beat start goes to the previous beat",
     "    src_t = round(float(src_t), 3)\n",
     "    src_t = float(src_t)\n",
     "a float 1e-16 below a beat start", _INJECTS),
    ("the executed rulings are ignored — the sheet judges against the rewritten record",
     '    for _v in (_exec_v if _vsrc == "EXECUTED" else (led.get("beat_verdicts") or [])):',
     '    for _v in (led.get("beat_verdicts") or []):',
     "executed_verdicts must be read", _INJECTS),
    ("t_moment is ignored — a card resolves on its render start, one beat early",
     '        _t = p.get("t_moment") if p.get("t_moment") is not None else p.get("t_start")',
     '        _t = p.get("t_start")',
     "must resolve to beat 1 via the moment", _INJECTS),
    ("an instant past the kept material is clamped instead of refused",
     "    # past the end of the kept material: report rather than clamp\n    return (UNMAPPED, None)",
     "    # past the end of the kept material: report rather than clamp\n    return (MAPPED, _acc)",
     "is UNMAPPED", _INJECTS),
]


def run(wt):
    r = subprocess.run([sys.executable, TARGET], cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="jp_")
_wt = str(pathlib.Path(_tmp) / "wt")
if subprocess.run(["git", "worktree", "add", "--detach", "-q", _wt, "HEAD"],
                  capture_output=True).returncode != 0:
    print("no isolated worktree"); sys.exit(2)
red, harness = 0, []
try:
    APP = pathlib.Path(_wt) / TARGET
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
            print(f"  WRONG REASON     {label}  :: expected '{expect}'\n{mout[-400:]}")
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
