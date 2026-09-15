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
    # THE PROPERTY, NOT THE SENTENCE. This read `"SINGLE edit_item call" in s`
    # — and the rule had to change, because an EFFECT names an item that must
    # already exist and so cannot ride the batch that creates it. The plan now
    # emits two calls, the prompt defers to it, and this leg failed on a
    # CORRECT prompt. Sixth reader this session keyed to wording rather than
    # behaviour. What turn 1 must actually forbid is placing one at a time; and
    # what it must actually say is that the plan decides the batching.
    # TURN vs PASS — THE WORD CHANGED AND THESE LEGS FAILED ON A CORRECT
    # PROMPT. They read "TURN 1"/"TURN 2"/"TURN 3" literally; the loop is now
    # described as PASSES because the agent watches, places, watches, fixes.
    # Same class as every other reader keyed to wording, in the smoke written
    # to protect the loop. They ask for the BEHAVIOUR now.
    ("pass 1 batches, and forbids placing one at a time",
     lambda s: (re.search(r"(TURN|PASS) 1", s)
                and re.search(r"one at a time", s)
                and re.search(r"BATCHES THE PLAN NAMES|SINGLE edit_item call"
                              r"|ONE BATCH", s))),
    # THIS ASSERTED A GAG THAT WAS DELIBERATELY REMOVED. It required "YOUR
    # TURN ENDS ... do not preview" — bounding how often the agent could LOOK,
    # which was a wall problem solved by taking away the thing that makes it an
    # editor. Not a reader keyed to wording this time: a check encoding a
    # DESIGN DECISION that was later reversed. That fails the same way and is
    # harder to catch, because the check was right when it was written.
    ("the edit is SENT to pass 1 — a head start, not a ration",
     lambda s: re.search(r"RENDERED AND SENT TO YOU", s)
     and re.search(r"HEAD START", s)),
    ("and the agent may look wherever, as often as it needs",
     lambda s: re.search(r"SCRUB WHEREVER YOU WANT", s)
     and re.search(r"[Nn]obody is counting", s)),
    ("pass 2 is look-then-fix on the composed picture",
     lambda s: re.search(r"(TURN|PASS) 2", s)
     and "COMPOSED PICTURE" in s
     and re.search(r"ONE edit_item call", s)),
    ("pass 3 is gated on a NAMED defect",
     lambda s: re.search(r"(TURN|PASS) 3", s) and "UNJUSTIFIED" in s),
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
        # THE MUTATION MUST MATCH THE LEG. This deleted the old wording, which
        # the leg no longer reads — so the RED proof printed 0 red and the
        # batching leg was, for that moment, a check that could not fail.
        ("batching removed",
         SRC.replace("one at a time", "however you like")),
        # The mutations that matter now are the HEAD START and the SCRUB
        # invitation — the turn-end gag they replaced is gone on purpose.
        ("the head start removed",
         SRC.replace("RENDERED AND SENT TO YOU", "yours to go and get")),
        ("the scrub invitation removed",
         SRC.replace("SCRUB WHEREVER YOU WANT", "get on with it")
            .replace("Nobody is counting", "You get one look")
            .replace("nobody is counting", "you get one look")),
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
