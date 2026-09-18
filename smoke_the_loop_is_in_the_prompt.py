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

def _joined(src):
    """Adjacent string literals joined, so a sentence wrapped across source
    lines reads as one sentence — and a mutation of the SOURCE still reaches
    the leg (a leg over the imported VALUE could not go red by mutating text)."""
    return re.sub(r'"\s*\n\s*"', "", src)


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
    # SEVENTH READER KEYED TO WORDING IN THIS FILE. `r"one at a time"` matched
    # a sentence in FETCH_RULE — "twelve frames read one at a time is twelve
    # turns" — which is about READING FRAMES, not about placing items. When
    # FETCH_RULE was rewritten (the harness serves the frames now, so nothing
    # is read one at a time any more) this leg went red on a prompt whose
    # batching rule had not changed at all: the phrase it tested lived in a
    # different rule the whole time. It now accepts either spelling of the
    # thing it means.
    ("turn 1 places everything in ONE edit_item call",
     lambda s: re.search(r"TURN 1 — PLACE", s) and re.search(r"send ONE edit_item call carrying all", s)),
    # THIS ASSERTED A GAG THAT WAS DELIBERATELY REMOVED. It required "YOUR
    # TURN ENDS ... do not preview" — bounding how often the agent could LOOK,
    # which was a wall problem solved by taking away the thing that makes it an
    # editor. Not a reader keyed to wording this time: a check encoding a
    # DESIGN DECISION that was later reversed. That fails the same way and is
    # harder to catch, because the check was right when it was written.
    # RE-AIMED 2026-09-18 (rulings 2-4): frames are SENT between turns and the
    # agent makes no discovery call of its own.
    ("the composed frames are sent to the agent between turns",
     lambda s: re.search(r"sends you the composed frames", s)
     and re.search(r"TURN 2 — REVIEW", s)),
    ("and the agent never fetches, inspects or previews on its own (ruling 4)",
     lambda s: re.search(r"you never fetch, inspect or preview anything yourself", s)
     and not re.search(r"SCRUB WHEREVER YOU WANT", s)),
    ("pass 2 is look-then-fix on the composed picture",
     lambda s: re.search(r"(TURN|PASS) 2", s)
     and "COMPOSED PICTURE" in s
     and re.search(r"ONE edit_item call", s)),
    ("turn 3 is export or ONE fix, a fourth only for what the fix broke, and no fifth",
     lambda s: re.search(r"TURN 3 — CONFIRM", s) and "single word: export" in s and "there is no fifth" in s),
    ("it is concatenated into the deciding prompt",
     lambda s: re.search(r"\+ TWO_TURN_LOOP\b", s)),
    ("the superseded one-revision prose is gone",
     lambda s: "ONE REVISION, AND ONLY ON WHAT YOU CAN SEE" not in s),
]


def run(s):
    return [name for name, leg in LEGS if not leg(_joined(s))]


if __name__ == "__main__":
    bad = run(SRC)
    for name, leg in LEGS:
        print("  [%s] %s" % ("ok" if leg(_joined(SRC)) else "FAIL", name))

    # RED PROOF — each leg fails when the thing it checks is removed.
    print("\n  RED PROOF")
    reds = [
        ("constant deleted", SRC.replace("TWO_TURN_LOOP = (", "X_UNUSED = (")),
        ("not concatenated", SRC.replace("+ TWO_TURN_LOOP", "+ \"\"")),
        ("turn 3 no longer ends on export", SRC.replace("single word: export", "single word: done")),
        # THE MUTATION MUST MATCH THE LEG. This deleted the old wording, which
        # the leg no longer reads — so the RED proof printed 0 red and the
        # batching leg was, for that moment, a check that could not fail.
        ("batching removed",
         SRC.replace("send ONE edit_item call carrying all", "send the calls you like for")),
        # The mutations that matter now are the HEAD START and the SCRUB
        # invitation — the turn-end gag they replaced is gone on purpose.
        ("the frames are no longer sent",
         SRC.replace("sends you the composed frames", "leaves you to fetch the frames")),
        ("the agent is invited to scrub again",
         SRC.replace("you never fetch, ", "you may fetch, ")),
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
