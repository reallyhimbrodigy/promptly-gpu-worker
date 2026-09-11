#!/usr/bin/env python3
"""RED proof for smoke_legs_are_unambiguous.py, in a throwaway worktree.

The mutations are the ways the ratchet stops ratcheting: a NEW ambiguous leg
written after the baseline, the baseline treated as an allowlist for anything,
the baseline growing silently, and the `In`/`NotIn` distinction collapsing.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

import red_proof_anchor

SMOKE = pathlib.Path("smoke_legs_are_unambiguous.py").resolve()
BASE = pathlib.Path("legs_ambiguous_baseline.json").resolve()
# A leg added to THIS file's own target: a fresh smoke that tests an ambiguous
# literal. The gate must fail on it even though the baseline exists.
VICTIM = "smoke_zz_red_proof_victim.py"
_INJECTS = None
MUTATIONS = [
    ("a NEW ambiguous leg is accepted because a baseline exists",
     "_new = [r for r in _amb if (r[0], r[2]) not in _base]",
     "_new = []",
     "no NEW source-presence leg", _INJECTS),
    ("the baseline is allowed to grow",
     'check("the baseline has not grown", len(_amb) <= len(_base) or not _base,',
     'check("the baseline has not grown", True,',
     "baseline has not grown", _INJECTS),
    ("the In/NotIn distinction collapses, so absence legs read as presence legs",
     "if isinstance(_node.ops[0], ast.In) and _count > 1:",
     "if _count > 1:",
     "no NEW source-presence leg", _INJECTS),
    ("a missing baseline is treated as a clean slate",
     'check("the baseline file exists", False,',
     'check("the baseline file exists", True,',
     "baseline file exists", None),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="legs_")
_wt = str(pathlib.Path(_tmp) / "wt")
if subprocess.run(["git", "worktree", "add", "--detach", "-q", _wt, "HEAD"],
                  capture_output=True).returncode != 0:
    print("no isolated worktree"); sys.exit(2)
red, harness = 0, []
try:
    shutil.copy(SMOKE, pathlib.Path(_wt) / SMOKE.name)
    shutil.copy(BASE, pathlib.Path(_wt) / BASE.name)
    SMK = pathlib.Path(_wt) / SMOKE.name
    BSE = pathlib.Path(_wt) / BASE.name
    ORIG_SMK, ORIG_BSE = SMK.read_text(), BSE.read_text()
    rc, out = run(_wt)
    if rc != 0:
        print("BASELINE IS NOT GREEN:\n" + out[-1500:]); sys.exit(2)
    print("baseline: PASS (isolated worktree)\n")

    # FIRST, THE POSITIVE CONTROL. Drop in a smoke with a genuinely ambiguous
    # leg and confirm the UNMUTATED gate catches it. Without this the four
    # mutations below could all be passing for the wrong reason — a gate that
    # never sees an offender cannot be shown to reject one.
    _v = pathlib.Path(_wt) / VICTIM
    _v.write_text('import pathlib\n'
                  'src = pathlib.Path("agentic_editor_app.py").read_text()\n'
                  'assert "credit_charged\\": False" in src\n'
                  'assert "region_bar_separation" in src\n')
    _vrc, _vout = run(_wt)
    if _vrc == 0:
        print("  POSITIVE CONTROL FAILED: the unmutated gate did NOT catch a "
              "new ambiguous leg, so nothing below proves anything")
        harness.append("positive control: gate did not catch a planted leg")
    else:
        print("  positive control: the unmutated gate CAUGHT a planted "
              "ambiguous leg\n")

    for label, old, new, expect, precond in MUTATIONS:
        _mode, _m = red_proof_anchor.apply_one(SMK.read_text(), old, new)
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
        if label.startswith("a missing baseline"):
            BSE.unlink(missing_ok=True)
        SMK.write_text(_m); mrc, mout = run(_wt)
        SMK.write_text(ORIG_SMK); BSE.write_text(ORIG_BSE)
        # the planted victim stays: the gate must still reject it
        if mrc == 0:
            print(f"  NOT RED          {label}  :: the mutant PASSED")
            harness.append(f"{label}: mutant passed")
        elif expect not in mout:
            print(f"  WRONG REASON     {label}  :: expected '{expect}'")
            harness.append(f"{label}: wrong reason")
        else:
            red += 1
            print(f"  RED              {label}\n                   caught by: {expect}")
    _v.unlink(missing_ok=True)
    frc, _ = run(_wt)
    print(f"\nRESTORED exit={frc}")
finally:
    subprocess.run(["git", "worktree", "remove", "--force", _wt], capture_output=True)
    shutil.rmtree(_tmp, ignore_errors=True)
    print(f"isolated worktree removed: {not pathlib.Path(_wt).exists()}")
print(f"{red}/{len(MUTATIONS)} RED-proven"
      + (f"   HARNESS FAILURES: {harness}" if harness else ""))
sys.exit(0 if red and red == len(MUTATIONS) and not harness else 1)
