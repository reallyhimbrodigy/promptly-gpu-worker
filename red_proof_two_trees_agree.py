#!/usr/bin/env python3
"""RED proof for smoke_two_trees_agree.py.

EVERY MUTATION REVERTS A FIX IN EXACTLY ONE TREE, because that is the defect:
not "the fix is gone" but "the fix is gone from ONE SIDE", which is what
actually happened and what nothing would have said.
"""
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_two_trees_agree.py")
T = os.path.join(HERE, "src", "remotion", "src", "motion-graphics")
P = os.path.join(HERE, "ported_mg")


def _env():
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


MUT = [
    ("tsx_only_loses_the_grouping",
     os.path.join(T, "StatCard", "StatCard.tsx"),
     "groupDigits(String(Math.round(currentValue)))",
     "Math.round(currentValue).toLocaleString()",
     "L1 no_fixed_defect_survives_in_either_tree"),
    ("ported_only_loses_the_grouping",
     os.path.join(P, "StatCard.jsx"),
     "groupDigits(String(Math.round(currentValue)))",
     "Math.round(currentValue).toLocaleString()",
     "L1 no_fixed_defect_survives_in_either_tree"),
    ("tsx_only_turns_the_fog_back_on",
     os.path.join(T, "StickyNotes", "StickyNotes.tsx"),
     "showFog = false", "showFog = true",
     "L2 every_fix_is_present_in_both_trees"),
    ("ported_only_moves_the_tag_back_outside",
     os.path.join(P, "Reticle.jsx"),
     "top: armLength + 14", "top: 0",
     "L2 every_fix_is_present_in_both_trees"),
]


def run():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True,
                       env=_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def failed(out, phrase):
    return any(phrase in ln and "FAIL" in ln for ln in out.splitlines())


def main():
    rc, out = run()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-700:])
        return 2
    print("baseline green.\n")
    red = 0
    for name, path, old, new, phrase in MUT:
        raw = io.open(path, encoding="utf-8").read()
        if raw.count(old) < 1:
            print("  %-38s HARNESS FAILURE: anchor 0x in %s"
                  % (name, os.path.basename(path)))
            continue
        io.open(path, "w", encoding="utf-8").write(raw.replace(old, new, 1))
        rc2, out2 = run()
        io.open(path, "w", encoding="utf-8").write(raw)
        ok = rc2 != 0 and failed(out2, phrase)
        red += 1 if ok else 0
        print("  %-38s %s   rc=%d leg_failed=%s"
              % (name, "RED " if ok else "NOT RED", rc2, failed(out2, phrase)))
        if io.open(path, encoding="utf-8").read() != raw:
            print("\nHARNESS FAILURE: residue in %s" % path)
            return 2
    print("\n%d/%d RED-proven" % (red, len(MUT)))
    return 0 if (MUT and red == len(MUT)) else 1


if __name__ == "__main__":
    sys.exit(main())
