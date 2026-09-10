#!/usr/bin/env python3
"""RED proof for smoke_source_duration_state.py. A check that has never failed
is not yet a check.

TWO GUARDS, because there are two ways a mutation stops being a mutation:

  ANCHOR DRIFT   `mut()` refuses to apply when the anchor does not appear
                 EXACTLY once, and reports `anchor Nx` rather than passing. A
                 refactor that hoists a string into a function orphans a
                 mutation silently otherwise.

  SEMANTIC VACUITY  the anchor matches, the edit applies, and the meaning does
                 not change. Builder-1 hit this on 2026-09-09: a mutation
                 removing an unbuildable-filter was a no-op once the filter's
                 input was empty, so the mutant was byte-different and
                 behaviourally identical and the proof read NOT RED with nothing
                 wrong. `count != 1` cannot see that. The defence here is that
                 each mutation declares the REASON it expects to be caught, and
                 a mutant that fails for a different reason — or passes — is
                 reported, not counted. That is not a general cure; it is the
                 narrowest thing that would have caught their instance and
                 mine.
"""
import ast
import pathlib
import subprocess
import sys

APP = pathlib.Path("agentic_editor_app.py")
SMOKE = pathlib.Path("smoke_source_duration_state.py")
ORIG_APP, ORIG_SMOKE = APP.read_text(), SMOKE.read_text()

# (label, file, old, new, expected substring of the failure, precondition)
#
# THE PRECONDITION IS THE SECOND VACUITY GUARD, and it is the one Builder-1's
# case needed. Their mutation REMOVED a filter to prove the filter filters —
# vacuous the day the filter's operand became empty, because removing an empty
# filter changes nothing. The anchor still matched and the edit still applied.
#
# The discriminator is cheap once named: a mutation that WEAKENS OR REMOVES
# something must first assert that thing currently DOES something. A mutation
# that INJECTS a defect cannot be vacuous in that way — the defect is new
# material — so it declares None and says so, rather than carrying a
# precondition that is always true and means nothing.
#
# A precondition is a callable over the UNMUTATED source, evaluated before the
# edit. When a mutant passes, this is what separates "the check is blind" from
# "the mutation was a no-op" — two diagnoses that look identical in a tally.
_INJECTS = None  # nothing to be vacuous about: the mutation adds new material

MUTATIONS = [
    ("laundering returns to the single read", APP,
     "_vdur_state, _vdur, _vdur_why = source_duration_state(meta)",
     '_vdur_state, _vdur_why = "MEASURED", "x"\n'
     '    _vdur = float(meta.get("format", {}).get("duration") or 0)',
     'no `.get("duration") or 0` anywhere', _INJECTS),
    ("laundering hides inside a str() wrapper", APP,
     "        _ds, dur, _dw = source_duration_state(meta)",
     '        _ds, _dw = "MEASURED", "x"\n'
     '        dur = float(str(meta.get("format", {}).get("duration") or 0))',
     'no `.get("duration") or 0` anywhere', _INJECTS),
    ("the raise guard is deleted", APP,
     "    if _vdur_state != SRC_DUR_MEASURED:\n        raise AssertionError(",
     "    if False:\n        raise AssertionError(",
     "guard dominates the first use",
     # WEAKENS a guard, so it must be non-vacuous: the guard has to exist and
     # be reachable in this tree, or deleting it proves nothing.
     lambda t: "if _vdur_state != SRC_DUR_MEASURED:" in t),
    ("a caller continues silently on non-MEASURED", APP,
     '        if _ds != SRC_DUR_MEASURED:\n'
     '            return {"error": f"source duration {_ds}: {_dw} — keep_spans cannot "',
     '        if _ds != SRC_DUR_MEASURED:\n'
     '            pass\n        if False:\n'
     '            return {"error": f"source duration {_ds}: {_dw} — keep_spans cannot "',
     "raises, returns or fails on non-MEASURED",
     lambda t: t.count("source_duration_state(") >= 4),
    ("ABSENT is reported as a measured zero", APP,
     '    return (SRC_DUR_ABSENT, None,\n'
     '            "no duration field in format or video stream"',
     '    return (SRC_DUR_MEASURED, 0.0,\n'
     '            "no duration field in format or video stream"',
     "probe returned {} -> ABSENT", _INJECTS),
    ("FAILED carries a number instead of None", APP,
     '        return (SRC_DUR_FAILED, None, "%s=%s is not a positive duration"',
     '        return (SRC_DUR_FAILED, 0.0, "%s=%s is not a positive duration"',
     "duration is zero -> FAILED", _INJECTS),
    ("a declared frame rate is used to fill the gap", APP,
     '    return (SRC_DUR_ABSENT, None,',
     '    if _vs.get("r_frame_rate"):\n'
     '        return (SRC_DUR_MEASURED, 1.0, "guessed from r_frame_rate")\n'
     '    return (SRC_DUR_ABSENT, None,',
     "declared frame rate is NOT read", _INJECTS),
]


