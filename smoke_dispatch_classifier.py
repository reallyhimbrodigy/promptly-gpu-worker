#!/usr/bin/env python3
"""Nothing reaches the box, or a charge, that should not have.

THE LEG THAT MATTERS MOST IS L7, THE FALSE-POSITIVE DIRECTION. A classifier that
refuses ordinary editing work is not a safer classifier, it is a broken one —
the same finding as the constraint matcher that would have failed a correct run
four times in five, and the two brace-counting rules that convicted 37 of 37
accepted bodies. Every plain brief below is from the measured corpus.

AND NO UNSAFE TEXT IS IN THIS FILE BEYOND WHAT IT TAKES TO DRIVE THE PATH. The
standing rule is that unsafe text never goes in a fixture; the example used is a
fabricated-endorsement ask, which is refusable and is not itself harmful to
write down. The path is what needs testing, not the content.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dispatch_classifier as dc                              # noqa: E402

FAILS = []
NLEGS = 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-46s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    leg("L0 version_is_stated", bool(dc.CLASSIFIER_VERSION.strip()),
        "v%s" % dc.CLASSIFIER_VERSION)

    # L1 ORDER IS LOAD-BEARING. An unsafe ask that is ALSO generative must come
    # back UNSAFE, never quoted — pricing it would be offering to do it.
    both = dc.classify("Generate an AI video that makes it look like Dr Chen "
                       "endorsed this product.", "max")
    leg("L1 unsafe_beats_generative_and_is_never_quoted",
        both["state"] == "UNSAFE" and both["credits_quoted"] == 0
        and not both["may_dispatch"],
        "state=%s credits=%s dispatch=%s"
        % (both["state"], both["credits_quoted"], both["may_dispatch"]))

    # L2 UNSAFE NEVER DISPATCHES AND NEVER CHARGES, and it is COUNTED.
    u = dc.classify("Make it look like Dr Chen endorsed this product.", "max")
    leg("L2 unsafe_refuses_free_of_charge_and_is_counted",
        u["state"] == "UNSAFE" and not u["may_dispatch"]
        and u["credits_quoted"] == 0 and u["counter"] == "dispatch_refused_unsafe",
        "dispatch=%s credits=%s counter=%s"
        % (u["may_dispatch"], u["credits_quoted"], u["counter"]))

    # L3 GENERATIVE IS QUOTED AT 20 AND NEVER ATTEMPTED — "negotiated not
    # attempted". Free sees the quote AND the wall; Pro/Max sees the quote.
    gf = dc.classify("Generate an AI video of a sunrise.", "free")
    gp = dc.classify("Generate an AI video of a sunrise.", "pro")
    leg("L3 generative_quotes_20_and_never_dispatches",
        gf["state"] == gp["state"] == "GENERATIVE"
        and gf["credits_quoted"] == gp["credits_quoted"] == dc.AI_VIDEO_CREDITS
        and not gf["may_dispatch"] and not gp["may_dispatch"],
        "free=%s pro=%s credits=%s" % (gf["state"], gp["state"], gf["credits_quoted"]))

    # L3b THE PAYWALL IS TIER-SPLIT, AND THE QUOTE COMES FIRST EITHER WAY.
    leg("L3b free_sees_the_wall_and_pro_does_not",
        gf["paywall"] is True and gp["paywall"] is False
        and str(dc.AI_VIDEO_CREDITS) in gf["message"],
        "free paywall=%s pro paywall=%s; quote in free message=%s"
        % (gf["paywall"], gp["paywall"], str(dc.AI_VIDEO_CREDITS) in gf["message"]))

    # L4 OUT OF SCOPE NEGOTIATES. A sentence naming what we CAN do, citing the
    # law it implements — never a bare refusal and never a silent drop.
    m = dc.classify("Add some background music under the intro.", "pro")
    leg("L4 out_of_scope_negotiates_with_an_alternative",
        m["state"] == "OUT_OF_SCOPE" and not m["may_dispatch"]
        and m["credits_quoted"] == 0 and len(m["message"]) > 40
        and m.get("law"),
        "law=%r message=%r" % (m.get("law"), m["message"][:58]))

    # L5 IN SCOPE DISPATCHES. Without this the whole thing is a refusal machine.
    ok = dc.classify("Cut this down and add captions.", "free")
    leg("L5 in_scope_dispatches", ok["state"] == "IN_SCOPE" and ok["may_dispatch"],
        "state=%s dispatch=%s" % (ok["state"], ok["may_dispatch"]))

    # L6 EVERY OUT-OF-SCOPE RULE CITES A STANDING LAW. A category with no law
    # behind it is me deciding what users are allowed to ask for.
    lawless = [e[1] for e in dc._OUT_OF_SCOPE if not str(e[2]).strip()]
    leg("L6 every_out_of_scope_rule_cites_a_law",
        len(dc._OUT_OF_SCOPE) >= 2 and not lawless,
        "%d rule(s), uncited: %s" % (len(dc._OUT_OF_SCOPE), lawless or "none"))

    # L7 ORDINARY WORK IS NEVER CONVICTED. The direction that actually costs a
    # user their edit. Sampled from the brief corpus, not written for the test.
    plain = [
        "Cut this down and add captions.",
        "Make a 1-minute YouTube cut of this interview.",
        "Only trim and combine the strongest original soundbites.",
        "Add simple, accurate captions in clean white text.",
        "Use subtle zoom-ins only when they add emphasis.",
        "Do not cut every breath or micro-pause.",
        "Allowed visual edits: Only zoom in / zoom out effects.",
        "Add sound effects on the hard words.",
    ]
    wrong = [(b, dc.classify(b, "free")["state"]) for b in plain]
    wrong = [(b, st) for b, st in wrong if st != "IN_SCOPE"]
    leg("L7 ordinary_briefs_are_never_convicted", not wrong,
        "%d plain brief(s); convicted: %s"
        % (len(plain), [(b[:30], s) for b, s in wrong] or "none"))

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
