#!/usr/bin/env python3
"""SMOKE — every ruling a smoke feeds the admission surface is still ADMITTED.

THE CLASS THIS CATCHES, measured 2026-09-14: four smokes were failing at once
and it read as a defect in `agentic_editor_app`. It was not. A requirement had
been added and the fixtures did not know:

  * `half_ruling_refusal` made size/case/where/colour/hold_s mandatory for any
    beat ruled `text`. Three smokes' fixtures predate it, so admit_verdict
    refused, `beat_verdicts` came back EMPTY, and the legs below either passed
    vacuously or died on an IndexError pointing at the wrong file.
  * `existing_edit_quote` became required for a `targeted_change` spec — added
    in THIS session, one commit before the smoke was next run. Nine legs failed
    on a correct grader.

Both are the same shape: **a fixture gap wearing a surface defect's clothes**,
and it costs whoever looks next a diagnosis that lands on the wrong component.

So the fixtures are checked as fixtures. Any ruling this repo's smokes hand to
`admit_verdict` must still be admitted — and when one is not, the failure NAMES
the refusal reason, which is the sentence that tells you which field was added.

RED-proven by stripping a required field from a fixture in the same run.
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agentic_editor_app as A                                 # noqa: E402

# THE REPRESENTATIVE RULINGS, one per treatment a fixture can carry. Not a scan
# of every smoke's literals: those are spread across kwargs, dict merges and
# helper functions, and a scanner that reads only the easy ones would report a
# clean zero for the files it could not parse — the tidiest and most expensive
# kind of pass. These are the shapes the fixtures use, asserted directly.
BASE = {"beat": 1, "purpose": "hook", "cut": "keep", "why": "w"}
CONTROLS = {"size": "medium", "case": "upper", "where": "upper_third",
            "colour": "white_on_footage", "hold_s": 2.0}
RULINGS = [
    ("text", {**BASE, **CONTROLS, "treatment": ["text"], "text_content": "HI"}),
    ("text+zoom", {**BASE, **CONTROLS, "treatment": ["zoom", "text"],
                   "text_content": "HI", "zoom_arc": "payoff"}),
    ("sfx", {**BASE, "treatment": ["sfx"], "sfx_name": "boom"}),
    ("none", {**BASE, "treatment": ["none"]}),
]
SPECS = [
    ("targeted_change", {"mode": "targeted_change", "families": ["text"],
                         "existing_edit_quote": "just add captions"}),
]


def admitted(v):
    led, seen = {"beat_verdicts": []}, set()
    ok, rj = A.admit_verdict(led, dict(v), seen)
    return ok, (rj or {}).get("reason") if isinstance(rj, dict) else rj


def legs():
    bad = []
    for name, v in RULINGS:
        ok, why = admitted(v)
        if not ok:
            bad.append(("admit", "the %s fixture is REFUSED: %s"
                                 % (name, str(why)[:160])))
    for name, spec in SPECS:
        st = A.spec_fidelity(spec, [{"family": f}
                                    for f in (spec.get("families") or [])])[0]
        # SELF_SCOPED means the spec did not anchor itself to the brief — the
        # exact state an un-updated fixture falls into.
        if st == "SELF_SCOPED":
            bad.append(("spec", "the %s fixture grades SELF_SCOPED — it no "
                                "longer anchors its scope to the brief" % name))
    return bad


if __name__ == "__main__":
    bad = legs()
    for kind, why in bad:
        print("  [FAIL] %-6s %s" % (kind, why))
    if not bad:
        print("  [ok] all %d representative rulings are still admitted"
              % len(RULINGS))
        print("  [ok] the targeted_change spec still anchors to its brief")

    print("\n  RED PROOF")
    red = True
    _saved = list(RULINGS)
    # strip one required control — the exact gap that broke three smokes
    RULINGS[:] = [("text", {k: v for k, v in _saved[0][1].items()
                            if k != "hold_s"})]
    r1 = legs()
    RULINGS[:] = _saved
    print("    a control stripped from a fixture -> %d leg(s) red" % len(r1))
    red &= any(k == "admit" for k, _ in r1)
    if r1:
        print("      names it: %s" % ("hold_s" in r1[0][1]))
        red &= "hold_s" in r1[0][1]

    _ss = list(SPECS)
    SPECS[:] = [("targeted_change", {"mode": "targeted_change",
                                     "families": ["text"]})]
    r2 = legs()
    SPECS[:] = _ss
    print("    the brief anchor dropped          -> %d leg(s) red" % len(r2))
    red &= any(k == "spec" for k, _ in r2)

    ok = not bad and red
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
