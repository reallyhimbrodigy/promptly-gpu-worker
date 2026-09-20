#!/usr/bin/env python3
"""RED PROOF — the no-hardcoded-fallbacks gate actually fires.

WHY (Zac, 2026-09-20). Defaults live in the property table and nowhere else,
because ChatCut REWRITES the code at registration and a fallback in source is
dead code that looks live. The gate that enforces it passed on its first run,
and a check that has never failed is not yet a check.

EVERY LEG RUNS AGAINST A COPY. The gate reads a directory; this harness makes a
throwaway copy of port/bodies and mutates THAT. The real tree is never written
to, so a SIGKILL between mutate and restore cannot leave the residue the gate
exists to detect — which is the failure mode relocation alone never reaches.

FIVE LEGS, FOUR OF THEM RED.
  1. GREEN  the tree as it stands passes (4 clean, 9 quarantined, 0 failing)
  2. RED    a fallback planted in a CLEAN body fails, and names the body
  3. RED    a quarantined body that becomes CLEAN fails ("is CLEAN but still
            pinned") — the list must shrink, and a stale pin must not sit here
            being read as a fact
  4. RED    an EMPTY bodies directory is a HARNESS FAILURE (exit 2), not a pass:
            a gate over an empty population asserts nothing, including this one
  5. RED    a fallback planted in a QUARANTINED body still only pins — proving
            the quarantine is what suppresses it, not a hole in the scanner

Each red asserts the gate's OWN WORDS, not merely a non-zero exit: a red for
some other reason is exactly as wrong as a green for some other reason.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent
GATE = ROOT / "port" / "no_fallbacks.mjs"
BODIES = ROOT / "port" / "bodies"
CLEAN = "SnapReframe"      # any body; the legs do not depend on which
# THE QUARANTINE SCENARIO IS BUILT, NOT BORROWED. Naming a body that happens to
# be pinned today makes this proof defend a DECISION: when Builder-1 cleared all
# nine — exactly what the gate exists to cause — two legs went red on correct
# code. The legs now WRITE a quarantine.json for whichever body they are
# testing, so they assert that quarantining WORKS rather than that anyone is
# currently quarantined.
PINNED = "StepZoom"        # arbitrary; this harness pins it itself
FALLBACK_LINE = '  const _planted = props.scale || 1.3;\n'


def gate(dirpath):
    """-> (rc, output). NO PIPE: the status is the gate's, not a pager's."""
    r = subprocess.run(["node", str(GATE), str(dirpath)],
                       capture_output=True, text=True, timeout=120)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def copy_bodies(quarantine=None):
    """A throwaway tree: bodies/ plus an optional quarantine.json beside it."""
    d = pathlib.Path(tempfile.mkdtemp(prefix="nofb_"))
    shutil.copytree(BODIES, d / "bodies")
    if quarantine:
        import json
        (d / "quarantine.json").write_text(json.dumps(quarantine), encoding="utf-8")
    return d, d / "bodies"


def plant(path, name):
    """Insert a fallback INSIDE the component. Returns False if the anchor moved."""
    p = path / (name + ".jsx")
    src = p.read_text(encoding="utf-8")
    anchor = "const props = (item && item.props) || {};\n"
    if src.count(anchor) != 1:
        return False
    p.write_text(src.replace(anchor, anchor + FALLBACK_LINE), encoding="utf-8")
    return True


def main():
    legs = []

    # 1. GREEN — the real tree, read-only.
    rc, out = gate(BODIES)
    legs.append(("GREEN the tree as it stands passes", rc == 0 and "0 FAILING" in out,
                 out.strip().splitlines()[-1] if out.strip() else "(no output)"))

    # 2. RED — a fallback in a clean body.
    d, bodies = copy_bodies()
    try:
        if not plant(bodies, CLEAN):
            legs.append(("RED   planted fallback fails", False, "HARNESS: anchor moved in " + CLEAN))
        else:
            rc, out = gate(bodies)
            legs.append(("RED   planted fallback fails", rc == 1 and ("[FAIL] %s" % CLEAN) in out,
                         "rc=%d names_body=%s" % (rc, ("[FAIL] %s" % CLEAN) in out)))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # 3. RED — a quarantined body that has become clean is a STALE PIN.
    d, bodies = copy_bodies({PINNED: {"owner": "test", "since": "2026-09-20"}})
    try:
        p = bodies / (PINNED + ".jsx")
        src = p.read_text(encoding="utf-8")
        # Strip every fallback line wholesale; the point is only that it is clean.
        keep = [l for l in src.split("\n")
                if not ("props." in l and ("||" in l or "??" in l or "=== undefined" in l)
                        and not l.strip().startswith("*"))]
        p.write_text("\n".join(keep), encoding="utf-8")
        rc, out = gate(bodies)
        # THE GATE'S OWN WORDS, not my internal state name. The first version of
        # this leg asserted "PIN IS STALE" — the enum value — while the gate
        # prints "is CLEAN but still pinned". It went red for the right reason
        # and the leg called it a failure, which is the phrase check working.
        phrase = "is CLEAN but still pinned"
        legs.append(("RED   a stale pin fails", rc == 1 and phrase in out and PINNED in out,
                     "rc=%d phrase=%s" % (rc, phrase in out)))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # 4. RED — an empty population is a HARNESS FAILURE, not a pass.
    d = pathlib.Path(tempfile.mkdtemp(prefix="nofb_empty_"))
    try:
        (d / "bodies").mkdir()
        rc, out = gate(d / "bodies")
        legs.append(("RED   empty population is rc=2", rc == 2 and "HARNESS FAILURE" in out,
                     "rc=%d phrase=%s" % (rc, "HARNESS FAILURE" in out)))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # 5. RED-CONTROL — the same plant inside a QUARANTINED body only pins.
    #    This is what proves the quarantine suppresses it, rather than the
    #    scanner being blind to that file.
    d, bodies = copy_bodies({PINNED: {"owner": "test", "since": "2026-09-20"}})
    try:
        if not plant(bodies, PINNED):
            legs.append(("RED   quarantine suppresses, scanner still sees", False,
                         "HARNESS: anchor moved in " + PINNED))
        else:
            rc, out = gate(bodies)
            ok = rc == 0 and ("[pin]  %s" % PINNED) in out and ("[FAIL] %s" % PINNED) not in out
            legs.append(("RED   quarantine suppresses, scanner still sees", ok,
                         "rc=%d pinned=%s" % (rc, ("[pin]  %s" % PINNED) in out)))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("RED PROOF — the no-fallbacks gate")
    bad = 0
    for name, ok, detail in legs:
        print("  [%s] %-46s %s" % ("ok " if ok else "FAIL", name, detail))
        bad += 0 if ok else 1
    print()
    # A FLOOR: a harness whose legs vanished reports success without it.
    if not legs:
        print("HARNESS FAILURE: no legs ran")
        return 2
    print("%d legs, %d green, %d failed" % (len(legs), len(legs) - bad, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
