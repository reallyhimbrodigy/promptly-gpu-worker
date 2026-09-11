#!/usr/bin/env python3
"""RED proof for smoke_red_proofs_guarded.py.

It mutates a REAL harness — removing the guard the way a careless edit would —
rather than a synthetic file, so the check is shown catching the thing that
would actually happen: someone adds a new red proof by copying an old one from
before the rule, or strips the try/except while tidying.
"""
import ast
import pathlib
import shutil
import subprocess
import sys

SMOKE = pathlib.Path("smoke_red_proofs_guarded.py")
TARGET = pathlib.Path("red_proof_alpha_state.py")
# IN MEMORY, NEVER A FILE. A fixed /tmp backup is shared across every
# branch and worktree on the machine, and restoring from a stale one
# silently replaces the file under test with another branch's copy.
_ORIG_TARGET = TARGET.read_text()
ORIG = TARGET.read_text()


def run():
    r = subprocess.run([sys.executable, str(SMOKE)], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


MUTATIONS = [
    ("the guard is removed from a harness entirely",
     '''    try:
        ast.parse(_mutant)
    except SyntaxError as _se:
        print(f"  HARNESS FAILURE [{label}] mutant does not parse: {_se.msg} "
              f"(line {_se.lineno}) — it never ran, so it proved nothing")
        return False
''', "", "refuses a mutant that will not parse"),
    ("the guard is present but its SyntaxError is not handled",
     '''    try:
        ast.parse(_mutant)
    except SyntaxError as _se:
        print(f"  HARNESS FAILURE [{label}] mutant does not parse: {_se.msg} "
              f"(line {_se.lineno}) — it never ran, so it proved nothing")
        return False
''', "    ast.parse(_mutant)\n", "refuses a mutant that will not parse"),
    # THE FLOOR. Removing it lets a harness with zero legs exit 0, which is
    # what every one of these did until today.
    ("the zero-legs floor is removed from a harness",
     "sys.exit(0 if r and all(r) and rc == 0 else 1)",
     "sys.exit(0 if all(r) and rc == 0 else 1)",
     "exit 0 with zero legs executed"),
    # THE EXTERNAL BACKUP. Reintroducing a /tmp backup path must fire.
    ("a source backup outside the tree comes back",
     "_ORIG_SRC = {}   # IN MEMORY, never a file",
     '_ORIG_SRC = {}\nBAK_PATH = "/tmp/_alpha_bak.py"',
     "backup outside the tree"),
]

rc, out = run()
if rc != 0:
    print("BASELINE IS NOT GREEN — nothing below means anything:\n" + out)
    sys.exit(2)
print("baseline: PASS\n")

red, harness = 0, []
for label, old, new, expect in MUTATIONS:
    txt = TARGET.read_text()
    n = txt.count(old)
    if n != 1:
        harness.append(f"{label}: anchor {n}x")
        print(f"  HARNESS FAILURE  {label}  :: anchor {n}x")
        continue
    _mutant = txt.replace(old, new, 1)
    try:
        ast.parse(_mutant)
    except SyntaxError as _se:
        harness.append(f"{label}: mutant does not parse")
        print(f"  HARNESS FAILURE  {label}  :: mutant does not parse ({_se.msg})")
        continue
    TARGET.write_text(_mutant)
    mrc, mout = run()
    TARGET.write_text(_ORIG_TARGET)
    if mrc == 0:
        print(f"  NOT RED          {label}  :: the mutant PASSED")
        harness.append(f"{label}: mutant passed")
    elif expect not in mout:
        print(f"  WRONG REASON     {label}  :: expected '{expect}'")
        harness.append(f"{label}: wrong reason")
    else:
        red += 1
        print(f"  RED              {label}\n                   caught by: {expect}")

TARGET.write_text(_ORIG_TARGET)
frc, _ = run()
print(f"\nRESTORED exit={frc}  target unchanged={TARGET.read_text() == ORIG}")
print(f"{red}/{len(MUTATIONS)} RED-proven"
      + (f"   HARNESS FAILURES: {harness}" if harness else ""))
# A HARNESS WITH NO LEGS MUST NOT EXIT 0. all([]) is True and 0 == 0 is
# True, so every red proof in this repo reported success on an empty leg
# list — the empty-set rule, sixteen times, inside the instruments built
# to catch exactly this. A suite PASS has to mean "ran and passed", not
# "did not run".
sys.exit(0 if red and red == len(MUTATIONS) and not harness and frc == 0 else 1)
