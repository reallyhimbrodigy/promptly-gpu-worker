#!/usr/bin/env python3
"""A component whose correct midpoint is signal-free carries a proof frame elsewhere.

Ruled by Zac 2026-09-21 on DipToBlack: prove it "at the frame where its signal
exists — 25% progress, the plate dimming, against the control — not at the
midpoint."

WHY A GATE AND NOT A NOTE. DipToBlack's correct output at its dip is a black
frame, which is byte-for-byte what a completely failed render produces. The
frame anybody naturally samples — the middle of the effect — is the ONE frame
that can never decide it, in either direction. A verdict taken there is
worthless whichever way it lands, and it looks exactly like every other verdict
in the table.

AND A NOISE FLOOR DOES NOT RESCUE IT. Measuring the floor on the run is the
right fix for a render that might have failed to fetch, but it cannot help
here: the correct output genuinely has no signal. There is nothing to be above.

THE FAMILY IS DERIVED, NOT LISTED. A black root plus complementary A/B opacity
fades is the shape that dips through the root, and it is read out of the bodies
— so a component that acquires the shape is covered the day it does rather than
the day someone remembers. Today it finds two, and only one of them is the one
anybody had noticed.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BODIES = os.path.join(HERE, "port", "bodies")
STILLS = os.path.join(HERE, "measured", "inventory_stills.json")
FAILS = []


def leg(name, ok, got):
    print("  %-38s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def dips_through_root(src):
    """True when the body can show its own root mid-ramp.

    The shape: an opaque root colour, plus an A layer that fades OUT and a B
    layer that fades IN, so there is a moment where neither covers it.
    """
    if not re.search(r'backgroundColor:\s*"#(?:000000|000)"', src):
        return False
    return bool(re.search(r"const\s+aOpacity\s*=", src)
                and re.search(r"const\s+bOpacity\s*=", src))


def main():
    fam = []
    for f in sorted(os.listdir(BODIES)):
        if not f.endswith(".jsx"):
            continue
        src = open(os.path.join(BODIES, f), encoding="utf-8").read()
        if dips_through_root(src):
            fam.append(f[:-4])

    # A CHECK OVER AN EMPTY POPULATION ASSERTS NOTHING.
    leg("L0 family_nonempty", len(fam) >= 1, "%d in the family: %s" % (len(fam), ", ".join(fam)))
    if not fam:
        print("0/0 — refusing to report a pass over an empty family")
        return 1

    stills = json.load(open(STILLS))["components"]

    missing = [n for n in fam if not (stills.get(n) or {}).get("proof_frame")]
    leg("L1 every_member_has_a_proof_frame", not missing, "missing: %s" % (missing or "none"))

    # L2 THE PROOF FRAME IS NOT THE DIP. This is the whole ruling: a proof frame
    # recorded AT the midpoint would satisfy L1 and prove nothing at all.
    at_the_dip = []
    for n in fam:
        pf = (stills.get(n) or {}).get("proof_frame") or {}
        dip = pf.get("dip_progress")
        ruled = (pf.get("ruled") or {}).get("progress")
        if ruled is None:
            at_the_dip.append("%s (no ruled progress)" % n)
        elif dip is not None and abs(ruled - dip) < 0.1:
            at_the_dip.append("%s (ruled %.2f vs dip %.2f)" % (n, ruled, dip))
    leg("L2 proof_frame_is_not_the_dip", not at_the_dip, "%s" % (at_the_dip or "none"))

    # L3 IT NAMES WHAT IT IS COMPARED AGAINST. "The plate is dimming" is only a
    # claim next to a control; without one, 90% opacity and 100% opacity are the
    # same picture to a reader.
    nocontrol = [n for n in fam if not ((stills.get(n) or {}).get("proof_frame") or {}).get("against")]
    leg("L3 proof_frame_names_its_control", not nocontrol, "missing control: %s" % (nocontrol or "none"))

    # L4 WHERE AN EXPECTED VALUE IS RECORDED IT IS ACTUALLY SEPARABLE — present
    # enough not to read as a failed render, changed enough not to read as a
    # passthrough. Recorded as ABSENT rather than guessed where it is unknown,
    # and an ABSENT expected value is not counted as a pass.
    unseparable, absent = [], []
    for n in fam:
        pf = (stills.get(n) or {}).get("proof_frame") or {}
        exp = (pf.get("ruled") or {}).get("expected_plate_opacity")
        if exp is None:
            absent.append(n)
        elif not (0.02 < exp < 0.98):
            unseparable.append("%s (%.4f)" % (n, exp))
    leg("L4 recorded_values_are_separable", not unseparable,
        "unseparable: %s | expected value ABSENT (not a pass): %s"
        % (unseparable or "none", absent or "none"))

    print("%d/%d legs ok" % (5 - len(FAILS), 5))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
