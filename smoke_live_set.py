#!/usr/bin/env python3
"""lane_contract.live_set() is the ONE accessor for the live set.

WHY IT NEEDS A CHECK AT ALL. Builder 1 asked for "the 47 by name" and the honest
answer was a list in a message — a second copy of a fact, which is what
lane_contract exists to stop. The accessor replaces the message; these legs are
what make the accessor trustworthy enough to replace it.

THE LEG THAT MATTERS MOST IS L6. An empty components map must come back FAILED,
never MEASURED with an empty list: every caller reads `components` and a clean []
says "production uses no components", which is a lost ruling wearing a
measurement's clothes. That is this repo's oldest defect class and it would land
here in its purest form.
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lane_contract as lc                                     # noqa: E402

FAILS = []


def leg(name, ok, got):
    print("  %-34s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    r = lc.live_set()
    print("live_set(): %s" % r.get("why", r.get("state")))

    leg("L1 state_measured", r["state"] == lc.MEASURED, r["state"])
    # The counts are pinned because a SILENT DRIFT is the failure here — a merge
    # that drops rows leaves a smaller, perfectly well-formed library.
    leg("L2 n_is_46", r.get("n") == 46, "n=%s" % r.get("n"))
    leg("L3 renderable_is_26", r.get("n_renderable") == 26, "n=%s" % r.get("n_renderable"))

    fams = r.get("by_family") or {}
    rend = set(r.get("renderable") or [])
    sfx, styles = set(fams.get("sfx") or []), set(fams.get("caption style") or [])
    leg("L4 no_sfx_in_renderable", bool(sfx) and not (sfx & rend),
        "%d sfx, %d leaked" % (len(sfx), len(sfx & rend)))
    leg("L5 no_style_in_renderable", bool(styles) and not (styles & rend),
        "%d styles, %d leaked" % (len(styles), len(styles & rend)))

    # L5b THE TWO-HOME LEG, ON A FIXTURE — because the real population cannot
    # exercise it. StickyNotes is a motion graphic AND a text overlay, and
    # NEITHER home is picture-free, so it stays renderable under any spelling of
    # the rule. Asserting it here would be a leg that cannot fail: the property
    # is "one picture-bearing home is enough", and today no component has one
    # home of each kind. So the fixture supplies the case the library lacks —
    # a component that is both an sfx and a motion graphic must stay renderable,
    # and one that is only an sfx must not.
    fx = {"_library": {"components": {
        "BothHomes": {"families": ["sfx", "motion graphic"]},
        "SoundOnly": {"families": ["sfx"]},
    }}}
    fxp = os.path.join(lc.HERE, "_smoke_live_set_twohome.json")
    open(fxp, "w").write(json.dumps(fx))
    try:
        t = lc.live_set("_smoke_live_set_twohome.json")
        trend = set(t.get("renderable") or [])
        leg("L5b two_home_kept",
            trend == {"BothHomes"},
            "renderable=%s (want {'BothHomes'})" % sorted(trend))
    finally:
        os.remove(fxp)
    leg("L5c stickynotes_present", "StickyNotes" in rend,
        "StickyNotes in renderable=%s" % ("StickyNotes" in rend))

    # L6 the floor. An empty map is a lost ruling, not a measurement.
    empty = {"_library": {"components": {}}}
    tmp = os.path.join(lc.HERE, "_smoke_live_set_empty.json")
    open(tmp, "w").write(json.dumps(empty))
    try:
        e = lc.live_set("_smoke_live_set_empty.json")
        leg("L6 empty_is_FAILED", e["state"] == lc.FAILED and "components" not in e,
            "state=%s components_key=%s" % (e["state"], "components" in e))
    finally:
        os.remove(tmp)

    # L7 a library with no ruling published is ABSENT, not FAILED and not empty.
    noscope = os.path.join(lc.HERE, "_smoke_live_set_noscope.json")
    open(noscope, "w").write(json.dumps({"zoom": ["StepZoom"]}))
    try:
        a = lc.live_set("_smoke_live_set_noscope.json")
        leg("L7 no_ruling_is_ABSENT", a["state"] == lc.ABSENT, "state=%s" % a["state"])
    finally:
        os.remove(noscope)

    # L8 the partition: nothing is lost between the two subsets, and nothing is
    # counted twice. A component that fell out of both would be invisible.
    nop = set((r.get("no_picture") or {}).keys())
    leg("L8 partition_exact",
        (rend | nop) == set(r.get("components") or []) and not (rend & nop),
        "%d + %d = %d of %d" % (len(rend), len(nop), len(rend | nop), r.get("n") or -1))

    print("%d/%d legs ok" % (9 - len(FAILS), 9))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
