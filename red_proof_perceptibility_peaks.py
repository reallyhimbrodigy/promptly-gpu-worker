#!/usr/bin/env python3
"""RED proof for smoke_perceptibility_peaks.py.

The first two mutations restore the two values this repo has already judged
wrong once — LightLeak's shipped 1.00 and the borrowed 0.82 — so the gate is
proven against the exact defects it exists for, not against invented ones.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_perceptibility_peaks.py")

MUTATIONS = [
    # WHAT ACTUALLY SHIPPED: fully opaque at the bloom, retaining 0.0719 —
    # worse than the 0.95 that was rejected as a blown exposure in June.
    ("lightleak_back_to_fully_opaque", "port/bodies/LightLeakOverlay.jsx",
     "[0, 0.71 * intensity, 0]", "[0, 1.0 * intensity, 0]",
     "L3 lightleak_l2_under_ceiling",
     lambda s: "0.71 * intensity" in s),
    # THE BORROW. It looks conservative and is not: 0.1402 against a 0.1822 bar.
    # This is the leg that makes "carried from another component" insufficient.
    ("lightleak_back_to_the_borrow", "port/bodies/LightLeakOverlay.jsx",
     "[0, 0.71 * intensity, 0]", "[0, 0.82 * intensity, 0]",
     "L4 shipped_value_clears_the_bar",
     lambda s: "0.71 * intensity" in s),
    # The label on ShutterFlash's property says "do not raise". A label is not
    # a gate; this is.
    # ANCHORED ON THE WHOLE BLOCK, NOT ON THE VALUE. `"defaultValue": 0.82`
    # occurs TWICE in this file — CardSwipe's `cardScale` is also 0.82, by
    # coincidence — and the single-line anchor was refused `anchor 2x` rather
    # than silently mutating the wrong property. A multi-line anchor is
    # normally the fragile choice; here it is the only unambiguous one, and the
    # count guard is what makes the trade visible instead of lucky.
    ("shutterflash_peak_raised", "port/transition_properties.json",
     '"label": "Peak wash opacity (0.82 measured \\u2014 do not raise)",\n'
     '   "type": "number",\n'
     '   "defaultValue": 0.82',
     '"label": "Peak wash opacity (0.82 measured \\u2014 do not raise)",\n'
     '   "type": "number",\n'
     '   "defaultValue": 0.95',
     "L2 shutterflash_peak_not_raised",
     lambda s: '"key": "peak"' in s),
    # THE INSTRUMENT ITSELF GOES BLIND. If the detail metric stops measuring
    # detail, every composite scores the same and the whole gate is decorative.
    # L0 separates a known-good from a known-rejected value for exactly this.
    ("detail_metric_goes_blind", "measure_perceptibility.py",
     "    return float(np.sqrt(np.mean((y - lo) ** 2)))",
     "    return float(np.sqrt(np.mean((y - y) ** 2)) + 1.0)",
     "L0 instrument_separates_known_pair",
     lambda s: "(y - lo) ** 2" in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def residue():
    p = subprocess.run(["git", "status", "--porcelain", "port", "measure_perceptibility.py"],
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
            # A MUTATED MODULE LEAVES A CACHED .pyc THAT OUTLIVES THE RESTORE.
            pyc = os.path.join(HERE, "__pycache__")
            if os.path.isdir(pyc):
                for f in os.listdir(pyc):
                    if f.startswith("measure_perceptibility"):
                        os.remove(os.path.join(pyc, f))
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
