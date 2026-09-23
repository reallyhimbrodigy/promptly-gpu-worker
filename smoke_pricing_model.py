#!/usr/bin/env python3
"""The pricing arithmetic, and the one thing it must never do: move a constant."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pricing_model as P                                      # noqa: E402

FAILS, NLEGS = [], 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-46s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    # L0 THE PEG IS THE PEG. credit_prices.py charges ceil(rate x 10), so one
    # of our credits IS one tenth of a ChatCut credit. If these two ever
    # disagree, every number in the model is quoted against a different
    # currency than the one we actually charge.
    import credit_prices as C
    leg("L0 the_peg_matches_what_we_charge",
        P.OUR_PER_THEIRS == C.OUR_PER_THEIRS,
        "model %d, credit_prices %d" % (P.OUR_PER_THEIRS, C.OUR_PER_THEIRS))

    # L1 THE x10 RULE IS ceil, NEVER round. Rounding down under-prices a video
    # every time it is used, and the edit still succeeds, so nothing surfaces
    # it — the same reason every row in credit_prices.py is ceil.
    bad = [c for c in (0.01, 0.11, 0.4, 1.0, 2.2175, 4.999)
           if P.our_credits_per_video(c) < c * P.OUR_PER_THEIRS]
    leg("L1 never_rounds_a_video_down", not bad, "under-priced at: %s" % (bad or "none"))

    # L2 COST_PER_RENDER IS ONLY RIGHT AT ONE COST, and the model says which.
    # This is the whole claim: "1 video = 10 credits" asserts an edit costs
    # exactly ONE ChatCut credit, which nobody has measured.
    exact = [c for c in (0.5, 1.0, 1.5, 2.0)
             if P.our_credits_per_video(c) == P.COST_PER_RENDER_TODAY]
    leg("L2 cost_per_render_is_right_only_at_one_credit",
        exact == [1.0], "matches today's 10 credits at C = %s" % exact)

    # L3 BREAK-EVEN FALLS AS THE CREDIT PRICE RISES. A model where a dearer
    # credit made a tier safer would be inverted, and the sign of that error
    # is invisible in a table of plausible-looking numbers.
    cheap = dict((n, v) for n, _p, _v, v in P.max_sustainable_cost(0.1225))
    dear = dict((n, v) for n, _p, _v, v in P.max_sustainable_cost(0.25))
    wrong = [n for n in cheap if cheap[n] is not None and dear[n] >= cheap[n]]
    leg("L3 break_even_falls_as_credits_cost_more", not wrong,
        "inverted for: %s" % (wrong or "none"))

    # L4 THE FREE TIER HAS NO BREAK-EVEN AND MUST NOT CLAIM ONE. Price 0
    # divided by anything is 0, and a 0 in a break-even column reads as "breaks
    # even immediately" rather than "never" — absence rendered as a value.
    free = [v for n, _p, _v, v in P.max_sustainable_cost(0.1225) if n == "free"]
    leg("L4 free_tier_reports_no_break_even", free == [None],
        "free break-even = %r (None, not 0)" % free[0])

    # L5 IT MOVES NO CONSTANT. Zac: "Don't change any constants until Zac has
    # seen it." Asserted mechanically rather than promised in a comment.
    src = open(os.path.join(HERE, "pricing_model.py"), encoding="utf-8").read()
    writes = [w for w in ("import credits", "TIER_ALLOWANCE =", "VIDEOS_LIMIT =",
                          "COST_PER_RENDER =", "open(", "write(")
              if w in src]
    leg("L5 the_model_writes_nothing", not writes,
        "write-ish constructs in the model: %s" % (writes or "none"))

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
