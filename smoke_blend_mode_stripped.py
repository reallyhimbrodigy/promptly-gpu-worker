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

WHAT THIS CHECKS, AND WHAT IT CANNOT. It cannot make the blend work. What it
can do is stop the source LYING: every body that declares mixBlendMode must
also carry the acknowledgement, so the next reader knows the layer composites
normally before they measure anything against it. That is exactly the cost I
paid — a perceptibility number solved against screen and soft-light when the
runtime does neither, corrected only because a rendered frame disagreed with the
arithmetic.

THE RISK IS NOT EQUAL ACROSS BLEND MODES, so the report names them. `screen`
stripped to normal makes a glow opaque instead of additive. `multiply` stripped
to normal is worse: a vignette that darkened what was under it becomes a flat
covering layer. DepthPull has one of each.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BODIES = os.path.join(HERE, "port", "bodies")
sys.path.insert(0, HERE)
import lane_contract as lc                                     # noqa: E402

# The acknowledgement a body must carry if it declares mixBlendMode. Matched on
# the FACT, not on a form of words, so a rewrite of the surrounding prose does
# not silently drop it.
ACK = re.compile(r"strips?\s+mixBlendMode|mixBlendMode\s+(?:is\s+)?(?:was\s+)?(?:stripped|removed)",
                 re.IGNORECASE)

FAILS = []


def leg(name, ok, got):
    print("  %-38s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    users = {}
    for f in sorted(os.listdir(BODIES)):
        if not f.endswith(".jsx"):
            continue
        src = open(os.path.join(BODIES, f), encoding="utf-8").read()
        modes = re.findall(r'mixBlendMode:\s*"([a-z-]+)"', src)
        if modes:
            users[f[:-4]] = (sorted(set(modes)), bool(ACK.search(src)))

    # A CHECK OVER AN EMPTY POPULATION ASSERTS NOTHING.
    leg("L0 population_nonempty", len(users) >= 1,
        "%d body/bodies declare mixBlendMode" % len(users))
    if not users:
        print("0/0 — refusing to report a pass over an empty population")
        return 1

    ls = lc.live_set()
    if ls["state"] != lc.MEASURED:
        print("HARNESS FAILURE: live_set is %s" % ls["state"])
        return 2

    for n, (modes, ack) in sorted(users.items()):
        where = ("ON MENU" if n in ls["menu"]
                 else "renderable" if n in ls["renderable"]
                 else "out of scope")
        print("     %-22s %-18s %-12s ack=%s" % (n, ",".join(modes), where, ack))

    # L1 every declaring body says so. This is the leg that stops the source
    # being a truthful description of a composite that never runs.
    silent = sorted(n for n, (m, a) in users.items() if not a)
    leg("L1 every_user_names_the_strip", not silent, "silent: %s" % (silent or "none"))

    # L2 NOTHING ON THE MENU CARRIES AN UNACKNOWLEDGED BLEND. The menu is the
    # offerable set; a component there whose source describes a blend it will
    # not get is one somebody will measure against the wrong model, which is
    # precisely what happened to LightLeakOverlay.
    on_menu = sorted(n for n, (m, a) in users.items() if n in ls["menu"] and not a)
    leg("L2 menu_has_no_silent_blend", not on_menu, "on menu and silent: %s" % (on_menu or "none"))

    # L3 `multiply` is named separately because the failure is worse and the
    # shape is different: screen stripped to normal makes a glow opaque; multiply
    # stripped to normal turns a darkening layer into a covering one.
    mult = sorted(n for n, (m, a) in users.items() if "multiply" in m)
    mult_unack = sorted(n for n in mult if not users[n][1])
    leg("L3 multiply_users_acknowledged", not mult_unack,
        "%d use multiply %s | unacknowledged: %s" % (len(mult), mult or "", mult_unack or "none"))

    print("%d/%d legs ok" % (4 - len(FAILS), 4))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
