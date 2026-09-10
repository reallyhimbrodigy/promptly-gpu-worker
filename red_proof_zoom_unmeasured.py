#!/usr/bin/env python3
"""RED proof: 'unmeasured' must not quietly become 'always passes'.

Removing a gate and making a gate always-pass look identical from outside and
are opposite mistakes. Each mutation restores one of them.
"""
import ast
import os
import shutil
import subprocess
import sys

APP = "agentic_editor_app.py"
_ORIG_SRC = {}   # IN MEMORY, never a file
_ORIG_SRC.setdefault(APP, open(APP, encoding="utf-8").read())
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
    _mutant = src.replace(old, new, 1)
    # A MUTANT THAT DOES NOT PARSE NEVER RAN. The check then fails for a reason
    # unrelated to the property under test, which is a pass it did not earn.
    # None of the other guards see it: the anchor matched, the match was code.
    try:
        ast.parse(_mutant)
    except SyntaxError as _se:
        print(f"  HARNESS FAILURE [{label}] mutant does not parse: {_se.msg} "
              f"(line {_se.lineno}) — it never ran, so it proved nothing")
        return False
    open(APP, "w", encoding="utf-8").write(_mutant)
    rc, out = run()
    open(APP, "w", encoding="utf-8").write(_ORIG_SRC[APP])
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
# A HARNESS WITH NO LEGS MUST NOT EXIT 0. all([]) is True and 0 == 0 is
# True, so every red proof in this repo reported success on an empty leg
# list — the empty-set rule, sixteen times, inside the instruments built
# to catch exactly this. A suite PASS has to mean "ran and passed", not
# "did not run".
sys.exit(0 if r and all(r) and rc == 0 else 1)
