#!/usr/bin/env python3
"""SMOKE — a narrow scope must be anchored to the brief, and fidelity must say so.

THE RUN THIS COMES FROM. Brief: "Cut this into a punchy vertical short. Remove
silence and filler. Keep the meaning intact. Burn readable captions." The agent
set, in its own words:

    mode: "targeted_change", families: ["caption","cut"]
    why:  "Request asks specifically to remove silence/filler (cut) and burn
           captions; it names no other family, so nothing else is added."

Seven beats then came back `treatment: ["none"]`, every `why` explaining only
the cut. Not restraint — the treatment axis was closed one stage earlier, and
the beat rulings could not reach it. The word "punchy" is the set_spec prompt's
OWN first example of a full_edit vibe; both signals were in the brief and the
narrow one won.

Then `spec_fidelity` graded it FAITHFUL, because `_asked` comes out of the spec
THE AGENT WROTE. A run that correctly places nothing and a run that wrongly
scoped itself to nothing were indistinguishable at that gate.

TWO LEGS, TWO STAGES:
  ANCHOR  — targeted_change needs the brief's own words showing an edit already
            exists, verified by substring. Not a keyword list: those learn a
            population instead of a property.
  GRADE   — with no anchor, fidelity reports SELF_SCOPED, not FAITHFUL.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agentic_editor_app as A                                 # noqa: E402

RAW = ("Cut this into a punchy vertical short. Remove silence and filler. "
       "Keep the meaning intact. Burn readable captions.")
REEDIT = "the captions are too small, make the captions bigger"


def anchor_legs():
    bad = []

    # 1. raw footage + named changes -> targeted_change must be REFUSED
    try:
        A.normalize_spec({"mode": "targeted_change", "families": ["caption", "cut"]},
                         brief=RAW)
        bad.append("a raw-footage brief was accepted as targeted_change with no anchor")
    except ValueError as e:
        if "edit ALREADY" not in str(e) and "raw footage" not in str(e):
            bad.append("refused, but not for the anchor reason: %s" % str(e)[:80])

    # 2. a PARAPHRASE is not evidence
    try:
        A.normalize_spec({"mode": "targeted_change", "families": ["caption"],
                          "existing_edit_quote": "they already have an edit"},
                         brief=RAW)
        bad.append("a paraphrased quote was accepted as an anchor")
    except ValueError as e:
        if "does not appear in the brief" not in str(e):
            bad.append("paraphrase refused for the wrong reason: %s" % str(e)[:80])

    # 3. a REAL re-edit, quoting the brief, is allowed through
    try:
        sc = A.normalize_spec(
            {"mode": "targeted_change", "families": ["caption"],
             "existing_edit_quote": "make the captions bigger"}, brief=REEDIT)
        if sc["mode"] != "targeted_change":
            bad.append("a genuine re-edit did not survive normalisation")
    except ValueError as e:
        bad.append("a genuine re-edit was refused: %s" % str(e)[:90])

    # 4. full_edit is never gated on the anchor
    try:
        A.normalize_spec({"mode": "full_edit"}, brief=RAW)
    except ValueError as e:
        bad.append("full_edit was gated on the anchor: %s" % str(e)[:80])
    return bad


def grade_legs():
    bad = []
    built = {"placements": [{"family": "cut"}], "cut_made": True}

    st, _, _, why = A.spec_fidelity(
        {"mode": "targeted_change", "families": ["cut"]},
        [{"family": "cut"}], cut_made=True)
    if st != A.FIDELITY_SELF_SCOPED:
        bad.append("an unanchored scope still graded %s, not SELF_SCOPED" % st)
    if "UNCHECKED" not in why:
        bad.append("the SELF_SCOPED reason does not say the scope is unchecked")

    st2, _, _, why2 = A.spec_fidelity(
        {"mode": "targeted_change", "families": ["cut"],
         "existing_edit_quote": "shorten the intro"},
        [{"family": "cut"}], cut_made=True)
    if st2 != A.FIDELITY_OK:
        bad.append("an ANCHORED scope did not grade FAITHFUL (got %s)" % st2)
    if "anchored to the brief" not in why2:
        bad.append("FAITHFUL does not name what anchored it")
    return bad


if __name__ == "__main__":
    a, g = anchor_legs(), grade_legs()
    for b in a:
        print("  [FAIL] anchor %s" % b)
    for b in g:
        print("  [FAIL] grade  %s" % b)
    if not a:
        print("  [ok] raw footage + named changes cannot be a targeted_change")
        print("  [ok] a paraphrase is refused; the brief's own words are required")
        print("  [ok] a genuine re-edit still passes, and full_edit is ungated")
    if not g:
        print("  [ok] an unanchored scope grades SELF_SCOPED, not FAITHFUL")
        print("  [ok] FAITHFUL names the quote that anchored it")

    ok = not a and not g
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
