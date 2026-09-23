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

    # L6 THE STORE'S CUT ONLY EVER REDUCES. A cut applied the wrong way round
    # inflates every margin in the table and looks entirely plausible.
    bad = [n for n, c in P.CHANNEL_CUT.items() if not (0 <= c < 1)
           or P.net_of_cut(100.0, c) >= 100.0]
    leg("L6 every_channel_cut_reduces_revenue", P.CHANNEL_CUT and not bad,
        "%d channel(s), bad: %s" % (len(P.CHANNEL_CUT), bad or "none"))

    # L7 THE FREE LOAD IS DIVIDED BY THE PAYERS, NOT BY THE FREE USERS. The
    # question is what each SUBSCRIBER carries; dividing by 1,975 free users
    # instead of 20 payers understates it by a factor of ~99 and still looks
    # like a per-user number.
    # DRIVEN THROUGH THE FUNCTION, not read off the constant. My first version
    # asserted FREE_LOAD["free_videos_per_paying_subscriber"] — a value
    # precomputed in the dict — so dividing by the 1,975 free users inside
    # free_load_per_subscriber() changed the code and not the leg, and the
    # mutation passed. A leg that reads a constant is testing arithmetic
    # someone already did, not the arithmetic that runs.
    f = P.FREE_LOAD
    got = P.free_load_per_subscriber(1.0, 1.0)          # unit cost -> videos carried
    expect = f["free_videos_30d"] / f["paid_users"]
    leg("L7 free_load_is_per_paying_subscriber",
        abs(got - expect) < 1e-9 and f["paid_users"] < f["free_users"],
        "%.1f videos per payer from the function (= %d free / %d payers)"
        % (got, f["free_videos_30d"], f["paid_users"]))

    # L8 ZERO PAYING SUBSCRIBERS IS NOT ZERO LOAD. It is undefined, and a 0
    # here would read as "the free tier costs nothing" at the exact moment it
    # costs everything — absence rendered as a value, in the money table.
    leg("L8 no_payers_is_not_free",
        P.free_load_per_subscriber(1.0, 0.1225, free_videos=2429, paid_users=0)
        == float("inf"),
        "0 payers -> %r" % P.free_load_per_subscriber(1.0, 0.1225, 2429, 0))

    # L9 true_margin SUBTRACTS ALL THREE. A margin missing any one of the cut,
    # own usage or the free share is a number answering a question nobody
    # asked — and it is the optimistic one every time.
    r = P.true_margin("pro monthly", 1.0, 0.1225,
                      P.CHANNEL_CUT["App Store, year 1 (30%)"], at_full_use=False)
    ok = abs(r["margin"] - (r["net_of_cut"] - r["own_usage_cost"]
                            - r["free_load_share"])) < 1e-9
    leg("L9 true_margin_subtracts_cut_usage_and_free", ok and r["net_of_cut"] < r["list"],
        "list %.2f -> net %.2f - own %.2f - free %.2f = %.2f"
        % (r["list"], r["net_of_cut"], r["own_usage_cost"], r["free_load_share"],
           r["margin"]))

    # L10 A HIGHER CONVERSION RATE MUST LOWER THE LOAD PER SUBSCRIBER. Free
    # volume is held constant, so more payers share the same 2,429 videos.
    # A model where converting made it worse would be inverted, and the sign
    # is invisible in a table of plausible numbers.
    loads = [P.free_videos_each(r) for r in P.CONVERSION_SWEEP]
    leg("L10 more_subscribers_means_less_load_each",
        all(a > b for a, b in zip(loads, loads[1:])),
        "%s" % ["%.1f" % x for x in loads])

    # L11 THE CONVERSION DENOMINATOR IS THE ACTIVE POPULATION. Against all
    # 22,594 profiles the same 24 subscribers read 0.11%; against the 1,995
    # who rendered they read 1.2%. Two orders of magnitude, one fact, and
    # only one of them is the rate anyone means by "~1%".
    cur = P.current_conversion()
    leg("L11 conversion_is_against_the_active_population",
        0.005 < cur < 0.03 and P.ACTIVE_POPULATION < P.PROFILES_TOTAL / 5,
        "%.2f%% on %d active (%.2f%% if measured on all %d profiles)"
        % (cur * 100, P.ACTIVE_POPULATION,
           P.SUBSCRIBER_BASE["rc_proxy_active"] / P.PROFILES_TOTAL * 100,
           P.PROFILES_TOTAL))

    # L12 THE BASE IS THE RC PROXY, NOT THE ONES WITH VIDEOS. Zac's ruling,
    # and the difference is 9 subscribers who rendered nothing and pay the
    # same. Asserted so a later edit cannot quietly swap in the smaller base
    # and make every margin look better.
    b = P.SUBSCRIBER_BASE
    leg("L12 subscriber_base_is_the_rc_proxy",
        b["rc_proxy_active"] == 24 and b["rendered_in_30d"] < b["rc_proxy_active"]
        <= b["mirror_active"],
        "rc_proxy %d, mirror %d, rendered %d, comped %d"
        % (b["rc_proxy_active"], b["mirror_active"], b["rendered_in_30d"], b["comped"]))

    # L13 A TIER THAT CANNOT COVER ITS OWN USAGE HAS NO BREAK-EVEN RATE, and
    # must say so rather than return a number. A root that does not exist
    # reported as a large percentage is the third state folded into the
    # second — UNDECIDABLE printed as merely difficult.
    huge = P.break_even_conversion("pro annual", 60.0, 0.25,
                                   P.CHANNEL_CUT["App Store, year 1 (30%)"])
    fine = P.break_even_conversion("pro annual", 1.0, 0.1225,
                                   P.CHANNEL_CUT["App Store, year 1 (30%)"])
    leg("L13 no_break_even_is_none_not_a_number",
        huge is None and fine is not None and 0 < fine < 1,
        "unaffordable -> %r, affordable -> %.1f%%" % (huge, fine * 100))

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
