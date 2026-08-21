#!/usr/bin/env python3
"""cert_freeze_mask_scope.py — THE FREEZE EXEMPTION IS INTERVAL-SCOPED, NOT A BLANKET PASS.

WHY THE EXEMPTION EXISTS. EvidenceCard and DeviceMockup render a <Freeze> of the
user's own frame: a HELD STILL IS THE COMPONENT. The integrity gate's freeze
check exists to catch a stuck render, so it saw those held frames and killed the
job — correct by its own rule, wrong for these components:

    INTEGRITY_TRIP: freeze=[[16.4,17.73],[18.13,19.0],[19.0,21.17],
                            [21.4,22.67],[22.67,23.8]]

Every interval falls inside a declared card window (out=[14.93..17.73],
[18.05..21.56], [21.32..23.82]). The freezes ARE the cards.

WHY THIS CERT IS MOSTLY NEGATIVE. An exemption is the easiest thing in this
codebase to over-widen: mask "freeze" and a genuinely stuck render ships as a
delivered video. The integrity gate is the last thing standing between a broken
render and a user, so the valuable assertions here are the ones about what still
TRIPS.

  1  POSITIVE — a freeze wholly inside a declared frame-comp window is masked.
  2  NEGATIVE — a freeze OUTSIDE any window still trips. This is the check that
     matters; without it the fix is indistinguishable from disabling freeze
     detection.
  3  NEGATIVE — a freeze that merely OVERLAPS a window's edge still trips. A
     stuck render that happens to begin during a card must not be laundered by
     it.
  4  SCOPE — only frame-replacing and full-size types contribute windows.
     StatCard (an overlay, no freeze of its own) contributes nothing, so it can
     never mask a stuck render behind a floating number.

    python3 cert_freeze_mask_scope.py
"""
import os
import sys

os.environ.setdefault("APP_URL", "")


def main():
    import handler as H
    fails = []
    mask_types = H._MG_FULLSIZE_TYPES | H._MG_FRAME_REPLACING_TYPES

    # ── 4: scope ────────────────────────────────────────────────────────────
    print(f"  [4] contributes a freeze window: EvidenceCard="
          f"{'EvidenceCard' in mask_types} DeviceMockup="
          f"{'DeviceMockup' in mask_types} StatCard="
          f"{'StatCard' in mask_types} (StatCard must be False)")
    for t in ("EvidenceCard", "DeviceMockup"):
        if t not in mask_types:
            fails.append(f"{t} renders a <Freeze> but contributes no mask window "
                         f"— the integrity gate will kill every job using it")
    if "StatCard" in mask_types:
        fails.append("StatCard contributes a freeze window — it is an overlay "
                     "with no freeze of its own, so masking its window could "
                     "launder a genuinely stuck render")

    # ── 1-3: the subtraction, on the REAL helper ────────────────────────────
    # _ig_subtract(spans, masks) is what the gate uses to decide what survives.
    windows = [(14.93, 17.73), (18.05, 21.56)]
    cases = [
        ("inside a window (the cards)", [(16.4, 17.7)], False),
        ("outside every window (stuck render)", [(30.0, 34.0)], True),
        ("overlapping a window's edge", [(21.0, 25.0)], True),
        ("spanning the gap between windows", [(17.8, 18.0)], True),
    ]
    for label, spans, must_trip in cases:
        resid = H._ig_subtract(spans, windows)
        trips = bool(resid)
        state = "TRIPS" if trips else "masked"
        print(f"  {'[1]' if not must_trip else '[2/3]'} {label:38} -> {state}")
        if trips != must_trip:
            fails.append(
                f"{label}: expected {'TRIP' if must_trip else 'masked'}, got "
                f"{'TRIP' if trips else 'masked'} — "
                + ("a stuck render would ship as a delivered video"
                   if must_trip else "the cards would keep killing the job"))

    # ── 5: RUNTIME — the mask must actually BUILD, not just be declared ─────
    # THE GAP THIS CLOSES: clauses 1-4 assert the TYPE SET and the subtraction
    # helper, both of which were correct while the live gate reported
    # masks=0/0/0. A cert that is true about the code and silent about the
    # wiring passes while the feature does nothing — the same shape as the
    # recipe_eval ordering bug. So drive the REAL mask builder.
    built = H._build_integrity_masks({
        "_integrity_fullmg_ranges": [(14.97, 17.77), (18.09, 21.59)],
        "_integrity_slot_ranges": [], "_broll_output_ranges": [],
        "_rendered_generated_scenes": [], "_render_fps": 30.0,
    })
    n_freeze = len(built.get("freeze") or [])
    print(f"  [5] _build_integrity_masks with 2 card windows -> {n_freeze} freeze mask(s)")
    if n_freeze < 2:
        fails.append(f"the real mask builder produced {n_freeze} freeze mask(s) "
                     f"from 2 declared card windows — the exemption is declared "
                     f"but does not BUILD, so the gate still sees the cards")
    empty = H._build_integrity_masks({"_render_fps": 30.0})
    if (empty.get("freeze") or []):
        fails.append("the builder invents masks with NO declared ranges — that "
                     "would mask a stuck render on a plan with no cards at all")
    print(f"      with no declared ranges -> {len(empty.get('freeze') or [])} (must be 0)")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT FREEZE-MASK-SCOPE: FAIL")
        return 1
    print("  CERT FREEZE-MASK-SCOPE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
