#!/usr/bin/env python3
"""RED proof for smoke_transition_covers_canvas.py.

Two mutations restore SlideOver's real, measured defect — the one the still at
f240 shows — and one removes the model's refusal, which is what stopped a wrong
number being reported about CardSwipe.

Backups in memory; the tree is checked for residue after every mutation.
Each mutation asserts the phrase its leg prints, because a crash and a caught
defect exit identically.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_transition_covers_canvas.py")

MUTATIONS = [
    # The real defect, restored: A drifts the way B arrives from and the root
    # shows through the strip it vacated. 22.33% at its worst.
    ("slideover_drifts_the_wrong_way", "port/bodies/SlideOver.jsx",
     "const translateA = lerp(e, 0, sign * 25);",
     "const translateA = lerp(e, 0, sign * -25);",
     "L1 no_root_showing_any_frame",
     lambda s: "sign * 25" in s),
    # The same defect on the other axis: A shrinking past full exposes a band
    # top and bottom for the whole middle of the move.
    ("slideover_shrinks_past_full", "port/bodies/SlideOver.jsx",
     "const scaleA = lerp(e, 1.09, 1.0);",
     "const scaleA = lerp(e, 1, 0.92);",
     "L1 no_root_showing_any_frame",
     lambda s: "lerp(e, 1.09, 1.0)" in s),
    # Remove the refusal and CardSwipe gets modelled as a horizontal pair it is
    # not, producing a confident 42.24% about geometry that does not exist.
    # This is the leg that stops a measurement of the wrong thing.
    ("model_stops_refusing", "smoke_transition_covers_canvas.py",
     '        if au != ("x", "%"):',
     '        if au is None:',
     "L1 no_root_showing_any_frame",
     lambda s: 'if au != ("x", "%"):' in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def residue():
    p = subprocess.run(["git", "status", "--porcelain",
                        "port/bodies", "smoke_transition_covers_canvas.py"],
                       cwd=HERE, capture_output=True, text=True)
    return p.stdout.strip()


def main():
    base = residue()
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-1200:]); return 2
    print("baseline green.\n")

    red = 0
    for name, target, old, new, phrase, pre in MUTATIONS:
        path = os.path.join(HERE, target)
        src = open(path, encoding="utf-8").read()
        n = src.count(old)
        if n != 1:
            print("  %-32s HARNESS FAILURE  anchor %dx in %s" % (name, n, target)); continue
        if pre is not None and not pre(src):
            print("  %-32s HARNESS FAILURE  VACUOUS precondition" % name); continue
        mutant = src.replace(old, new, 1)
        try:
            if target.endswith(".py"):
                compile(mutant, path, "exec")
            elif not mutant.strip():
                raise ValueError("mutant is empty")
        except (SyntaxError, ValueError) as e:
            print("  %-32s HARNESS FAILURE  mutant will not parse (%s)" % (name, e)); continue
        open(path, "w", encoding="utf-8").write(mutant)
        try:
            mrc, mout = run_smoke()
        finally:
            open(path, "w", encoding="utf-8").write(src)
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        ok = mrc != 0 and fired
        print("  %-32s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
        if ok:
            red += 1
        r = residue()
        if r != base:
            print("     RESIDUE after %s: %r" % (name, r)); return 2

    ok = bool(MUTATIONS) and red == len(MUTATIONS)
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
