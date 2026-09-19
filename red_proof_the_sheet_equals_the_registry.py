#!/usr/bin/env python3
"""RED PROOF: the sheet builder REFUSES rather than quietly shrinking the inventory.

THE DEFECT IT GUARDS (measured 2026-09-19). EndCard and NamePlate both RENDER — MEASURED by the same
method as every other component, own project, own empty frame, pixels diffed, 3.469% and 3.545% of the
frame — and were dropped from the sheet for having no WHEN heading in the knowledge file. The builder
PRINTED them and wrote the sheet anyway, so the registry said 37 components, the picture the agent picks
from said 35, and nothing reconciled the two. The agent was never shown either one.

The mutation removes one component's condition, the way deleting a heading or renaming a component in the
knowledge file would, and the proof asserts the builder REFUSES and NAMES the component it would have
dropped. A builder that merely printed it would pass a check that only read the exit code.
"""
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KNOW = os.path.join(HERE, "knowledge", "05_motion_graphics.md")
SHEET = os.path.join(HERE, "component_sheet.py")
DRIVE = """import sys, json, os
sys.path.insert(0, %r)
import component_sheet as CS
try:
    CS.build(%r)
    print("BUILT")
except SystemExit as e:
    print("REFUSED:", e)
""" % (HERE, os.path.join(HERE, "sheet"))


def run():
    r = subprocess.run([sys.executable, "-c", DRIVE], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    src = io.open(KNOW, encoding="utf-8").read()
    rc, out = run()
    if "BUILT" not in out:
        print("HARNESS FAILURE: the unmutated builder does not build\n%s" % out[-500:]); sys.exit(2)
    # THE MUTATION: one component loses its condition, exactly as a renamed heading would do.
    victim = "Reticle"
    m = re.search(r"^\*\*%s\*\*.*$" % victim, src, re.M)
    if not m:
        print("HARNESS FAILURE: %s has no entry to remove — the anchor moved" % victim); sys.exit(2)
    mutant = src[:m.start()] + "**NotAComponentAnyMore** (SMALL) — removed by the red proof." + src[m.end():]
    io.open(KNOW, "w", encoding="utf-8").write(mutant)
    try:
        rc2, out2 = run()
    finally:
        io.open(KNOW, "w", encoding="utf-8").write(src)
    named = victim in out2
    refused = "REFUSED" in out2 and "BUILT" not in out2
    if refused and named:
        print("  [RED]  a component that renders and loses its condition -> the builder REFUSES and names it (%s)" % victim)
    else:
        print("  [NOT RED] refused=%s named=%s\n%s" % (refused, named, out2[-400:])); sys.exit(1)
    rc3, out3 = run()
    if "BUILT" not in out3:
        print("  RESIDUE: the knowledge file did not restore\n%s" % out3[-300:]); sys.exit(1)
    print("  restored: the builder builds again")
    print("\n1/1 RED-proven")


if __name__ == "__main__":
    main()
