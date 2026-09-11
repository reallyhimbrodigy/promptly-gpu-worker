#!/usr/bin/env python3
"""RED proof for smoke_flag_never_guesses.py.

Mutation 1 restores the EXACT defect Builder-1 found — the silent-fold
predicate — rather than a synthetic break, so the proof shows the check
catching the thing that happened.

Both guards carried: mut() refuses an anchor that is not present exactly once,
and every mutation declares whether it can go semantically vacuous. All four
INJECT or RESTORE behaviour rather than weakening a filter whose operand might
be empty, so all four declare _INJECTS and say so — a precondition that is
always true teaches the next reader to skip the field.
"""
import ast
import pathlib
import subprocess
import sys

APP = pathlib.Path("agentic_editor_app.py")
SMOKE = pathlib.Path("smoke_flag_never_guesses.py")
ORIG = APP.read_text()
_INJECTS = None

MUTATIONS = [
    ("the silent-fold predicate returns (the original defect)",
     '''    _var = "PROMPTLY_DISABLE_" + name.upper()
    _raw = os.environ.get(_var)''',
     '''    return str(os.environ.get("PROMPTLY_DISABLE_" + name.upper(), "")).strip() != "1"
    _var = "PROMPTLY_DISABLE_" + name.upper()
    _raw = os.environ.get(_var)''',
     "raises rather than picking a side", _INJECTS),
    ("junk folds into ON instead of raising",
     '''    raise ValueError(
        "%s=%r is not a value I can read.''',
     '''    return True
    raise ValueError(
        "%s=%r is not a value I can read.''',
     "raises rather than picking a side", _INJECTS),
    ("the default becomes OFF instead of ON",
     '''    if _raw is None or str(_raw).strip() == "":
        return True''',
     '''    if _raw is None or str(_raw).strip() == "":
        return False''',
     "unset/blank", _INJECTS),
    # THE FIRST VERSION OF THIS MUTATION DID NOT MUTATE ANYTHING OBSERVABLE.
    # It rewrote the format string to "%s is not a value I can read. (%r)" and
    # still passed both _var and _raw, so the message still contained the
    # variable AND the repr and the leg still passed. Byte-different, and
    # information-identical. Not semantic vacuity in Builder-1's sense — the
    # anchor was fine and the operand non-empty — but the same family: I
    # changed the SHAPE of the thing while leaving the PROPERTY the check
    # tests. The mutation was wrong, not the check.
    ("the raise stops naming the value",
     '''    raise ValueError(
        "%s=%r is not a value I can read. Accepted: %s (on) / %s (off), "
        "case-insensitive, or unset for ON. Refusing to guess — a flag that "
        "picks a side quietly turns an ablation arm into a fabricated null."
        % (_var, _raw, "/".join(_FLAG_TRUE), "/".join(_FLAG_FALSE)))''',
     '''    raise ValueError("that flag value is not readable")''',
     "names the variable and the value", _INJECTS),
]


def run():
    r = subprocess.run([sys.executable, str(SMOKE)], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


rc, out = run()
if rc != 0:
    print("BASELINE IS NOT GREEN — nothing below means anything:\n" + out)
    sys.exit(2)
print("baseline: PASS\n")

red, harness = 0, []
for label, old, new, expect, precond in MUTATIONS:
    txt = APP.read_text()
    n = txt.count(old)
    if n != 1:
        harness.append(f"{label}: anchor {n}x (expected 1)")
        print(f"  HARNESS FAILURE  {label}  :: anchor {n}x")
        continue
    if precond is not None and not precond(txt):
        harness.append(f"{label}: VACUOUS — precondition false in this tree")
        print(f"  VACUOUS          {label}")
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
    APP.write_text(_mutant)
    mrc, mout = run()
    APP.write_text(ORIG)
    if mrc == 0:
        print(f"  NOT RED          {label}\n"
              f"                   the mutant PASSED. Precondition "
              f"{'held' if precond else 'n/a (injects)'}, so this is the check "
              f"being blind, not a vacuous edit")
        harness.append(f"{label}: mutant passed")
    elif expect not in mout:
        print(f"  WRONG REASON     {label}  :: expected '{expect}'")
        harness.append(f"{label}: wrong reason")
    else:
        red += 1
        print(f"  RED              {label}\n                   caught by: {expect}")

APP.write_text(ORIG)
frc, _ = run()
print(f"\nRESTORED exit={frc}")
print(f"{red}/{len(MUTATIONS)} RED-proven"
      + (f"   HARNESS FAILURES: {harness}" if harness else ""))
# A HARNESS WITH NO LEGS MUST NOT EXIT 0. all([]) is True and 0 == 0 is
# True, so every red proof in this repo reported success on an empty leg
# list — the empty-set rule, sixteen times, inside the instruments built
# to catch exactly this. A suite PASS has to mean "ran and passed", not
# "did not run".
sys.exit(0 if red and red == len(MUTATIONS) and not harness and frc == 0 else 1)
