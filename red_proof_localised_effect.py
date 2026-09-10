#!/usr/bin/env python3
"""RED proof for the localised effect measure."""
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
    r = subprocess.run([sys.executable, "smoke_localised_effect.py"],
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

# 1. THE CROP ORDER — the bug that read 44.85 dB on a 9.45 dB region.
r.append(mut('        _c = "crop=%d:%d:%d:%d" % (_w, _h, _x, _y)',
             '        _c = "crop=%d:%d:%d:%d" % (_x, _y, _w, _h)',
             "crop is fed the box order instead of w:h:x:y",
             "crop is fed w, h, x, y"))

# 2. inf silently dropped — the cleanest control window becomes unmeasurable.
r.append(mut('    if ctrl_psnr == _inf and place_psnr == _inf:\n        return 0.0',
             '    if False:\n        return 0.0',
             "both-inf stops meaning 'nothing moved anywhere'",
             "both-inf is 'nothing moved anywhere'"))

# 3. EMPTY/UNMEASURED become a verdict — the false-failure class returning.
r.append(mut('                _rec["changed"] = None\n                _rec["region_verdict"] = _bx_st.upper()',
             '                _rec["changed"] = False\n                _rec["region_verdict"] = _bx_st.upper()',
             "an unanswered box reports INERT",
             "no branch reports an unanswered box as INERT"))

# 4. The bar moves outside the measured window.
r.append(mut("_REGION_EFFECT_BAR_DB = 6.0",
             "_REGION_EFFECT_BAR_DB = 25.0",
             "the bar rises above the worst real placement",
             "the bar separates every measured arm"))

# 5. The bar is centred rather than biased toward the tolerable error.
r.append(mut("_REGION_EFFECT_BAR_DB = 6.0",
             "_REGION_EFFECT_BAR_DB = 15.0",
             "the bar stops being biased toward the tolerable error",
             "biased LOW within the window"))

# 6. A family that paints a local overlay loses its layer and falls back to the
#    whole-frame average that produced the false failures.
r.append(mut('                                       layer=led.get("caption_mov"))',
             '                                       )',
             "the text placement stops passing its alpha layer",
             'the "text" placement passes its alpha layer'))

# 7. The box stops coming from the layer at all.
# A lambda keeps the mutant SYNTACTICALLY VALID while removing the call. The
# first version left a dangling `env=` inside a tuple, so the module died of a
# SyntaxError and a different leg reported — a mutation that breaks the module
# proves nothing about the check under test.
r.append(mut('            _bx_st, _bx, _bx_why = alpha_paint_box(',
             '            _bx_st, _bx, _bx_why = (lambda *a, **k: (ALPHA_BOX_MEASURED, (0, 0, 1080, 1920), ""))(',
             "the box becomes the whole frame again",
             "it asks the layer for the box"))

rc, out = run()
print(f"RESTORED exit={rc}")
print(f"\n{sum(r)}/{len(r)} RED-proven")
# A FLOOR, BECAUSE all([]) IS TRUE. A red proof whose mutation list is
# emptied — by a bad merge, a botched refactor, a commented-out block —
# reports SUCCESS. An instrument built to prove a check CAN FAIL,
# rendering its own absence as success. Found in 10 of 11 here and 16 of
# 16 on Builder-2's tree: 26 of 27 across both.
sys.exit(0 if r and all(r) and rc == 0 else 1)
