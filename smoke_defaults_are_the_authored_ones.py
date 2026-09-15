#!/usr/bin/env python3
"""RED-PROVEN. The check that makes 2026-09-14's blank-frame class impossible.

WHAT IT GUARDS. ChatCut's property system has no "unset" — its own validator
says so: `props.X has a hardcoded fallback via "??". Remove it — the property
system guarantees values are always present via defaultValue.` So a registered
default is not a formality; it is the ONLY value the component will ever see,
and it silently replaces every `??`, every parameter default, and every derived
colour the author wrote.

The registry had `enterFrames: 0` for all fourteen. `timing.enterFrames ??
defaultEnterFrames` therefore returned 0, `effectiveEnterFrames` became 0, and
useMGPhase's first hook called `interpolate(localFrame, [0, 0], [0, 1])`, which
Remotion refuses outright. Fourteen components, zero pixels, no error anywhere
we were looking. Ninety-eight defaults were wrong in total — fontSize 0, rows 0,
speed 0, every boolean false, every colour white.

TWO LEGS, TWO FAILURE CLASSES:

  1. FIDELITY — every registered default equals what the component does when
     the prop is absent. Catches the general silent override.
  2. CONSEQUENCE — the timing defaults cannot collapse an interpolate input
     range. Catches the specific blank frame, by the path actually traced,
     not by a name heuristic. Leg 1 would pass a registry rebuilt from a
     component whose own authored default was zero; leg 2 would not.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_chatcut_registry as B                             # noqa: E402

REG = os.path.join(HERE, "chatcut_registry.json")


def leg_fidelity(reg):
    """Every default equals the component's own absent-prop behaviour."""
    fresh = B.build(verbose=False)["components"]
    bad = []
    for n, spec in sorted(reg["components"].items()):
        if n not in fresh:
            bad.append((n, "-", "registered but the builder refuses it"))
            continue
        want = {p["key"]: p["defaultValue"] for p in fresh[n]["properties"]}
        for p in spec["properties"]:
            k = p["key"]
            if k not in want:
                bad.append((n, k, "declared but the builder does not derive it"))
            elif want[k] != p["defaultValue"]:
                bad.append((n, k, f"{p['defaultValue']!r} != authored {want[k]!r}"))
    return bad


def leg_consequence(reg):
    """No timing default can collapse `interpolate`'s input range.

    resolveMGPhaseFrames builds TWO ranges from these props:
        [0, effectiveEnterFrames]          effectiveEnterFrames = min(enter, ...)
        [exitStartFrame, durationFrames]   exitStart = durationFrames - exit
    Remotion's checkValidInputRange requires arr[i] > arr[i-1] STRICTLY, so a
    zero enterFrames or a zero exitFrames throws on every frame.
    """
    bad = []
    for n, spec in sorted(reg["components"].items()):
        if "useMGPhase(" not in spec["code"]:
            continue
        d = {p["key"]: p["defaultValue"] for p in spec["properties"]}
        if "enterFrames" not in d:
            continue
        fps = 30
        dur_frames = round((d.get("durationMs", 0) or 0) / 1000 * fps)
        enter, exit_ = d.get("enterFrames"), d.get("exitFrames")
        if not isinstance(enter, (int, float)) or enter <= 0:
            bad.append((n, "enterFrames", f"{enter!r} collapses [0, {enter!r}]"))
        if not isinstance(exit_, (int, float)) or exit_ <= 0:
            bad.append((n, "exitFrames",
                        f"{exit_!r} collapses [{dur_frames}, {dur_frames}]"))
        elif dur_frames - exit_ >= dur_frames:
            bad.append((n, "exitFrames", "exit window is not inside the duration"))
        if dur_frames <= 0:
            bad.append((n, "durationMs", f"{d.get('durationMs')!r} -> 0 frames"))
    return bad


def leg_agreement(reg):
    """The declared property set and the code's `props.X` reads are the SAME.

    ChatCut refuses either direction by name, and both refusals arrive as
    ABSENT — indistinguishable from a component that registered and drew
    nothing. Six of fourteen sat in that state while the number said 0/14.
    """
    import re
    bad = []
    for n, spec in sorted(reg["components"].items()):
        read = set(re.findall(r"\bprops\??\.([A-Za-z_$][\w$]*)", spec["code"]))
        dec = set(p["key"] for p in spec["properties"])
        for k in sorted(dec - read):
            bad.append((n, k, "declared but the code never reads it"))
        for k in sorted(read - dec):
            bad.append((n, k, "read by the code but not declared"))
    return bad


def run(reg):
    f, c, a = leg_fidelity(reg), leg_consequence(reg), leg_agreement(reg)
    for n, k, why in f:
        print("  FIDELITY    %-18s %-16s %s" % (n, k, why))
    for n, k, why in c:
        print("  CONSEQUENCE %-18s %-16s %s" % (n, k, why))
    for n, k, why in a:
        print("  AGREEMENT   %-18s %-16s %s" % (n, k, why))
    return f, c, a


if __name__ == "__main__":
    reg = json.load(open(REG, encoding="utf-8"))
    f, c, a = run(reg)
    print("  fidelity %d   consequence %d   agreement %d"
          % (len(f), len(c), len(a)))
    green = not f and not c and not a

    # RED PROOF — a check that has never failed is not yet a check. Both legs
    # are driven to RED here, in this file, every run.
    print("\n  RED PROOF")
    r1 = copy.deepcopy(reg)
    for p in r1["components"]["StatCard"]["properties"]:
        if p["key"] == "accentColor":
            p["defaultValue"] = "#FFFFFF"        # the old type default
    f1, c1 = leg_fidelity(r1), leg_consequence(r1)
    print("    a silent colour override        -> fidelity %d, consequence %d"
          % (len(f1), len(c1)))
    r2 = copy.deepcopy(reg)
    for n in r2["components"]:
        for p in r2["components"][n]["properties"]:
            if p["key"] in ("enterFrames", "exitFrames"):
                p["defaultValue"] = 0            # the exact shipped defect
    f2, c2 = leg_fidelity(r2), leg_consequence(r2)
    print("    enterFrames/exitFrames = 0      -> fidelity %d, consequence %d"
          % (len(f2), len(c2)))
    r3 = copy.deepcopy(reg)
    one = sorted(r3["components"])[0]
    r3["components"][one]["properties"].append(
        {"key": "aPropTheCodeNeverReads", "label": "x", "type": "number",
         "defaultValue": 0})        # the exact shape ChatCut refused
    a3 = leg_agreement(r3)
    print("    a declared prop the code never reads -> agreement %d" % len(a3))
    # RELATIVE, NOT A HARDCODED COUNT. The first version asserted
    # `len(c2) == 28` and `len(a3) == 1`, both true only of a 14-component
    # registry; the population changed to 9 and the RED proof went red for the
    # wrong reason. A check that hardcodes today's state fails the day the
    # state improves — this repo's own rule, in the file written to enforce it.
    n_phase = sum(1 for s in reg["components"].values()
                  if "useMGPhase(" in s["code"])
    red_ok = (len(f1) == 1 and len(c1) == 0 and len(f2) > 0
              and len(c2) == 2 * n_phase and len(a3) == 1)
    print("    all three legs RED where expected -> %s  "
          "(consequence %d == 2 x %d useMGPhase components)"
          % (red_ok, len(c2), n_phase))

    ok = green and red_ok
    print("\n  %s" % ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
