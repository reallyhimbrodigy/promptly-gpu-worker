#!/usr/bin/env python3
"""RED proof for smoke_encode_threads_pinned.py.

The check is QUARANTINED at a baseline of 13 known-unpinned sites, so the
property it actively enforces is that the set does not GROW. Mutation 1 adds a
fourteenth. Mutation 2 blinds the scan.

Both mutations run in a THROWAWAY WORKTREE — agentic_editor_app.py is a mounted
path and round 49 is live. A verification that can reach the tree a round runs
from is the hazard this repo spent the day on.
"""
import ast
import pathlib
import shutil
import subprocess
import sys
import tempfile

SMOKE = pathlib.Path("smoke_encode_threads_pinned.py").resolve()
_INJECTS = None

# THE MUTATIONS MOVED WHEN THE QUARANTINE CLOSED. They used to shift
# _BASELINE_UNPINNED, which tested a line being held. The check now enforces the
# PROPERTY — zero unpinned — so the mutation that matters is REMOVING A REAL PIN
# from the app. Re-anchoring rather than leaving mutations aimed at a constant
# that no longer exists: an anchor that stops matching is the first way a
# mutation stops mutating, and a fix is exactly where it happens.
MUTATIONS = [
    ("a real pin is removed from an encode (APP)",
     '"-c:v", "libx264", "-crf", "18", "-x264-params", f"threads={_X264_ENCODE_THREADS}", ',
     '"-c:v", "libx264", "-crf", "18", ',
     "every libx264 encode pins its thread count", _INJECTS),
    ("the scan stops finding encode sites (CHECK)",
     '"libx264" in _n.value',
     '"libx264_NOPE" in _n.value',
     "non-vacuity", _INJECTS),
]


def run(cwd):
    # RUN THE COPY IN THE WORKTREE, NOT THE ORIGINAL. SMOKE is an absolute path,
    # so the first version mutated the worktree's copy and then executed MY
    # branch's unmutated file — both mutations passed, and the tally said 0/2
    # with nothing wrong in either the check or the mutations. A mutation
    # applied to a file the run never opens is the plainest form of the
    # wrong-target family: the bytes changed, and not in the artifact under
    # test.
    r = subprocess.run([sys.executable, str(pathlib.Path(cwd) / SMOKE.name)],
                       cwd=cwd, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="encpin_")
_wt = str(pathlib.Path(_tmp) / "wt")
_made = subprocess.run(["git", "worktree", "add", "--detach", "-q", _wt, "HEAD"],
                       capture_output=True, text=True).returncode == 0
if not _made:
    print("could not create an isolated worktree"); sys.exit(2)
try:
    shutil.copy(SMOKE, pathlib.Path(_wt) / SMOKE.name)
    TARGET = pathlib.Path(_wt) / SMOKE.name
    ORIG = TARGET.read_text()
    rc, out = run(_wt)
    if rc != 0:
        print("BASELINE IS NOT GREEN — nothing below means anything:\n" + out)
        sys.exit(2)
    print("baseline: PASS (in an isolated worktree)\n")

    red, harness = 0, []
    for label, old, new, expect, precond in MUTATIONS:
        _tgt = (pathlib.Path(_wt) / "agentic_editor_app.py") if "(APP)" in label \
            else TARGET
        txt = _tgt.read_text()
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
        _restore = _tgt.read_text()
        _tgt.write_text(_mutant)
        mrc, mout = run(_wt)
        _tgt.write_text(_restore)
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
# A HARNESS WITH NO LEGS MUST NOT EXIT 0.
sys.exit(0 if red and red == len(MUTATIONS) and not harness else 1)
