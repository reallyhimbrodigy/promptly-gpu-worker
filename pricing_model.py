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
        print("  %-14s %9s %8s %s" % ("tier", "price", "videos", "max credits/edit at each credit price"))
        print("  %-14s %9s %8s %12s %12s %12s"
              % ("", "", "", "@0.1225", "@0.2100", "@0.2500"))
        for name, price, videos, _ in max_sustainable_cost(0.1225):
            if price <= 0:
                print("  %-14s %9.2f %8d   free tier — every video is a cost, no break-even" % (name, price, videos))
                continue
            vals = [price / (videos * u) for u in (0.1225, 0.21, 0.25)]
            print("  %-14s %9.2f %8d %12.2f %12.2f %12.2f" % (name, price, videos, *vals))
