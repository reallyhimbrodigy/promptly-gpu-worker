#!/usr/bin/env python3
"""RED proof for the three-state alpha instrument.

Each mutation restores a DIFFERENT half of the defect Builder-1 found on round
39, and each must turn smoke_alpha_not_empty RED. A check that has never failed
is not yet a check.
"""
import os
import shutil
import subprocess
import sys

APP = "agentic_editor_app.py"
SMOKE = "smoke_alpha_not_empty.py"
# BACKUP IN MEMORY, NEVER A FILE. This was `_ORIG_SRC = "/tmp/..."` — a FIXED
# PATH SHARED ACROSS EVERY BRANCH AND WORKTREE ON THIS MACHINE. Builder-2
# observed it silently restore ANOTHER BRANCH'S agentic_editor_app.py over
# their working copy: a 914-line diff, `git status` the only witness, and
# the harness printed 19/19 RED-proven about a file it had just replaced
# with a stranger.
#
# A per-branch filename does NOT fix it: the file still outlives the
# process and can be restored from after the tree moves under it. The
# backup must not survive the run that made it.
#
# THIRD SYMPTOM OF ONE DEFECT — a fixture outside the tree can be MISSING
# (dies at import, reports nothing), DRIFTED (anchor 0x), or STALE FROM
# ANOTHER BRANCH (this one, which reports SUCCESS while corrupting the
# file under test). The third is worst because it is silent AND green.
_ORIG_SRC = open(APP, encoding="utf-8").read()
None
env = dict(os.environ, PYTHONPATH=".")


def run():
    r = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def mut(old, new, label, expect):
    src = open(APP, encoding="utf-8").read()
    if src.count(old) != 1:
        print(f"  HARNESS FAILURE [{label}] anchor appears {src.count(old)}x")
        return False
    open(APP, "w", encoding="utf-8").write(src.replace(old, new, 1))
    rc, out = run()
    open(APP, "w", encoding="utf-8").write(_ORIG_SRC)
    ok = rc != 0 and expect in out
    print(f"  {'RED ok ' if ok else 'NOT RED'} [{label}] exit={rc}")
    if not ok:
        print("      expected %r in output" % expect)
    return ok


rc, out = run()
print(f"BASELINE exit={rc}")
assert rc == 0, out
r = []

# 1. THE HOLE ITSELF: the guard skips a failed measurement again.
r.append(mut(
    "        if _a_st == ALPHA_ABSENT:",
    "        if _reel_alpha is not None and False:",
    "the reel guard tests `is not None` again",
    "no guard tests alpha with `is not None` again"))

# 2. ABSENT collapses back into a number, so an alpha-less reel reads as content.
r.append(mut(
    '        return (ALPHA_ABSENT, None,',
    '        return (ALPHA_MEASURED, 4095.0,',
    "a stream with no alpha reports a confident number",
    "reads ABSENT, not a number"))

# 3. An unmeasurable layer stops failing the round.
r.append(mut(
    '    "alpha_layer_unmeasured",',
    '    "alpha_layer_unmeasured_RETIRED",',
    "an unmeasured layer no longer fails the round",
    "alpha_layer_unmeasured FAILS the round"))

# 4. The bar moves above real content, so a painted layer reads empty. Guards
#    the non-vacuity leg: without it, every state check could pass on a
#    threshold that calls everything blank.
r.append(mut(
    "_ALPHA_EMPTY_YMAX = 260.0",
    "_ALPHA_EMPTY_YMAX = 4000.0",
    "the bar rises above a painted layer",
    "a painted layer reads MEASURED and well above the bar"))

rc, out = run()
print(f"RESTORED exit={rc}")
print(f"\n{sum(r)}/{len(r)} RED-proven")
# A FLOOR, BECAUSE all([]) IS TRUE. A red proof whose mutation list is
# emptied — by a bad merge, a botched refactor, a commented-out block —
# reports SUCCESS. An instrument built to prove a check CAN FAIL,
# rendering its own absence as success. Found in 10 of 11 here and 16 of
# 16 on Builder-2's tree: 26 of 27 across both.
sys.exit(0 if r and all(r) and rc == 0 else 1)
