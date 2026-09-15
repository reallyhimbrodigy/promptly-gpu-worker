#!/usr/bin/env python3
"""SMOKE — a ruling that does not reach the plan RAISES, by name.

MEASURED ON THE BLUE-SHIRT EDIT. The pipeline ruled 14 placements — text 7,
cutaway 3, sfx 2, zoom 1, card 1 — and the plan carried 7. Three cutaways were
NAMED as dropped because cutaway has no verified primitive. The other four
vanished in silence, including a StatCard whose hero was the video's own
closing line ("5 MINUTES", "to edit — I did nothing").

THE CAUSE was one loop that emitted ONE TITLE PER TREATED BEAT whatever the
beat was ruled, so `text+card+sfx` produced a title and the rest evaporated —
while FAMILY_MAP said card, zoom and sfx all had verified primitives.

AND THE GATE COULD NOT SEE IT. `PLACEMENTS` compares the plan's own
`planned_adds` with what the agent built, so it read 8 of 8 MEASURED while the
plan had already lost half the rulings. The check sat downstream of the loss —
the same shape as the caption contradiction, one layer further up.

So the translator now keeps an account: every ruled family is emitted, or
dropped-and-named, or the plan REFUSES TO EXIST. A placement that disappears
is not a smaller edit; it is an edit nobody ruled.
"""
import copy
import json
import re
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_for_chatcut as P                                   # noqa: E402


def _beat(t0, t1, treatment, text="WORDS"):
    return {"treatment": treatment, "src_t0": t0, "src_t1": t1,
            "text_content": text, "size": "medium", "case": "upper",
            "where": "upper_third", "colour": "white_on_footage",
            "hold_s": 2.0, "why": "smoke", "purpose": "hook",
            "zoom_arc": "payoff", "sfx_name": "transition-sfx",
            "card_condition": "WHEN A NUMBER LANDS", "card_hero": "5 MINUTES",
            "card_label": "to edit"}


BASE = {
    "ledger": {"keep_spans": [[0.0, 20.0]], "source_duration_s": 20.0,
               "spec": {"mode": "full_edit", "families": None}},
    "plan": [_beat(1.0, 3.0, ["text"]),
             _beat(5.0, 8.0, ["text", "zoom"]),
             _beat(10.0, 13.0, ["text", "card", "sfx"])],
}


def emit(plan):
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(plan, fh)
    fh.close()
    try:
        return P.render(fh.name, staged=True, allow_drop=True)
    finally:
        os.unlink(fh.name)


def legs():
    bad = []
    t = emit(BASE)
    # COUNT THE BLOCK, NOT ITS LABEL. The effect moved into a second
    # edit_item call and its header changed from `edit_item adds[0]:`
    # to `CALL 2, adds[0]:` — a counter keyed to the old prose
    # reported the zoom missing from a plan that emits it.
    # ...and a HEADER, not a MENTION of one. The plan's own prose shows the
    # agent the shape ("EVERY add BELOW IS LABELLED ... `CALL 1, adds[3]:`"),
    # and an unanchored scan counted that sentence as a seventh add. Fourth
    # reader today to be wrong about correct text: anchor to the whole line.
    n_adds = len(re.findall(r"^[ \t]*CALL \d+, adds\[\d+\]:[ \t]*$", t, re.M))
    # 1 video + 3 graphics + 1 zoom + 1 sfx = 6
    if n_adds != 7:
        bad.append("expected 7 adds (1 video, 3 graphics, 1 CARD, 1 zoom, 1 sfx), got %d"
                   % n_adds)
    for want in ("THE ZOOMS", "SOUND EFFECTS", "builtin:zoom",
                 "library:sound:"):
        if want not in t:
            bad.append("the plan never names %r" % want)
    if "WHEN A NUMBER LANDS" not in t:
        bad.append("a beat ruled `card` does not carry its card condition")
    return bad


if __name__ == "__main__":
    bad = legs()
    for b in bad:
        print("  [FAIL] %s" % b)
    if not bad:
        print("  [ok] every ruled family reaches the plan as an add")
        print("  [ok] zoom is an effect, sfx is an audio item, both named")
        print("  [ok] a card beat carries its condition and hero")

    print("\n  RED PROOF")
    red_ok = True
    # A VERIFIED FAMILY WITH NO EMITTER is the exact defect: not dropped, so
    # not named; not emitted, so gone.
    P.FAMILY_MAP["cutaway"]["verified"] = True
    r = copy.deepcopy(BASE)
    r["plan"][0]["treatment"] = ["text", "cutaway"]
    try:
        emit(r)
        print("    a verified family with no emitter -> NOT RAISED")
        red_ok = False
    except P.Incomplete as e:
        named = "cutaway" in str(e)
        print("    a verified family with no emitter -> RAISED, names it: %s"
              % named)
        red_ok &= named
    finally:
        P.FAMILY_MAP["cutaway"]["verified"] = False

    # and the green half: unverified -> dropped AND named, no raise
    try:
        t2 = emit(r)
        ok = "cutaway" in t2.split("RULED BUT NOT")[1][:200]
        print("    the same family unverified   -> dropped and named: %s" % ok)
        red_ok &= ok
    except P.Incomplete as e:
        print("    the same family unverified   -> RAISED (should not): %s"
              % str(e)[:60])
        red_ok = False

    ok = not bad and red_ok
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
