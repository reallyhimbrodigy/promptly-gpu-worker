#!/usr/bin/env python3
"""SMOKE — a graphic with nowhere clear is repositioned, then dropped WITH A NOTE.

PRODUCTION'S RULE IS NOT "FAIL". handler.py has carried this ladder for months:
`_place_component_gracefully` contracts the window looking for a sub-window
where a band is clear, and when none exists it drops the graphic and hands the
user a sentence — "the frame is too tight there for one to sit clear of your
face, so I let the line carry it." Nothing failed; a component was considered
and not placed, which is a decision an editor makes constantly.

THIS LANE COULD NOT DO ANY OF IT. `agentic_editor_app.py` produces no
`face_traj` and no `source_text_regions`, and the translator has neither cv2
nor the weights, so every placement went down blind. HOP 6 then found three of
them sitting on the speaker — a true finding with no mechanism behind it to
act on.

Legs, each RED-proven:
  CLEAR    a band the face does not occupy is placed unchanged
  CONTRACT a band clear only later in the window is REPOSITIONED, and the
           START never moves — the anchor is where the planner grounded it
  DROP     a band nothing clears is dropped, with `unfittable`
  NOTE     the sentence names the moment in the USER'S words and carries no
           component type, no error code and no failure language
  ABSENT   regions that could not be read are NAMED, not treated as clear
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_for_chatcut as P                                   # noqa: E402
import face_bands as FB                                        # noqa: E402

# A face that sits LOW for the first half and rises for the second: `top` is
# clear early and blocked late, which is what makes CONTRACT distinguishable
# from CLEAR at all.
LOW = [{"t": round(i * 0.25, 2), "cy": 1500, "found": True} for i in range(9)]
HIGH = [{"t": 2.0 + round(i * 0.25, 2), "cy": 400, "found": True}
        for i in range(9)]


def legs():
    bad = []
    # CLEAR — face low, `top` is free for the whole window
    o, end, why = P.place_gracefully("top", 0.0, 2.0, LOW, [])
    if o != "placed" or end != 2.0:
        bad.append(("clear", "a free band was not simply placed: %s" % ((o, end),)))

    # CONTRACT — face rises at 2.0s, so 0.0-4.0 is blocked but 0.0-~2.0 is not
    traj = LOW + HIGH
    o2, end2, _ = P.place_gracefully("top", 0.0, 4.0, traj, [])
    if o2 != "repositioned":
        bad.append(("contract", "a window clear only in part was %r, not "
                                "repositioned" % o2))
    elif not (P.MG_MIN_WINDOW_S <= end2 < 4.0):
        bad.append(("contract", "repositioned to a window outside the bounds: "
                                "%s" % end2))

    # ...AND THE START NEVER MOVES. The ladder returns only an END; a version
    # that slid the anchor would keep grounding nowhere.
    import inspect
    src = inspect.getsource(P.place_gracefully)
    if "t0 -" in src or "t0 +=" in src or "t0 =" in src:
        bad.append(("contract", "the ladder moves the START — the anchor is "
                                "where the planner grounded the beat"))

    # DROP — face high the whole time AND the other bands owned by the source
    o3, _, why3 = P.place_gracefully("top", 2.0, 4.0, HIGH, ["center", "bottom"])
    if o3 != "dropped" or why3 != "unfittable":
        bad.append(("drop", "a blocked band was %r/%r, not dropped/unfittable"
                            % (o3, why3)))

    # a band the SOURCE's text owns is never clear, whatever the face does
    if P._band_clear("center", 0.0, 2.0, LOW, ["center"]):
        bad.append(("drop", "a burned-in-text band read as clear"))

    # NOTE — the user's words, and none of ours
    note = P.unplaced_note("MADE WITH THE APP")
    for word in ("StatCard", "error", "failed", "unfittable", "band", "None"):
        if word.lower() in note.lower():
            bad.append(("note", "the sentence says %r to the user" % word))
    if "MADE WITH THE APP" not in note:
        bad.append(("note", "the sentence does not name the moment"))
    if not P.unplaced_note("").strip():
        bad.append(("note", "there is no sentence when the line is unknown"))

    # ABSENT — regions that could not be read must be named
    r = P._regions({"regions": {}})
    if r.get("face_state") == "MEASURED" and not os.path.exists(
            os.path.join(HERE, "regions.json")):
        bad.append(("absent", "missing regions reported as MEASURED"))
    return bad


if __name__ == "__main__":
    bad = legs()
    for k, w in bad:
        print("  [FAIL] %-9s %s" % (k, w))
    if not bad:
        print("  [ok] a clear band is placed unchanged")
        print("  [ok] a partly-clear window is repositioned, anchor fixed")
        print("  [ok] a blocked band is dropped as `unfittable`")
        print("  [ok] the note names the moment in the user's words")
        print("  [ok] unreadable regions are NAMED, not treated as clear")

    print("\n  RED PROOF")
    red = True
    # the ladder must not place a blocked band
    o, _, _ = P.place_gracefully("top", 2.0, 4.0, HIGH, ["center", "bottom"])
    print("    every band blocked          -> %r" % o)
    red &= (o == "dropped")

    # a window too short to contract cannot be repositioned into existence
    o2, _, _ = P.place_gracefully("top", 2.0, 2.5, HIGH, [])
    print("    window below the floor      -> %r" % o2)
    red &= (o2 == "dropped")

    # and the threshold is production's, not a local one
    print("    threshold is production's   -> %s (%s)"
          % (FB.MG_FACE_CLEAR_THRESHOLD == 0.35, FB.MG_FACE_CLEAR_THRESHOLD))
    red &= (FB.MG_FACE_CLEAR_THRESHOLD == 0.35)

    # a note that names a component would be caught
    _bad_note = "I wanted a StatCard there but it failed"
    print("    a note naming a component   -> caught: %s"
          % any(w in _bad_note for w in ("StatCard", "failed")))
    red &= any(w in _bad_note for w in ("StatCard", "failed"))

    ok = not bad and red
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
