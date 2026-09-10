#!/usr/bin/env python3
"""The residue check fires when a harness is killed mid-mutation.

THE CHECK-OF-THE-CHECK, AND IT BUILDS ITS OWN THROWAWAY WORKTREE TO RUN IN.
That is not fastidiousness; it is the entire lesson. On 2026-09-09 I ran a
mutating sweep to prove a tree was clean, and the sweep WAS the writer that made
it dirty — it left `led["cut_word_intrusions"] = []` on disk, one line in
12,000, in the measurement whose whole job is counting cut-word intrusions.
A verification that can reach the thing it verifies is not a verification.

An earlier draft of this file mutated the checkout it was run from. It restored
correctly — and if it had been killed halfway it would have left exactly the
residue it exists to detect, in whatever branch happened to be checked out.
Shipping that would have put the hazard into the repo under the name of the
check for it.

WHAT IT PROVES. A harness killed before it restores leaves the mutant on disk.
In-memory backups do not survive a SIGKILL, so NO relocation of the backup
reaches this failure mode — only a POST-RUN TREE CHECK does. The claim under
test is that the check actually fires, actually restores, stays silent on a
clean tree, and is sensitive at ONE LINE, which is the size the real incident
was.

Safe to run from any branch at any time: it touches nothing outside the
temporary worktree it creates and removes.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


_tmp = tempfile.mkdtemp(prefix="sweepcheck_")
_wt = str(pathlib.Path(_tmp) / "wt")
_made = False
try:
    _r = git("worktree", "add", "--detach", "-q", _wt, "HEAD")
    _made = _r.returncode == 0
    check("an isolated worktree can be created (nothing real is touched)", _made,
          (_r.stderr or "")[:200])
    if not _made:
        print("\nSWEEP-RESIDUE: FAIL"); sys.exit(1)

    APP = pathlib.Path(_wt) / "agentic_editor_app.py"

    def dirty():
        return git("status", "--porcelain", "--", "agentic_editor_app.py",
                   cwd=_wt).stdout.strip()

    def residue_check_and_restore():
        d = dirty()
        if d:
            git("checkout", "--", "agentic_editor_app.py", cwd=_wt)
        return bool(d)

    check("baseline: the isolated checkout is clean", not dirty(), dirty())
    _orig = APP.read_text()

    # 1. THE REAL DEFECT, reproduced: a harness killed mid-mutation.
    _anchor = 'led["cut_word_intrusions"] = cut_word_intrusions(spans, words)'
    check("the real defect's anchor exists here (non-vacuity)",
          _orig.count(_anchor) == 1,
          f"found {_orig.count(_anchor)}x — this test would prove nothing")
    APP.write_text(_orig.replace(_anchor, 'led["cut_word_intrusions"] = []', 1))
    check("a killed mutation leaves the tree DIRTY", bool(dirty()),
          "git saw nothing — the check has no signal to fire on")
    check("the residue check FIRES on it", residue_check_and_restore())
    check("and it RESTORES the file", APP.read_text() == _orig)
    check("the tree is clean afterwards", not dirty(), dirty())

    # 2. NON-VACUITY. A check that always fires is as useless as one that never
    #    does, and this repo has both on record.
    check("the check does NOT fire on a clean tree",
          not residue_check_and_restore(),
          "it reports residue when there is none — every run looks interrupted")

    # 3. SENSITIVITY AT ONE LINE, which is the size the real incident was. A
    #    check keyed on a diff summary or a size heuristic would miss it.
    APP.write_text(_orig.replace("        return True", "        return False", 1))
    check("a ONE-LINE mutant is detected", bool(dirty()))
    residue_check_and_restore()
    check("restored after the one-line case", APP.read_text() == _orig)
finally:
    if _made:
        git("worktree", "remove", "--force", _wt)
    shutil.rmtree(_tmp, ignore_errors=True)
    # PROVE THE CLEANUP, rather than assuming it: a verification that leaves a
    # worktree behind has littered the thing it promised not to touch.
    _left = pathlib.Path(_wt).exists()
    check("the throwaway worktree is removed", not _left, _wt)

print()
if fails:
    print("SWEEP-RESIDUE: FAIL")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("SWEEP-RESIDUE: PASS — fires on a killed mutation, restores the file, "
      "stays silent on a clean tree, catches a one-line mutant, and cleans up")
