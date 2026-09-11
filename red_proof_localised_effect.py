#!/usr/bin/env python3
"""RED proof for the localised effect measure."""
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
    r = subprocess.run([sys.executable, "smoke_localised_effect.py"],
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
# A HARNESS WITH NO LEGS MUST NOT EXIT 0. all([]) is True and 0 == 0 is
# True, so every red proof in this repo reported success on an empty leg
# list — the empty-set rule, sixteen times, inside the instruments built
# to catch exactly this. A suite PASS has to mean "ran and passed", not
# "did not run".
sys.exit(0 if r and all(r) and rc == 0 else 1)
