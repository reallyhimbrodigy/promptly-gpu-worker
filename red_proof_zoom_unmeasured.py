#!/usr/bin/env python3
"""RED proof: 'unmeasured' must not quietly become 'always passes'.

Removing a gate and making a gate always-pass look identical from outside and
are opposite mistakes. Each mutation restores one of them.
"""
import os
import shutil
import subprocess
import sys

APP = "agentic_editor_app.py"
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
    r = subprocess.run([sys.executable, "smoke_zoom_wired.py"],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def mut(old, new, label, expect):
    src = open(APP, encoding="utf-8").read()
    if src.count(old) != 1:
        print(f"  HARNESS FAILURE [{label}] anchor {src.count(old)}x")
        return False
    open(APP, "w", encoding="utf-8").write(src.replace(old, new, 1))
    rc, out = run()
    open(APP, "w", encoding="utf-8").write(_ORIG_SRC)
    ok = rc != 0 and expect in out
    print(f"  {'RED ok ' if ok else 'NOT RED'} [{label}] exit={rc}")
    if not ok:
        print(f"      expected {expect!r}")
    return ok


rc, out = run()
print(f"BASELINE exit={rc}")
assert rc == 0, out
r = []

# 1. UNMEASURED silently becomes PASSED — the mistake this ruling exists to
#    avoid, and the one that looks like success in every report.
r.append(mut('                _sg["geometry_ok"] = None',
             '                _sg["geometry_ok"] = True',
             "unmeasured becomes an unearned PASS",
             "geometry_ok is set to None, not True"))

# 2. A bar comes back and refuses again.
r.append(mut('                _sg["geometry_verdict"] = "UNMEASURED"',
             '                if _gd is not None and _gd <= -8.0:\n'
             '                    fail("zoom_not_applied", "back")\n'
             '                _sg["geometry_verdict"] = "UNMEASURED"',
             "a bar returns and refuses on geometry",
             "nothing fails a round on zoom geometry"))

# 3. The name returns to CONTRACT_FAILURES without a producer — the
#    card_props_mismatch defect, recreated.
r.append(mut('    "render_frames_mismatch",',
             '    "zoom_not_applied",\n    "render_frames_mismatch",',
             "the failure name returns with no producer",
             "zoom_not_applied is gone from CONTRACT_FAILURES"))

# 4. The count stops being PRINTED — an absence nobody prints reads green.
# Keeps the parens balanced — commenting only the first line of a multi-line
# print leaves its continuation dangling, which is a SyntaxError and fires a
# DIFFERENT leg. A mutation that breaks the module proves nothing about the
# check under test.
r.append(mut('        print(f"  ZOOM GEOMETRY   : {_zgu} placement(s) UNMEASURED',
             '        _unprinted = (f"  ZOOM GEOMETRY  : {_zgu} placement(s) UNMEASURED',
             "the unmeasured count stops being printed",
             "PRINTED in the same commit"))

rc, out = run()
print(f"RESTORED exit={rc}")
print(f"\n{sum(r)}/{len(r)} RED-proven")
# A FLOOR, BECAUSE all([]) IS TRUE. A red proof whose mutation list is
# emptied — by a bad merge, a botched refactor, a commented-out block —
# reports SUCCESS. An instrument built to prove a check CAN FAIL,
# rendering its own absence as success. Found in 10 of 11 here and 16 of
# 16 on Builder-2's tree: 26 of 27 across both.
sys.exit(0 if r and all(r) and rc == 0 else 1)
