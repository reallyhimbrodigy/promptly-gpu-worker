#!/usr/bin/env python3
"""ChatCut strips mixBlendMode, so no body may describe a blend as if it renders.

MEASURED 2026-09-21, not inferred. Re-registering LightLeakOverlay returned
"Export contract auto-fix: mixBlendMode was removed; those layers now draw with
the normal blend mode", and reading the registered asset back confirmed it: all
three declarations gone, while the source comments still said "drawn in
`screen`". The fifth auto-rewrite, beside the props-fallback strip, the nested
({item}) injection, <img> -> <Img>, and the stripped trailing newline.

IT IS THE ONLY ONE OF THE FIVE THAT CHANGES WHAT A COMPONENT LOOKS LIKE. The
other four change how the code is written and leave the picture alone. This one
leaves the code looking exactly as the author wrote it and changes the render —
so the source is a truthful account of a composite that never happens, and four
rounds of reading it found nothing.

THE RULE IS NOW ZERO DECLARATIONS, NOT ZERO SILENT ONES (Zac, 2026-09-21:
"acknowledge the strip in the body or lose the declaration"). The first version
of this check asked every declaring body to carry an acknowledgement. That was
the right shape for an afternoon and the wrong shape to keep: a declaration
that CANNOT TAKE EFFECT is a fallback in source, which this lane already
forbids, and an annotated one is still dead code that looks live. All four
bodies lost theirs, the population went to zero, and this check went red on its
own success — which is the correct behaviour for a leg over an empty set and
the reason the floor exists.

So it counts the whole body corpus instead, and asserts the property directly.

WHY THE REASON IS ALSO ASSERTED. Deleting every declaration leaves nothing to
explain why, and the next person to want a `screen` glow will simply add one
back. L2 requires the finding to survive somewhere in the corpus, so the
deletion carries its own argument.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BODIES = os.path.join(HERE, "port", "bodies")

# The acknowledgement a body must carry if it declares mixBlendMode. Matched on
# the FACT, not on a form of words, so a rewrite of the surrounding prose does
# not silently drop it.
# THE DETECTOR'S PATTERN, HOISTED SO THE CANARY USES THE SAME ONE. It had its
# own copy inline, so breaking the detector left the canary matching happily and
# the blindness went unreported — a check testing a second copy of the thing it
# is checking.
DECL = r'mixBlendMode:\s*"([a-z-]+)"'

ACK = re.compile(r"strips?\s+mixBlendMode|mixBlendMode\s+(?:is\s+)?(?:was\s+)?(?:stripped|removed)",
                 re.IGNORECASE)

FAILS = []


def leg(name, ok, got):
    print("  %-38s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    bodies = sorted(f for f in os.listdir(BODIES) if f.endswith(".jsx"))
    # A CHECK OVER AN EMPTY POPULATION ASSERTS NOTHING — and here the population
    # is every body, so it stays non-empty even when zero of them declare a
    # blend. That is the whole repair: the first version counted DECLARERS, so
    # fixing the defect emptied the check.
    leg("L0 corpus_nonempty", len(bodies) >= 20, "%d bodies" % len(bodies))
    if not bodies:
        print("0/0 — refusing to report a pass over an empty corpus")
        return 1

    declared = {}
    ack_bodies = []
    for f in bodies:
        src = open(os.path.join(BODIES, f), encoding="utf-8").read()
        modes = re.findall(DECL, src)
        if modes:
            declared[f[:-4]] = sorted(set(modes))
        if ACK.search(src):
            ack_bodies.append(f[:-4])

    # L1 THE PROPERTY. ChatCut strips mixBlendMode, so a declaration is inert by
    # construction and the source would describe a composite that never happens.
    leg("L1 no_blend_declarations", not declared,
        "declaring: %s" % ({k: ",".join(v) for k, v in declared.items()} or "none"))

    # L2 THE REASON SURVIVES, PER BODY AND BY NAME. This first floored on a
    # COUNT (>= 3 bodies carry the finding) and the red proof walked straight
    # past it: deleting DepthPull's note left three others standing, so the
    # total held while the body that most needs the warning lost it. That is
    # this repo's own rule about a floor on a sum hiding which contributor
    # vanished, and I wrote the leg that way anyway. Named individually now.
    MUST_CARRY = ["DepthPull", "LightLeakOverlay", "ShutterFlash", "ShutterFlashOverlay"]
    lost = [n for n in MUST_CARRY if n not in ack_bodies]
    leg("L2 the_finding_is_recorded", not lost,
        "%d/%d carry it; lost: %s" % (len(MUST_CARRY) - len(lost), len(MUST_CARRY), lost or "none"))

    # L3 THE DETECTOR CAN STILL SEE ONE. Breaking the pattern empties `declared`
    # and L1 then passes for the wrong reason — a clean corpus and a blind
    # detector are the same output. The canary is a string this file owns, so it
    # cannot go stale with the corpus.
    canary = 'style={{ opacity: 1, mixBlendMode: "screen" }}'
    leg("L3 detector_finds_a_known_positive",
        re.findall(DECL, canary) == ["screen"],
        "canary -> %s" % re.findall(DECL, canary))

    print("%d/%d legs ok" % (4 - len(FAILS), 4))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
