#!/usr/bin/env python3
"""RED proof for smoke_proof_frame_recorded.py.

The first mutation is the one that matters: it moves DipToBlack's proof frame
TO the dip. That satisfies "a proof frame exists" while proving nothing at all,
which is exactly the failure the ruling exists to prevent — and it is the shape
a well-meaning edit would take.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_proof_frame_recorded.py")

MUTATIONS = [
    ("proof_frame_moved_to_the_dip", "measured/inventory_stills.json",
     '"progress": 0.25,\n          "expected_plate_opacity": 0.9043',
     '"progress": 0.5,\n          "expected_plate_opacity": 0.9043',
     "L2 proof_frame_is_not_the_dip",
     lambda s: '"progress": 0.25' in s),
    ("control_no_longer_named", "measured/inventory_stills.json",
     '"against": "the same frame with the transition absent — a passthrough at full plate opacity"',
     '"against_REMOVED": "the same frame with the transition absent — a passthrough at full plate opacity"',
     "L3 proof_frame_names_its_control",
     lambda s: '"against": "the same frame with the transition absent' in s),
    ("expected_value_is_indistinguishable", "measured/inventory_stills.json",
     '"expected_plate_opacity": 0.9043',
     '"expected_plate_opacity": 0.999',
     "L4 recorded_values_are_separable",
     lambda s: '"expected_plate_opacity": 0.9043' in s),
    # The family derivation goes blind: with nothing detected, every leg below
    # iterates an empty list and the whole gate would pass while covering
    # nothing. L0 is the floor that stops it.
    ("family_derivation_goes_blind", "smoke_proof_frame_recorded.py",
     'if not re.search(r\'backgroundColor:\\s*"#(?:000000|000)"\', src):',
     'if not re.search(r\'backgroundColor:\\s*"#(?:NOSUCHCOLOUR)"\', src):',
     "L0 family_nonempty",
     lambda s: '#(?:000000|000)' in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def residue():
    p = subprocess.run(["git", "status", "--porcelain",
                        "measured/inventory_stills.json", "smoke_proof_frame_recorded.py"],
                       cwd=HERE, capture_output=True, text=True)
    return p.stdout.strip()


def main():
    base = residue()
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-1200:])
        return 2
    print("baseline green.\n")

    red = 0
    for name, target, old, new, phrase, pre in MUTATIONS:
        path = os.path.join(HERE, target)
        src = open(path, encoding="utf-8").read()
        n = src.count(old)
        if n != 1:
            print("  %-36s HARNESS FAILURE  anchor %dx in %s" % (name, n, target))
            continue
        if pre is not None and not pre(src):
            print("  %-36s HARNESS FAILURE  VACUOUS precondition" % name)
            continue
        mutant = src.replace(old, new, 1)
        try:
            if target.endswith(".json"):
                json.loads(mutant)
            elif target.endswith(".py"):
                compile(mutant, path, "exec")
        except (SyntaxError, ValueError) as e:
            print("  %-36s HARNESS FAILURE  mutant will not parse (%s)" % (name, e))
            continue
        open(path, "w", encoding="utf-8").write(mutant)
        try:
            mrc, mout = run_smoke()
        finally:
            open(path, "w", encoding="utf-8").write(src)
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        ok = mrc != 0 and fired
        print("  %-36s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
        if ok:
            red += 1
        r = residue()
        if r != base:
            print("     RESIDUE after %s: %r" % (name, r))
            return 2

    ok = bool(MUTATIONS) and red == len(MUTATIONS)
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
