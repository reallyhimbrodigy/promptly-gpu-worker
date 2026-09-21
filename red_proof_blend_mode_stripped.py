#!/usr/bin/env python3
"""RED proof for smoke_blend_mode_stripped.py.

The mutations remove the acknowledgements that were genuinely missing an hour
ago — the gate found all three on its first run — so it is proven against the
state the repo was actually in, not an invented one.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_blend_mode_stripped.py")

MUTATIONS = [
    # DepthPull is the multiply case: a darkening layer becoming a covering one.
    ("depthpull_stops_saying_it", "port/bodies/DepthPull.jsx",
     " * CHATCUT STRIPS mixBlendMode, AND THIS COMPONENT HAS THE WORST CASE OF IT.",
     " * DepthPull applies a vignette and a glow.",
     "L3 multiply_users_acknowledged",
     lambda s: "CHATCUT STRIPS mixBlendMode" in s),
    # ShutterFlashOverlay is the menu case.
    ("menu_component_stops_saying_it", "port/bodies/ShutterFlashOverlay.jsx",
     " * CHATCUT STRIPS mixBlendMode, so the beam and the dot below composite",
     " * The beam and the dot below composite",
     "L1 every_user_names_the_strip",
     lambda s: "CHATCUT STRIPS mixBlendMode" in s),
    # The detector itself goes blind: with no body seen to declare a blend, the
    # population empties and every leg below would pass over nothing.
    ("detector_goes_blind", "smoke_blend_mode_stripped.py",
     "        modes = re.findall(r'mixBlendMode:\\s*\"([a-z-]+)\"', src)",
     "        modes = re.findall(r'mixBlendModeXX:\\s*\"([a-z-]+)\"', src)",
     "L0 population_nonempty",
     lambda s: "mixBlendMode:" in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def residue():
    p = subprocess.run(["git", "status", "--porcelain",
                        "port/bodies", "smoke_blend_mode_stripped.py"],
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
            print("  %-32s HARNESS FAILURE  anchor %dx in %s" % (name, n, target))
            continue
        if pre is not None and not pre(src):
            print("  %-32s HARNESS FAILURE  VACUOUS precondition" % name)
            continue
        mutant = src.replace(old, new, 1)
        try:
            if target.endswith(".py"):
                compile(mutant, path, "exec")
        except SyntaxError as e:
            print("  %-32s HARNESS FAILURE  mutant will not parse (%s)" % (name, e))
            continue
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
            print("     RESIDUE after %s: %r" % (name, r))
            return 2

    ok = bool(MUTATIONS) and red == len(MUTATIONS)
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
