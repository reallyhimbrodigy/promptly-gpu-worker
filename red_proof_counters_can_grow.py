#!/usr/bin/env python3
"""RED proof for smoke_counters_can_grow.py, in a throwaway worktree.

A positive control first: plant the phantom shape back into the app and confirm
the UNMUTATED gate rejects it. Then the mutations — the detector blinded, the
container comparison dropped (which is what made its first version flag an
ordinary read), and the census requirements gutted.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

import red_proof_anchor

SMOKE = pathlib.Path("smoke_counters_can_grow.py").resolve()
CENSUS = pathlib.Path("zero_counters_census.md").resolve()
APPNAME = "agentic_editor_app.py"
_INJECTS = None
MUTATIONS = [
    ("the self-assignment detector is blinded",
     "        _phantom.append((_n.lineno, _k))", "        pass",
     "no ledger key is assigned from its own", None),
    ("the container comparison is dropped, so an ordinary read reads as a phantom",
     "            and ast.unparse(_v.func.value) == _tgt_obj):",
     "            and True):",
     "no ledger key is assigned from its own", None),
    ("the census is no longer required to name every counter",
     '    check("every always-zero counter from the census is named in it",\n'
     '          not _missing,',
     '    check("every always-zero counter from the census is named in it",\n'
     '          True,',
     "named in it", None),
    ("the census may drop its denominator",
     '    check("and it states the denominator it was taken over",\n'
     '          "28 ledger" in _txt and "rounds 51-60" in _txt)',
     '    check("and it states the denominator it was taken over", True)',
     "states the denominator", None),
    ("the phantom may be removed quietly instead of recorded FIXED",
     '    check("the phantom is recorded as FIXED rather than quietly removed",\n'
     '          "skill_gate_blocks" in _txt and "FIXED" in _txt)',
     '    check("the phantom is recorded as FIXED rather than quietly removed", True)',
     "recorded as FIXED", None),
]
SMOKE_MUTATIONS = set(range(len(MUTATIONS)))


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="ctr_")
_wt = str(pathlib.Path(_tmp) / "wt")
if subprocess.run(["git", "worktree", "add", "--detach", "-q", _wt, "HEAD"],
                  capture_output=True).returncode != 0:
    print("no isolated worktree"); sys.exit(2)
red, harness = 0, []
try:
    shutil.copy(SMOKE, pathlib.Path(_wt) / SMOKE.name)
    SMK = pathlib.Path(_wt) / SMOKE.name
    APP = pathlib.Path(_wt) / APPNAME
    ORIG_SMK, ORIG_APP = SMK.read_text(), APP.read_text()
    rc, out = run(_wt)
    if rc != 0:
        print("BASELINE IS NOT GREEN:\n" + out[-1500:]); sys.exit(2)
    print("baseline: PASS (isolated worktree)\n")

    # POSITIVE CONTROL: put the real phantom shape back and confirm the
    # unmutated gate rejects it. Without this, every mutation below could be
    # passing against a gate that has never seen an offender.
    _mode, _planted = red_proof_anchor.apply_one(
        ORIG_APP, '    led["inputs"] = _inputs',
        '    led["phantom_probe"] = led.get("phantom_probe", 0)\n    led["inputs"] = _inputs')
    if _planted is None:
        harness.append("positive control: could not plant the phantom (%s)" % _mode)
        print("  HARNESS FAILURE  positive control  :: anchor %s" % _mode)
    else:
        APP.write_text(_planted)
        _prc, _pout = run(_wt)
        APP.write_text(ORIG_APP)
        if _prc == 0:
            harness.append("positive control: the gate did not catch a planted phantom")
            print("  POSITIVE CONTROL FAILED: the unmutated gate did NOT catch "
                  "a planted self-assignment, so nothing below proves anything")
        else:
            print("  positive control: the unmutated gate CAUGHT a planted "
                  "self-assigned counter\n")

    for i, (label, old, new, expect, precond) in enumerate(MUTATIONS):
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
        SMK.write_text(_m)
        # the first two need an offender present to have anything to miss
        if i in (0, 1) and _planted is not None:
            APP.write_text(_planted)
        mrc, mout = run(_wt)
        SMK.write_text(ORIG_SMK); APP.write_text(ORIG_APP)
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
