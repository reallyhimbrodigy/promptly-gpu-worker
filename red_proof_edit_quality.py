#!/usr/bin/env python3
"""RED proof: the truncation cure, and the three edit-quality measures."""
import ast
import os, shutil, subprocess, sys
APP = "agentic_editor_app.py"; _ORIG_SRC = {}   # IN MEMORY, never a file
_ORIG_SRC.setdefault(APP, open(APP, encoding="utf-8").read())
env = dict(os.environ, PYTHONPATH=".")


def run():
    r = subprocess.run([sys.executable, "smoke_edit_quality.py"],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def mut(old, new, label, expect):
    src = open(APP, encoding="utf-8").read()
    if src.count(old) != 1:
        print(f"  HARNESS FAILURE [{label}] anchor {src.count(old)}x"); return False
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
    rc, out = run(); open(APP, "w", encoding="utf-8").write(_ORIG_SRC[APP])
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
# RETARGETED after the dedup rewrite removed the old anchor. The harness
# reported "anchor 0x" rather than counting it RED, which is the whole reason
# mut() checks the count — a mutation that no longer applies proves nothing, and
# a refactor is exactly where that happens.
r.append(mut('        if not _x.get("box"):\n            continue',
             '        _x = dict(_x, box=_x.get("box") or (0, 0, 1, 1))\n        if False:\n            continue',
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
# DERIVED FROM THE SOURCE, NOT FROM /tmp. These were two scratch files I wrote
# while authoring this mutation. They are long gone, so `open()` raised at
# IMPORT time and THE WHOLE HARNESS DIED — legs 1 through 13 never ran either,
# and this proof has been reporting nothing for as long as the files have been
# missing. A red proof that cannot run is a check that has stopped being a
# check while still sitting in the suite with a name that says otherwise.
#
# The block is now located by anchor and the mutant built by deleting its
# print() calls, so the mutation travels with the code it mutates.
_APPSRC = open(APP, encoding="utf-8").read()
_B0 = _APPSRC.index("        if _fl is None:\n")
_B1 = _APPSRC.index("   MEASURED, no threshold\")\n", _B0) + len("   MEASURED, no threshold\")\n")
_OLD_BLOCK = _APPSRC[_B0:_B1]
# Kill BOTH prints — the block has a MEASURED and an UNMEASURED branch and
# removing one leaves the other, which is why a single-print mutation could not
# fire. Replaced with a pass in each branch so the mutant still parses; the
# ast.parse guard would refuse it otherwise, which is the guard working.
_NEW_BLOCK = """        if _fl is None:
            pass
        else:
            _above = [x for x in _cwi if x.get("intrusion_ms", 0) > _fl]
            pass
"""
assert _OLD_BLOCK.count("print(") == 2, (
    "expected exactly two prints in the CUT INTRUSIONS block, found "
    f"{_OLD_BLOCK.count('print(')} — the block moved and this mutation would "
    "no longer be testing what it claims")
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

# 14. The dedup goes away and a placement collides with its own duplicate —
#     the round-45 artefact, which is bimodal and would justify a bar at 0.5.
r.append(mut('        if _k in _seen:\n            continue',
             '        if False:\n            continue',
             "a placement collides with its own duplicate record again",
             "the same placement recorded twice is NOT a collision"))
# 15. The dedup gets TOO BROAD and swallows real pairs that merely share a box.
r.append(mut('        _k = (_x.get("family"), round(float(_x.get("t0", 0)), 3),\n'
             '              round(float(_x.get("t1", 0)), 3), tuple(_x["box"]))',
             '        _k = (_x.get("family"), tuple(_x["box"]))',
             "the dedup key drops the time window and swallows real pairs",
             "a duplicate at a DIFFERENT time is still compared"))
# 16. The duplicate count stops being reported — the harness signal disappears.
r.append(mut('    led["painted_boxes_duplicate"] = len(_pb) - len(_uniq)',
             '    led["_painted_boxes_duplicate_unreported"] = len(_pb) - len(_uniq)',
             "the duplicate count stops being recorded",
             "duplicates are counted, not silently collapsed"))

# 17. The no-cards case goes silent again — round 45's actual behaviour.
# Neutralise the print CALL, since the check reads calls. `if False:` leaves the
# print in the source and the static check cannot see unreachability — a limit
# already stated for CUT INTRUSIONS and the same here.
r.append(mut('        print(f"  CARD ALIGNMENT  : NO CARDS PLACED"',
             '        _unprinted = (f"  CARD ALIGNMENT : NO-CARDS-PLACED"',
             "the no-cards case prints nothing again",
             "the no-cards case is PRINTED, not skipped"))
# 18. UNEXERCISED keys on "no failures" rather than "nothing could fail", so a
#     set of all-not-applicable cards reports as passing.
r.append(mut("                 if not _off and not _ung and _could_fail == 0 else \"\"))",
             "                 if not _off and not _ung and False else \"\"))",
             "UNEXERCISED stops keying on cards that could have failed",
             "UNEXERCISED keys on cards that could have failed"))

# 19. THE `or 0` IDIOM RETURNS on a denominator — Builder-1's paint_ms defect,
#     in my lines, on the numbers Zac asked me to report.
r.append(mut('        _tot = (r.get("ledger") or {}).get("cut_boundaries_total")\n'
             '        _tot_s = "?" if _tot is None else str(_tot)',
             '        _tot = (r.get("ledger") or {}).get("cut_boundaries_total") or 0\n'
             '        _tot_s = str(_tot)',
             "a never-written denominator prints as a measured zero again",
             "no measure I report uses"))
rc, out = run(); print(f"RESTORED exit={rc}")
print(f"\n{sum(r)}/{len(r)} RED-proven")
# A HARNESS WITH NO LEGS MUST NOT EXIT 0. all([]) is True and 0 == 0 is
# True, so every red proof in this repo reported success on an empty leg
# list — the empty-set rule, sixteen times, inside the instruments built
# to catch exactly this. A suite PASS has to mean "ran and passed", not
# "did not run".
sys.exit(0 if r and all(r) and rc == 0 else 1)
