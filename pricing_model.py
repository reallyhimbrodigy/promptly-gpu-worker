#!/usr/bin/env python3
"""What a finished edit costs us, and what that does to every tier.

ONE NUMBER IS MISSING AND EVERYTHING ELSE IS HERE. The model takes
CHATCUT CREDITS PER FINISHED EDIT as its input; B1's funded run measures it as
the delta of two `GET /api/payment/credits` reads across one real edit. Until
that lands this file prints a SWEEP over candidate values and says so on every
line — it is not an answer, it is the answer's shape.

THE x10 RULE IS A PEG, AND THE PEG IS THE WHOLE ARGUMENT. credit_prices.py
charges ceil(their_rate x 10), so ONE OF OUR CREDITS IS ONE TENTH OF A CHATCUT
CREDIT, by construction, everywhere. That makes "1 video = 10 credits"
(COST_PER_RENDER) a claim that a finished edit costs exactly ONE ChatCut
credit. Nobody measured that. It was set when the only thing credits priced was
our own Modal render, and it has never been re-derived against the thing that
now does the work.

SO THE TEST IS ARITHMETIC, NOT OPINION: if a finished edit costs C ChatCut
credits, the x10 rule says a video should cost ceil(C x 10) of ours, and
COST_PER_RENDER is right only at C = 1.0.

NO CONSTANT MOVES HERE. This file imports none and writes none.
"""
import math
import sys

# ── what we charge ────────────────────────────────────────────────────────
# PROVENANCE, AND IT IS WEAKER THAN THE REST. These come from the WEB constant
# in content-studio's lib/__smoke_web_checkout_knob.js — a SMOKE FIXTURE
# describing the web-checkout knob, not a billing surface I read. They match
# the shape of the App Store ladder and the file's own note about Apple's
# advertised discount, but they are fixture values and must be confirmed
# against RevenueCat before any of the money below is quoted as fact.
TIERS = {
    # name:          (monthly-equivalent USD, videos/month allowed, our credits granted)
    "free":          (0.00,   1,   10),
    "pro weekly":    (47.62, 50,  200),   # $10.99/wk x 52 / 12
    "pro monthly":   (29.99, 50,  200),
    "pro annual":    (24.17, 50,  200),   # $289.99/yr / 12
    "max monthly":   (89.99, 200, 1000),
    "max yearly":    (66.67, 200, 1000),  # $799.99/yr / 12
}

# ── what ChatCut charges us per credit ────────────────────────────────────
# MEASURED from their published plans, 2026-09-23. The spread is real and it
# is not small: the middle tier buys credits at 71% more than the tiers either
# side of it, so "what a credit costs us" depends on which plan we are on.
USD_PER_CREDIT = {
    "Plus 400/800 annual": 0.1225,   # $49/400 and $98/800 — the cheapest
    "Plus 200 annual":     0.2100,   # $42/200
    "any plan, monthly":   0.2500,   # $50/200, $100/400, $200/800 — flat
}
OUR_PER_THEIRS = 10                  # the peg: 10 of ours = 1 of theirs
COST_PER_RENDER_TODAY = 10           # what "1 video = 10 credits" asserts



# ── APPLE'S CUT ───────────────────────────────────────────────────────────
# NOT ONE NUMBER. The cut depends on the programme and on how long the
# subscriber has been subscribed, and the difference between 30% and 15% is
# larger than most of the margins below.
#
#   30%  standard App Store commission, year 1
#   15%  Small Business Programme (under $1M/yr) AND year 2+ on any
#        auto-renewing subscription
#    3%  web checkout — no Apple at all, card processing only (~2.9% + 30c;
#        30c on a $29.99 charge is another 1.0%, so ~3.9% all-in)
#
# WHICH ONE APPLIES TO US IS NOT SOMETHING I CAN READ FROM HERE. It is an
# App Store Connect fact, and the model prints all three rather than picking.
CHANNEL_CUT = {
    "App Store, year 1 (30%)": 0.30,
    "App Store, SMB or year 2+ (15%)": 0.15,
    "web checkout (~3.9%)": 0.039,
}

