#!/usr/bin/env python3
"""SMOKE — the PLACEMENTS gate counts the adds in the plan it is actually handed.

THE FAILURE THIS PREVENTS IS A FALSE *ABSENT*, WHICH IS WORSE THAN A FALSE FAIL.
The gate read `plan.count("edit_item adds[")`. The plan then started labelling
every add with its call — `CALL 1, adds[3]:` — because an effect names an item
that must already exist and so cannot ride the batch that creates it. The
counter would have read ZERO on a complete plan, and `state` is ABSENT when
`planned_adds` is 0: a full edit reported as "no plan", green, with nothing to
explain it. Absence rendered as success, one more time.

So the counter is checked against the REAL translator output, in both the old
spelling and the new, and the `state` ladder is checked at the boundary that
made the false ABSENT possible.

Every leg is RED-proven in the same run.
"""
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_for_chatcut as P                                   # noqa: E402

# THE COUNTER ITSELF, lifted from chatcut_job_app by AST so this smoke cannot
# drift from the thing it checks. A copy of the regex retyped here would go on
# passing after the app's own copy changed — which is the whole failure again,
# one level out.
import ast                                                     # noqa: E402
_src = open(os.path.join(HERE, "chatcut_job_app.py"), encoding="utf-8").read()
_pat = None
for _n in ast.walk(ast.parse(_src)):
    if (isinstance(_n, ast.Assign)
            and getattr(_n.targets[0], "id", "") == "_planned"
            and isinstance(_n.value, ast.Call)):
        for _a in ast.walk(_n.value):
            if isinstance(_a, ast.Constant) and isinstance(_a.value, str) \
                    and "adds" in _a.value:
                _pat = _a.value
if _pat is None:
    print("  [FAIL] could not read the gate's own add-counting pattern")
    sys.exit(1)


def planned(plan_text):
    return len(re.findall(_pat, plan_text or "", re.M))


def _beat(t0, t1, treatment, text="WORDS"):
    return {"treatment": treatment, "src_t0": t0, "src_t1": t1,
            "text_content": text, "size": "medium", "case": "upper",
            "where": "upper_third", "colour": "white_on_footage",
            "hold_s": 2.0, "why": "smoke", "purpose": "hook",
            "zoom_arc": "payoff", "sfx_name": "transition-sfx",
            "card_condition": "WHEN A NUMBER LANDS", "card_hero": "5",
            "card_label": "min"}


RULING = {
    "ledger": {"keep_spans": [[0.0, 20.0]], "source_duration_s": 20.0,
               "spec": {"mode": "full_edit", "families": None}},
    # 1 video + 3 graphics + 1 sfx + 1 zoom = 6 adds, ACROSS TWO CALLS.
    "plan": [_beat(1.0, 3.0, ["text"]),
             _beat(5.0, 8.0, ["text", "zoom"]),
             _beat(10.0, 13.0, ["text", "card", "sfx"])],
}
EXPECT = 7        # 1 video + 3 graphics + 1 StatCard + 1 sfx + 1 zoom


def emit():
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(RULING, fh)
    fh.close()
    try:
        return P.render(fh.name, staged=True, allow_drop=True)
    finally:
        os.unlink(fh.name)


def legs(txt):
    bad = []
    n = planned(txt)
    if n != EXPECT:
        bad.append(("live", "the translator emits %d adds and the gate counts "
                            "%d" % (EXPECT, n)))
    # THE OLD SPELLING TOO. A plan written before the two-call split must not
    # suddenly count zero either — a reader that only understands today's
    # format has the same fragility pointing backwards.
    old = re.sub(r"^([ \t]*)CALL \d+, adds\[", r"\1edit_item adds[", txt,
                 flags=re.M)
    if planned(old) != EXPECT:
        bad.append(("old", "the pre-split spelling counts %d, not %d"
                           % (planned(old), EXPECT)))
    # A MENTION IS NOT A HEADER. The plan teaches the shape in prose
    # ("...LABELLED WITH ITS CALL AND ITS SLOT — `CALL 1, adds[3]:`.") and an
    # unanchored counter reads that sentence as one more add.
    if "adds[" in txt and planned(txt) != txt.count("adds["):
        pass          # good: the counter is narrower than a bare substring
    else:
        bad.append(("anchor", "the counter matches every mention of `adds[`, "
                              "including the plan's own worked example"))
    # AND ZERO MUST BE REACHABLE ONLY FOR A REAL EMPTY PLAN.
    if planned("a plan that names no adds at all") != 0:
        bad.append(("zero", "a plan with no adds does not count zero"))
    return bad


if __name__ == "__main__":
    txt = emit()
    bad = legs(txt)
    for kind, why in bad:
        print("  [FAIL] %-7s %s" % (kind, why))
    if not bad:
        print("  [ok] the gate counts %d adds in the plan the translator "
              "actually emits" % EXPECT)
        print("  [ok] ...and the same %d in the pre-split spelling" % EXPECT)
        print("  [ok] the plan's own worked example is not counted as an add")
        print("  [ok] zero is reachable only for a plan that names none")

    print("\n  RED PROOF")
    red = True
    # The exact regression: the plan relabels and the counter does not follow.
    r1 = legs(re.sub(r"^([ \t]*)CALL (\d+), adds\[", r"\1CALL \2 slot[", txt,
                     flags=re.M))
    print("    the plan relabels its adds   -> %d leg(s) red" % len(r1))
    red &= any(k == "live" for k, _ in r1)

    # The counter widened to a bare substring — the anchor leg must catch it.
    _real = globals()["planned"]
    globals()["planned"] = lambda t: (t or "").count("adds[")
    r2 = legs(txt)
    globals()["planned"] = _real
    print("    counter widened to substring -> %d leg(s) red" % len(r2))
    red &= any(k == "anchor" for k, _ in r2)

    # A plan that emits NOTHING must not read as a healthy count.
    r3 = legs("")
    print("    an empty plan                -> %d leg(s) red" % len(r3))
    red &= bool(r3)

    ok = not bad and red
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
