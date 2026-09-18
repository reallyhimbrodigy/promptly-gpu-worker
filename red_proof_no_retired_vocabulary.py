#!/usr/bin/env python3
"""RED PROOF for smoke_no_retired_vocabulary: a dead mechanism written back
into a surface the agent reads must turn the gate red — one surface per class
(the built system prompt, the loop constant, a knowledge document)."""
import ast
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_no_retired_vocabulary.py")
APP = os.path.join(HERE, "chatcut_job_app.py")
DOC = os.path.join(HERE, "knowledge", "03_captions.md")

MUTATIONS = [
    ("the system prompt asks for a DONE mark again", APP,
     '"You write no files. The record is read back from the timeline; the "',
     '"Write /work/DONE when you have placed. The record is read back from the timeline; the "',
     "system.md (build_system_prompt)"),
    ("the loop paragraph asks for the record file again", APP,
     '"YOU DO NOT EXPORT and you write no files. The harness reads the timeline "',
     '"YOU DO NOT EXPORT; write rulings.json first. The harness reads the timeline "',
     "const TWO_TURN_LOOP"),
    ("a knowledge document describes the old pipeline again", DOC,
     "", "\n\nWhen captions are on, write /work/DONE2 and run ffmpeg to tile the frames.\n",
     "doc knowledge/03_captions.md"),
]


def run():
    r = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


ORIG = {}


def main():
    ORIG[APP] = io.open(APP, encoding="utf-8").read()
    ORIG[DOC] = io.open(DOC, encoding="utf-8").read()
    rc, out = run()
    if rc != 0:
        print("HARNESS FAILURE: the unmutated gate is not green (rc=%d)\n%s" % (rc, out[-800:]))
        sys.exit(2)
    red = 0
    for label, path, old, new, phrase in MUTATIONS:
        src = io.open(path, encoding="utf-8").read()
        if old:
            if src.count(old) != 1:
                print("HARNESS FAILURE: %s — anchor %dx" % (label, src.count(old)))
                sys.exit(2)
            mutant = src.replace(old, new)
        else:
            mutant = src + new
        if path.endswith(".py"):
            try:
                ast.parse(mutant)
            except SyntaxError as e:
                print("HARNESS FAILURE: %s — mutant will not parse: %s" % (label, e))
                sys.exit(2)
        io.open(path, "w", encoding="utf-8").write(mutant)
        try:
            rc2, out2 = run()
        finally:
            io.open(path, "w", encoding="utf-8").write(src)
        hit = rc2 == 1 and ("[RETIRED] %s" % phrase) in out2
        print("  [%s] %s (rc=%d, names the surface=%s)" % ("RED" if hit else "NOT RED", label, rc2, ("[RETIRED] %s" % phrase) in out2))
        red += 1 if hit else 0
    # THE TREE AFTER: a killed run leaves the mutant on disk; say which file.
    residue = [p for p, keep in ((APP, ORIG[APP]), (DOC, ORIG[DOC])) if io.open(p, encoding="utf-8").read() != keep]
    for p in residue:
        io.open(p, "w", encoding="utf-8").write(ORIG[p])
        print("RESIDUE: %s left mutated — restored" % os.path.relpath(p, HERE))
    print("%d/%d RED-proven" % (red, len(MUTATIONS)))
    sys.exit(0 if red and red == len(MUTATIONS) and not residue else 1)


if __name__ == "__main__":
    main()          # the predicate above is the file's LAST sys.exit, as the guard reads it
