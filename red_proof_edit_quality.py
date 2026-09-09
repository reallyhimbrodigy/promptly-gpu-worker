#!/usr/bin/env python3
"""RED proof: the truncation cure, and the three edit-quality measures."""
import os, shutil, subprocess, sys
APP = "agentic_editor_app.py"; BAK = "/tmp/_eq_bak.py"
shutil.copy(APP, BAK)
env = dict(os.environ, PYTHONPATH=".")


def run():
    r = subprocess.run([sys.executable, "smoke_edit_quality.py"],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def mut(old, new, label, expect):
    src = open(APP, encoding="utf-8").read()
    if src.count(old) != 1:
        print(f"  HARNESS FAILURE [{label}] anchor {src.count(old)}x"); return False
    open(APP, "w", encoding="utf-8").write(src.replace(old, new, 1))
    rc, out = run(); shutil.copy(BAK, APP)
    ok = rc != 0 and expect in out
    print(f"  {'RED ok ' if ok else 'NOT RED'} [{label}] exit={rc}")
    if not ok:
        print(f"      expected {expect!r}")
    return ok


rc, out = run(); print(f"BASELINE exit={rc}"); assert rc == 0, out
r = []

# 1. THE DEFECT ITSELF returns — round 43's three truncated fixtures.
r.append(mut('"[0:v][cap]overlay=0:0:eof_action=pass[outv]"',
             '"[0:v][cap]overlay=0:0:shortest=1[outv]"',
             "the caption composite truncates again",
             "no overlay filter uses shortest"))

# 2. THE HALF-FIX: shortest dropped, eof_action omitted — overlay then REPEATS
#    its last frame for the rest of the video, and every length check passes.
r.append(mut('"[0:v][cap]overlay=0:0:eof_action=pass[outv]"',
             '"[0:v][cap]overlay=0:0[outv]"',
             "shortest dropped but the cure omitted",
             "every ungated overlay declares eof_action=pass"))

# 3. A cut inside a word stops being reported.
r.append(mut("                if _ws < _t < _we:", "                if False:",
             "cuts inside words stop being reported",
             "a cut inside a word IS an intrusion"))

# 4. The intrusion depth becomes distance from the START rather than the
#    NEARER edge — a plausible-looking change that misreports every late cut.
r.append(mut("                            min(_t - _ws, _we - _t) * 1000.0)),",
             "                            (_t - _ws) * 1000.0)),",
             "intrusion is measured from the word start, not the nearer edge",
             "measures to the NEARER edge"))

# 5. A hero with no digits reports as UNGROUNDED rather than not-applicable.
r.append(mut("    if not _digits:\n        _grounded = None",
             "    if not _digits:\n        _grounded = False",
             "a non-numeric hero reads as ungrounded",
             "NOT APPLICABLE, not ungrounded"))

# 6. Collisions ignore time, so two placements that never coexist collide.
r.append(mut('            if float(_a["t1"]) <= float(_b["t0"]) or float(_b["t1"]) <= float(_a["t0"]):\n                continue',
             '            if False:\n                continue',
             "collision stops requiring a time overlap",
             "placements overlapping in time AND pixels collide"))

# 7. An unmeasured box is treated as a rectangle rather than skipped.
r.append(mut('    _p = [x for x in (placed or []) if x.get("box")]',
             '    _p = [dict(x, box=x.get("box") or (0, 0, 1, 1)) for x in (placed or [])]',
             "an unmeasured box becomes a rectangle at the origin",
             "skipped, not guessed"))

# 8-10. THE WIRING ITSELF — the defect that made all three produce nothing.
r.append(mut('        led["cut_word_intrusions"] = cut_word_intrusions(spans, words)',
             '        led["cut_word_intrusions"] = []',
             "cut_word_intrusions stops being called by the pipeline",
             "cut_word_intrusions is CALLED by the pipeline"))
r.append(mut('                card_beat_alignment({"anchor_s": _mg_at, "hero": hero}, b),',
             '                {},',
             "card_beat_alignment stops being called by the pipeline",
             "card_beat_alignment is CALLED by the pipeline"))
r.append(mut('    led["placement_collisions"] = placement_collisions(led.get("_painted_boxes") or [])',
             '    led["placement_collisions"] = []',
             "placement_collisions stops being called by the pipeline",
             "placement_collisions is CALLED by the pipeline"))
# 11. Measured and ledgered but never PRINTED — round 29's defect exactly.
# BOTH PRINTS, not one. The block has a MEASURED and an UNMEASURED branch and
# killing either leaves the other, so the single-print mutation could not fire.
# And `_cwi = None` cannot fire it either: the check is STATIC — it proves a
# print() carrying the label EXISTS, not that it executes. That limit is real
# and stated rather than papered over; what the check guards is "nobody wrote
# the print", which is the defect that actually happened.
_OLD_BLOCK = open("/tmp/block_old.txt").read()
_NEW_BLOCK = open("/tmp/block_new.txt").read()
r.append(mut(_OLD_BLOCK, _NEW_BLOCK,
             "neither branch prints the cut distribution",
             "CUT INTRUSIONS is PRINTED"))

# 12. THE DEFAULT RETURNS — a guessed floor, silently deciding which
#     intrusions are arithmetic.
r.append(mut('    if not _r and not _a:\n        return (None, "UNMEASURED", "no frame rate on the source stream")',
             '    if not _r and not _a:\n        return (16.67, "MEASURED", "assumed 30fps")',
             "a missing frame rate defaults to 30 again",
             "a missing frame rate is UNMEASURED, not 30"))
# 13. VFR stops being detected, so motion silently rejoins the pooled numbers
#     with one of two wrong floors.
r.append(mut("        if _spread > _CUT_FLOOR_VFR_TOLERANCE:",
             "        if False:",
             "a VFR source is given a floor anyway",
             "a VFR source has NO floor"))

rc, out = run(); print(f"RESTORED exit={rc}")
print(f"\n{sum(r)}/{len(r)} RED-proven")
sys.exit(0 if all(r) and rc == 0 else 1)
