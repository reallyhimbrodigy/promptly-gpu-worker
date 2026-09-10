#!/usr/bin/env python3
"""RED proof for smoke_tree_parses.py. Both legs, on a real tracked file.

The mutations reproduce the ACTUAL defect — the three-way stash-pop block that
ff9311f committed into handler.py — rather than a synthetic broken file, so the
proof shows the check catching the thing that happened, in the state it
happened in.
"""
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
# A FLOOR, BECAUSE all([]) IS TRUE. A red proof whose mutation list is
# emptied — by a bad merge, a botched refactor, a commented-out block —
# reports SUCCESS. An instrument built to prove a check CAN FAIL,
# rendering its own absence as success. Found in 10 of 11 here and 16 of
# 16 on Builder-2's tree: 26 of 27 across both.
sys.exit(0 if MUTATIONS and red == len(MUTATIONS) and not harness and frc == 0 else 1)
