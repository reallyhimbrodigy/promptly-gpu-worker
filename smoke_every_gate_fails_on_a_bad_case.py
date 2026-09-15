#!/usr/bin/env python3
"""SMOKE — every gate in the chain has been shown to FAIL, not only to pass.

A GATE THAT HAS ONLY EVER PASSED IS UNTESTED. Four of this session's gates were
green over defects they could not see:
  * the PLACEMENTS gate confirmed 8 of 8 while the translator had dropped half
    the rulings;
  * `items_added` counted adds SENT while ChatCut resolved an id PREFIX;
  * a pixel check reported ZERO placements missing on the file where the card
    is definitively absent;
  * and the plan asserted the card and the title were one placement on a
    component with no card properties.
Every one of them passed. None of them had been shown to fail.

So each gate is driven here with a KNOWN-BAD input and must refuse it — and
with a known-good one, so a gate that refuses everything is caught too. The
pixel and detector judgments were extracted into `verify_chain` precisely so
they can be exercised without spending a run: a gate whose decision only ever
executes inside a container against live pixels can only be tested by paying
for it.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify_chain as V                                       # noqa: E402
import plan_for_chatcut as P                                   # noqa: E402
import face_bands as FB                                        # noqa: E402

fails = []


def gate(name, bad_refused, good_accepted, detail=""):
    ok = bad_refused and good_accepted
    if not ok:
        fails.append("%s: %s" % (name, detail or (
            "the BAD case was accepted" if not bad_refused
            else "the GOOD case was refused")))
    print("  [%s] %-26s bad refused=%-5s good accepted=%s"
          % ("ok" if ok else "FAIL", name, bad_refused, good_accepted))


def _beat(**kw):
    d = {"treatment": ["text"], "src_t0": 1.0, "src_t1": 3.0,
         "text_content": "WORDS", "size": "medium", "case": "upper",
         "where": "upper_third", "colour": "white_on_footage", "hold_s": 2.0,
         "why": "smoke", "purpose": "hook", "zoom_arc": "payoff",
         "sfx_name": "transition-sfx", "card_condition": "WHEN A NUMBER LANDS",
         "card_hero": "5 MINUTES", "card_label": "to edit"}
    d.update(kw)
    return d


def plan_of(beats):
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump({"ledger": {"keep_spans": [[0.0, 20.0]],
                          "source_duration_s": 20.0,
                          "spec": {"mode": "full_edit", "families": None}},
               "plan": beats}, fh)
    fh.close()
    try:
        return P.render(fh.name, staged=True, allow_drop=True)
    finally:
        os.unlink(fh.name)


if __name__ == "__main__":
    good_plan = plan_of([_beat(), _beat(src_t0=10.0, src_t1=14.0,
                                        treatment=["text", "card"])])
    man = V.plan_manifest(good_plan)

    # ── HOP 2 — an assetId nobody registered ────────────────────────────────
    reg = {"GRAPHIC 1": "a", "GRAPHIC 2": "b", "StatCard": "c",
           "caption:TwoTone": "d"}
    gate("hop2 unregistered asset",
         bool(V.hop2_prestage(man, {})),
         not V.hop2_prestage(man, reg))

    # ── HOP 3 — an add that never became an item ────────────────────────────
    items_all = [{"kind": "item", "timelineRange": {"fromFrame": r["from"]}}
                 for r in man if r["type"] != "effect"]
    gate("hop3 add never placed",
         bool(V.hop3_placed(man, [])),
         not V.hop3_placed(man, items_all))

    # ── HOP 4 — an item that arrived without the ruling ─────────────────────
    empty = {r["from"]: {"propertyOverrides": {}} for r in man}
    full = {r["from"]: {"propertyOverrides": dict(r.get("overrides") or {})}
            for r in man}
    gate("hop4 override dropped",
         bool(V.hop4_carries(man, empty)),
         not V.hop4_carries(man, full))

    # ── HOP 5 — two tracks whose pixels share the frame ─────────────────────
    # 1000-pixel masks. The bad pair overlaps on 400; the good pair is disjoint.
    A = [1] * 500 + [0] * 500
    B = [0] * 100 + [1] * 500 + [0] * 400      # shares 400 px with A
    C = [0] * 500 + [1] * 500                  # shares 0 with A
    gate("hop5 pixels overlap",
         bool(V.masks_overlap({"V2": A, "V3": B})),
         not V.masks_overlap({"V2": A, "V3": C}))

    # ── HOP 6 — a placement sitting on a face or on the source's text ───────
    # production's own band table: top is y 120-640 => 0.0625-0.333
    on_face = V.sits_on((0.05, 0.30), {"top"}, FB.band_to_fraction)
    clear = V.sits_on((0.70, 0.90), {"top"}, FB.band_to_fraction)
    gate("hop6 sits on a face", bool(on_face), not clear)

    # ── COLLISION — two placements ruled into one region ────────────────────
    meas = V.measured_bands()
    card = {"type": "motion-graphic", "asset": "StatCard", "slot": 8,
            "overrides": {"value": 5}, "band": None, "from": 526, "dur": 82}
    cap = {"type": "motion-graphic", "asset": "caption:TwoTone", "slot": 11,
           "overrides": None, "band": None, "from": 0, "dur": 608}
    moved = dict(card, overrides={"value": 5, "offsetY": 288})
    gate("collision at plan time",
         bool(V.collisions([card, cap], meas)),
         not V.collisions([moved, cap], meas))

    # ── AND THE TRANSLATOR ITSELF REFUSES A RULING IT CANNOT EXECUTE ────────
    _bad_refused = False
    try:
        plan_of([_beat(treatment=["text", "card"], card_hero="everything")])
    except P.Incomplete:
        _bad_refused = True
    gate("card with no number", _bad_refused, bool(good_plan))

    print()
    if fails:
        for f in fails:
            print("  FAILED: %s" % f)
        print("\n  FAIL")
        sys.exit(1)
    print("  OK — every gate refused its known-bad case and accepted its good one")
    sys.exit(0)