def run():
    r = subprocess.run([sys.executable, str(SMOKE)], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def restore():
    APP.write_text(ORIG_APP)
    SMOKE.write_text(ORIG_SMOKE)


rc, out = run()
if rc != 0:
    print("BASELINE IS NOT GREEN — nothing below means anything:\n" + out)
    sys.exit(2)
print("baseline: PASS\n")

red, harness = 0, []
for label, path, old, new, expect, precond in MUTATIONS:
    txt = path.read_text()
    if precond is not None and not precond(txt):
        # VACUITY GUARD. The thing this mutation weakens does not currently do
        # anything, so weakening it cannot change behaviour. Refuse it; never
        # count it, and never let it read as NOT RED.
        harness.append(f"{label}: VACUOUS — precondition false in this tree")
        print(f"  VACUOUS          {label}  :: the target does nothing here, so "
              f"the mutation cannot change behaviour")
        continue
    n = txt.count(old)
    if n != 1:
        # THE ANCHOR GUARD. Refuse the mutation; never report a pass.
        harness.append(f"{label}: anchor {n}x (expected 1) — a refactor moved it")
        print(f"  HARNESS FAILURE  {label}  :: anchor {n}x")
        continue
    _mutant = txt.replace(old, new)
    # FOURTH WAY A MUTATION FAILS TO MUTATE: SYNTACTICALLY DEAD. (Builder-1,
    # 2026-09-09 — their mutant inserted a 4-space block before an 8-space
    # line.) A mutant that does not compile makes the check fail for a reason
    # unrelated to the property under test, and a check failing for the wrong
    # reason is a check reporting a pass it did not earn. The other guards are
    # all silent: the anchor matched, the operand was non-empty, the match was
    # in code.
    #
    #     anchor 0x             a refactor moved it     count guard
    #     operand is empty      the edit is a no-op     precondition
    #     match lands in prose  a comment now owns it   _match_is_prose
    #     mutant will not parse it never ran at all     THIS
    try:
        ast.parse(_mutant)
    except SyntaxError as _se:
        harness.append(f"{label}: mutant does not parse ({_se.msg})")
        print(f"  HARNESS FAILURE  {label}  :: the mutant does not parse "
              f"({_se.msg} at line {_se.lineno}) — it never ran, so it proved "
              f"nothing")
        continue
    path.write_text(_mutant)
    mrc, mout = run()
    restore()
    if mrc == 0:
        print(f"  NOT RED          {label}\n"
              f"                   the mutant PASSED. Precondition "
              f"{'held' if precond else 'n/a (injects)'}, so this is the check "
              f"being blind, not a vacuous edit")
        harness.append(f"{label}: mutant passed")
    elif expect not in mout:
        # SEMANTIC VACUITY / WRONG-REASON GUARD. It failed, but not for the
        # reason this mutation exists to provoke, so it proves something else.
        print(f"  WRONG REASON     {label}\n"
              f"                   failed without '{expect}' — this mutation is "
              f"not proving the leg it claims to")
        harness.append(f"{label}: failed for the wrong reason")
    else:
        red += 1
        print(f"  RED              {label}\n"
              f"                   caught by: {expect}")

restore()
frc, _ = run()
print(f"\nRESTORED exit={frc}")
print(f"{red}/{len(MUTATIONS)} RED-proven"
      + (f"   HARNESS FAILURES: {harness}" if harness else ""))
sys.exit(0 if red == len(MUTATIONS) and not harness and frc == 0 else 1)