# ── THE FREE TIER'S LOAD, MEASURED ────────────────────────────────────────
# From video_jobs joined to profiles, 30 days to 2026-09-23, status completed:
#
#   free   1,975 users   2,429 videos   1.23 each
#   paid      20 users     437 videos  21.85 each
#
# FREE IS 5.6x THE PAID TIER'S ENTIRE VOLUME. Every one of those 2,429 videos
# costs whatever a finished edit costs, and is paid for by twenty subscribers
# — 121 free videos carried per paying subscriber per month.
#
# TWO THINGS THIS WINDOW CANNOT TELL YOU, both stated rather than smoothed:
#   * It PREDATES today's free cap change. Free was 3 videos a month for most
#     of it and is 1 now. Every one of those 1,975 users rendered at least
#     once, so under a 1-cap the same population produces at most 1,975 — a
#     19% reduction, not the 67% the cap ratio suggests.
#   * Paid users average 21.85 of their 50, so break-even AT FULL USE is the
#     pessimistic bound and this is the realistic one. Both are reported,
#     because the heavy users are the ones a full-use number is about.
FREE_LOAD = {
    "free_users": 1975, "free_videos_30d": 2429,
    "paid_users": 20, "paid_videos_30d": 437, "paid_videos_per_user": 21.85,
    "window": "30 days to 2026-09-23, status=completed",
    "free_videos_per_paying_subscriber": 2429 / 20,
}


def net_of_cut(price, cut):
    """What reaches us after the store takes its share."""
    return price * (1.0 - cut)


def free_load_per_subscriber(c, usd_per_credit, free_videos=None, paid_users=None):
    """The free tier's monthly cost, divided across the people paying for it."""
    fv = FREE_LOAD["free_videos_30d"] if free_videos is None else free_videos
    pu = FREE_LOAD["paid_users"] if paid_users is None else paid_users
    if pu <= 0:
        return float("inf")
    return (fv * c * usd_per_credit) / pu


def true_margin(tier, c, usd_per_credit, cut, at_full_use=True):
    """-> dict. Net of the store's cut, of own usage, and of the free tier.

    THE THREE SUBTRACTIONS ARE THE WHOLE POINT. A tier that looks profitable
    on list price can be underwater once the store takes 30%, and one that
    survives that can still be underwater once it carries its share of 2,429
    free videos a month. Reporting any of the three alone is a number that
    answers a question nobody asked.
    """
    price, videos, _granted = TIERS[tier]
    used = videos if at_full_use else FREE_LOAD["paid_videos_per_user"]
    net = net_of_cut(price, cut)
    own = used * c * usd_per_credit
    free = free_load_per_subscriber(c, usd_per_credit)
    return {"tier": tier, "list": price, "net_of_cut": net, "videos_used": used,
            "own_usage_cost": own, "free_load_share": free,
            "margin": net - own - free}


def our_credits_per_video(chatcut_credits_per_edit):
    """The x10 rule applied to the real number."""
    return math.ceil(chatcut_credits_per_edit * OUR_PER_THEIRS)


def rows(c, usd_per_credit):
    """-> one row per tier at this cost-per-edit and this credit price."""
    out = []
    for name, (price, videos, granted) in TIERS.items():
        cost_per_video = c * usd_per_credit
        full_cost = videos * cost_per_video
        # BREAK-EVEN IS IN VIDEOS, because that is the unit the user was sold
        # and the unit they choose. A tier is underwater from the video at
        # which cost passes price.
        be = (price / cost_per_video) if cost_per_video > 0 else float("inf")
        # What the allowance BUYS under the peg, versus what we advertise.
        buys = granted / our_credits_per_video(c) if c > 0 else float("inf")
        out.append({
            "tier": name, "price": price, "videos": videos, "granted": granted,
            "cost_per_video": cost_per_video, "full_allowance_cost": full_cost,
            "margin": price - full_cost, "break_even_videos": be,
            "allowance_buys_videos": buys,
        })
    return out


def render(c, label, usd_per_credit, note=""):
    ourc = our_credits_per_video(c)
    print("\n%s  —  %.3f ChatCut credits per finished edit  @ $%.4f/credit  %s"
          % (label, c, usd_per_credit, note))
    print("  the x10 rule says a video costs %d of our credits "
          "(COST_PER_RENDER is %d today%s)"
          % (ourc, COST_PER_RENDER_TODAY,
             "" if ourc == COST_PER_RENDER_TODAY else " — WRONG by %.1fx" % (ourc / COST_PER_RENDER_TODAY)))
    print("  %-13s %8s %7s %11s %11s %9s %11s %s"
          % ("tier", "price", "videos", "$/video", "allowance", "margin",
             "break-even", "allowance buys"))
    for r in rows(c, usd_per_credit):
        print("  %-13s %8.2f %7d %11.4f %11.2f %9.2f %11.1f %14.1f"
              % (r["tier"], r["price"], r["videos"], r["cost_per_video"],
                 r["full_allowance_cost"], r["margin"], r["break_even_videos"],
                 r["allowance_buys_videos"]))


