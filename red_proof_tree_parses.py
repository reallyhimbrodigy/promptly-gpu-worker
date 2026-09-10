#!/usr/bin/env python3
"""RED proof for smoke_tree_parses.py. Both legs, on a real tracked file.

The mutations reproduce the ACTUAL defect — the three-way stash-pop block that
ff9311f committed into handler.py — rather than a synthetic broken file, so the
proof shows the check catching the thing that happened, in the state it
happened in.
"""
import ast
import pathlib
import subprocess
import sys

SMOKE = pathlib.Path("smoke_tree_parses.py")
TARGET = pathlib.Path("handler.py")          # a tracked file the check scans
ORIG = TARGET.read_text()


def run():
    r = subprocess.run([sys.executable, str(SMOKE)], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


rc, out = run()
if rc != 0:
    print("BASELINE IS NOT GREEN — nothing below means anything:\n" + out)
    sys.exit(2)
print("baseline: PASS\n")

# The real block, verbatim in shape: markers AND a syntax error together, which
# is what a stash-pop leaves behind.
_REAL = ('<<<<<<< Updated upstream\n'
         '        ("browser_launch", ("Failed to launch",\n'
         '=======\n'
         '        ("browser_launch", ("chrome", "Chromium",\n'
         '>>>>>>> Stashed changes\n')

MUTATIONS = [
    ("a stash-pop conflict block is committed (markers + SyntaxError)",
     _REAL, ("CONFLICT MARKERS", "DOES NOT PARSE")),
    # MARKERS WITHOUT A SYNTAX ERROR. Inside a string literal the file still
    # compiles, so this leg fires ONLY if the marker scan is real — it proves
    # the two legs are independent and neither is carrying the other. (The
    # first version of this mutation commented the markers out, which is not a
    # conflict at all: a real marker is always at line start, and the check is
    # right to ignore one that is not. The mutation was wrong, not the check.)
    ("markers at line start in a file that still parses",
     '_CONFLICT_DOC = """\n<<<<<<< Updated upstream\n=======\n>>>>>>> Stashed changes\n"""\n',
     ("CONFLICT MARKERS",)),
]

red, harness = 0, []
for label, block, expects in MUTATIONS:
    mutated = ORIG + "\n" + block
    if mutated == ORIG:
        harness.append(f"{label}: mutation was a no-op")
        print(f"  HARNESS FAILURE  {label}  :: nothing changed")
        continue
    # A MUTANT THAT DOES NOT PARSE NEVER RAN. Leg 1 here deliberately mutates
    # handler.py into something that does NOT parse — that IS the defect under
    # test — so this harness asserts the mutant is unparseable exactly when the
    # leg says it should be, rather than refusing every mutant that fails to
    # compile. The guard is the same question, asked with the expected answer
    # stated: "does this mutant compile, and did I mean it to?"
    _parses = True
    try:
        ast.parse(mutated)
    except SyntaxError:
        _parses = False
    if _parses is not ("DOES NOT PARSE" not in " ".join(expects)):
        harness.append(f"{label}: mutant parse state {_parses} contradicts the "
                       f"leg's own expectation")
        print(f"  HARNESS FAILURE  {label}  :: the mutant "
              f"{'parses' if _parses else 'does not parse'}, which contradicts "
              f"what this leg claims to be testing")
        continue
    TARGET.write_text(mutated)
    mrc, mout = run()
    TARGET.write_text(ORIG)
    if mrc == 0:
        print(f"  NOT RED          {label}  :: the mutant PASSED")
        harness.append(f"{label}: mutant passed")
    elif not all(e in mout for e in expects):
        print(f"  WRONG REASON     {label}  :: expected {expects}")
        harness.append(f"{label}: wrong reason")
    else:
        red += 1
        print(f"  RED              {label}\n"
              f"                   caught by: {', '.join(expects)}")

TARGET.write_text(ORIG)
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
