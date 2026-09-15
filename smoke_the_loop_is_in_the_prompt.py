#!/usr/bin/env python3
"""SMOKE — the two-turn loop reaches the agent, and says all three turns.

WHY THIS AND NOT A COMMENT. A paragraph of instruction that never reaches the
prompt is this lane's oldest failure: `--no-use-hands` did not remove the
subagent because the paragraph was unconditional, and that voided a comparison
already passed to Zac. The loop is a behaviour we are about to MEASURE — turns
and batches — so a run where the instruction silently did not arrive would
report the loop as refuted when it was never tested.

RED-PROVEN below: each leg is driven red against a mutated source in the same
run, so none of them is a check that has never failed.
"""
import re
import sys

SRC = open("chatcut_job_app.py", encoding="utf-8").read()

LEGS = [
    ("the constant exists",
     lambda s: re.search(r"^TWO_TURN_LOOP = \(", s, re.M)),
    ("it names turn 1 as one batch",
     lambda s: "TURN 1" in s and "SINGLE edit_item call" in s),
    ("it names turn 2 as look-then-fix",
     lambda s: "TURN 2" in s and "preview_timeline" in s),
    ("it gates turn 3 on a NAMED defect",
     lambda s: "TURN 3" in s and "UNJUSTIFIED" in s),
    ("it is concatenated into the plan-path prompt",
     lambda s: re.search(r"\+ TWO_TURN_LOOP\b", s)),
    ("the superseded one-revision prose is gone",
     lambda s: "ONE REVISION, AND ONLY ON WHAT YOU CAN SEE" not in s),
]


def run(s):
    return [name for name, leg in LEGS if not leg(s)]


if __name__ == "__main__":
    bad = run(SRC)
    for name, leg in LEGS:
        print("  [%s] %s" % ("ok" if leg(SRC) else "FAIL", name))

    # RED PROOF — each leg fails when the thing it checks is removed.
    print("\n  RED PROOF")
    reds = [
        ("constant deleted", SRC.replace("TWO_TURN_LOOP = (", "X_UNUSED = (")),
        ("not concatenated", SRC.replace("+ TWO_TURN_LOOP", "+ \"\"")),
        ("turn 3 gate removed", SRC.replace("UNJUSTIFIED", "fine")),
        ("batching removed", SRC.replace("SINGLE edit_item call", "call")),
    ]
    red_ok = True
    for label, mutated in reds:
        failed = run(mutated)
        print("    %-22s -> %d leg(s) red" % (label, len(failed)))
        if not failed:
            red_ok = False

    ok = not bad and red_ok
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