def max_sustainable_cost(usd_per_credit):
    """-> per tier, the highest cost-per-edit that still breaks even AT FULL USE.

    THE MOST DECISION-USEFUL NUMBER IN THE FILE, and it needs no measurement:
    it is price / (videos x $per-credit), so it can be computed today and the
    measured cost is then just a point on the line. When the run lands, the
    only question is which side of these numbers it falls on.

    AT FULL USE is the load-bearing qualifier. Almost nobody renders their
    whole allowance, so a tier underwater here is not a tier losing money on
    average — it is a tier that loses money on its HEAVIEST users, which is
    the population that grows if the product is good.
    """
    out = []
    for name, (price, videos, granted) in TIERS.items():
        if price <= 0 or videos <= 0:
            out.append((name, price, videos, None))
            continue
        out.append((name, price, videos, price / (videos * usd_per_credit)))
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1:
        c = float(sys.argv[1])
        for lbl, upc in USD_PER_CREDIT.items():
            render(c, "MEASURED", upc, "(%s)" % lbl)
    else:
        print("NO MEASURED COST YET — this is a SWEEP, not an answer.")
        print("B1's funded run supplies it as the delta of two "
              "GET /api/payment/credits reads across one real edit.")
        upc = USD_PER_CREDIT["Plus 400/800 annual"]
        for c in (1.0, 2.0, 4.0):
            render(c, "PROVISIONAL", upc, "(Plus 400/800 annual)")
        print("\n" + "=" * 78)
        print("WHERE EACH TIER GOES UNDERWATER — needs no measurement at all.")
        print("The highest ChatCut-credits-per-edit that still breaks even AT FULL USE.\n")
        print("\n" + "=" * 78)
        print("THE SAME QUESTION WITH THE STORE'S CUT AND THE FREE TIER SUBTRACTED.")
        print("Free carries %.0f videos per paying subscriber per month (%d free videos,"
              % (FREE_LOAD["free_videos_per_paying_subscriber"], FREE_LOAD["free_videos_30d"]))
        print("%d paying subscribers, %s).\n" % (FREE_LOAD["paid_users"], FREE_LOAD["window"]))
        upc2 = USD_PER_CREDIT["Plus 400/800 annual"]
        for c2 in (0.5, 1.0, 2.0):
            print("  at %.1f credits/edit, $%.4f/credit — margin per subscriber per month"
                  % (c2, upc2))
            print("    %-14s %9s %10s %10s %10s %9s"
                  % ("tier", "list", "net", "own use", "free share", "margin"))
            for t in ("pro monthly", "pro annual", "max monthly", "max yearly"):
                r = true_margin(t, c2, upc2, CHANNEL_CUT["App Store, year 1 (30%)"],
                                at_full_use=False)
                print("    %-14s %9.2f %10.2f %10.2f %10.2f %9.2f%s"
                      % (t, r["list"], r["net_of_cut"], r["own_usage_cost"],
                         r["free_load_share"], r["margin"],
                         "  UNDERWATER" if r["margin"] < 0 else ""))
            print()
        print("  own use is at the MEASURED 21.85 videos/subscriber, not the 50 allowance.")
        print("  cut is the 30% year-1 App Store rate — the worst of the three channels.")
        print("\n" + "=" * 78)
        print("  %-14s %9s %8s %s" % ("tier", "price", "videos", "max credits/edit at each credit price"))
        print("  %-14s %9s %8s %12s %12s %12s"
              % ("", "", "", "@0.1225", "@0.2100", "@0.2500"))
        for name, price, videos, _ in max_sustainable_cost(0.1225):
            if price <= 0:
                print("  %-14s %9.2f %8d   free tier — every video is a cost, no break-even" % (name, price, videos))
                continue
            vals = [price / (videos * u) for u in (0.1225, 0.21, 0.25)]
            print("  %-14s %9.2f %8d %12.2f %12.2f %12.2f" % (name, price, videos, *vals))
