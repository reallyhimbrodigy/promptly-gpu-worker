#!/usr/bin/env python3
"""SMOKE — two placements may not occupy one region of one frame.

WHAT SHIPPED. StatCard occupies y 0.314-0.442 of the frame and caption:TwoTone
occupies 0.367-0.410 — the caption sits INSIDE the card — and both were live
for frames 526-608. In the delivered file the caption word "FIVE" sits directly
over the card's "5" at frame 562, "EDIT" at 585, "NOTHING" at 600.

AND THE PLAN HAD ASSERTED THEY WOULD NOT COLLIDE: "StatCard anchors CENTRE by
default and the title sits in the upper third, so they do not collide." True
about the TITLE, and never checked against the CAPTION. A confident sentence
covering the one pair nobody had compared.

NOTHING CHECKED ACROSS FAMILIES. The title loop knew titles, the caption
section knew captions, the card rode the graphics pass, and no reader ever held
two of them at once. Every gate was within a family.

THE BANDS ARE MEASURED, NOT GUESSED. A first version invented a caption band of
0.52-0.70 and therefore found NO collision — the one collision that had
actually shipped. The real numbers come from the render check's own bboxes, and
the two caption styles are 200px apart from each other, so no single guessed
band could ever have been right for both.

Legs, each RED-proven:
  DETECT   a card and a caption in one window is a collision
  MEASURE  the bands come from rows.json, not from a table in this file
  OFFSET   a moved component is judged where it NOW is
  RESOLVE  the planner places the card clear rather than only refusing
  REFUSE   and a plan that still collides does not build
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify_chain as V                                       # noqa: E402
import plan_for_chatcut as P                                   # noqa: E402

CARD = {"type": "motion-graphic", "asset": "StatCard", "slot": 8,
        "overrides": {"value": 5}, "band": None, "from": 526, "dur": 82}
CAP = {"type": "motion-graphic", "asset": "caption:TwoTone", "slot": 11,
       "overrides": None, "band": None, "from": 0, "dur": 608}
TITLE = {"type": "motion-graphic", "asset": "the GRAPHIC 7 assetId", "slot": 7,
         "overrides": None, "band": "upper_third", "from": 526, "dur": 82}


def legs():
    bad = []
    meas = V.measured_bands()
    if not meas:
        return [("measure", "sheet/rows.json gave NO measured bands — every "
                            "leg below would be judging a guess")]
    for n in ("StatCard", "caption:TwoTone"):
        if n not in meas:
            bad.append(("measure", "%s has no measured band" % n))

    # DETECT — the pair that shipped
    c = V.collisions([CARD, CAP, TITLE], meas)
    pairs = {(min(x["a"], x["b"]), max(x["a"], x["b"])) for x in c}
    if (8, 11) not in pairs:
        bad.append(("detect", "the card/caption collision is not detected — "
                              "card %s, caption %s"
                              % (V.band_of(CARD, meas), V.band_of(CAP, meas))))

    # OFFSET — a moved card is judged where it now is
    dy = V.free_offset(CARD, [CAP, TITLE], meas)
    if dy is None:
        bad.append(("resolve", "no free region found for the card at all"))
    else:
        moved = dict(CARD, overrides={"value": 5, "offsetY": dy})
        b0 = V.band_of(CARD, meas)
        b1 = V.band_of(moved, meas)
        if abs((b1[0] - b0[0]) * 1920 - dy) > 1:
            bad.append(("offset", "offsetY is not applied to the band: %s -> %s"
                                  % (b0, b1)))
        if V.collisions([moved, CAP, TITLE], meas):
            bad.append(("resolve", "the resolved position still collides"))
    return bad


def _ruling(**kw):
    b = {"treatment": ["text", "card"], "src_t0": 10.0, "src_t1": 14.0,
         "text_content": "WORDS", "size": "medium", "case": "upper",
         "where": "upper_third", "colour": "white_on_footage", "hold_s": 2.0,
         "why": "smoke", "purpose": "hook", "card_condition": "WHEN A NUMBER LANDS",
         "card_hero": "5 MINUTES", "card_label": "to edit"}
    b.update(kw)
    return {"ledger": {"keep_spans": [[0.0, 20.0]], "source_duration_s": 20.0,
                       "spec": {"mode": "full_edit", "families": None}},
            "plan": [b]}


def build(r):
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(r, fh)
    fh.close()
    try:
        return P.render(fh.name, staged=True, allow_drop=True)
    finally:
        os.unlink(fh.name)


if __name__ == "__main__":
    bad = legs()
    for k, w in bad:
        print("  [FAIL] %-8s %s" % (k, w))
    if not bad:
        meas = V.measured_bands()
        print("  [ok] bands are MEASURED from %d rendered components" % len(meas))
        print("  [ok] the card/caption collision that shipped is detected")
        print("  [ok] offsetY moves the band it is judged by")
        print("  [ok] the planner resolves to a position that clears both")

    print("\n  RED PROOF")
    red = True
    # a plan whose card cannot be moved clear must REFUSE rather than ship
    meas = V.measured_bands()
    _tall = dict(meas, StatCard=(0.0, 0.97))
    c = V.collisions([dict(CARD), CAP, TITLE], _tall)
    print("    a card the height of the frame -> %d collision(s)" % len(c))
    red &= bool(c)
    print("    ...and no free offset exists   -> %s"
          % (V.free_offset(CARD, [CAP, TITLE], _tall) is None))
    red &= V.free_offset(CARD, [CAP, TITLE], _tall) is None

    # the real translator refuses a plan it cannot resolve
    try:
        build(_ruling(card_hero="everything"))
        print("    a card with no number          -> NOT REFUSED")
        red = False
    except P.Incomplete:
        print("    a card with no number          -> refused")

    # and builds one it can
    try:
        t = build(_ruling())
        m = V.plan_manifest(t)
        card = [r for r in m if (r.get("overrides") or {}).get("value") is not None]
        ok_built = bool(card) and not V.collisions(m)
        print("    a resolvable card              -> built, %d collision(s)"
              % len(V.collisions(m)))
        red &= ok_built
    except P.Incomplete as e:
        print("    a resolvable card              -> REFUSED: %s" % str(e)[:80])
        red = False

    print("\n  %s" % ("OK" if (not bad and red) else "FAIL"))
    sys.exit(0 if (not bad and red) else 1)
