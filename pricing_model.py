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



# ── THE SUBSCRIBER BASE: THREE NUMBERS, AND THEY ARE NOT THE SAME ─────────
# Measured from profiles, 2026-09-23. Reported together because picking one
# silently is how a rate gets quoted against a denominator nobody agreed to.
#
#   29  active by OUR MIRROR       pro_until > now()
#   24  carrying an rc_product_id  the closest proxy we have to RevenueCat's
#                                  own active count, and it matches the ~25
#                                  rows on the backfill list
#   20  rendered a video in 30d    the only ones who cost us anything
#    7  comped                     active, paying nothing, still a cost
#
# THE BASE IS 24, per Zac: RevenueCat's count, not the 20 with videos. It is
# STILL OUR MIRROR OF RC AND NOT RC — reading RC needs the secret and the
# Render shell — so it is labelled a proxy and wants confirming by the
# readback. The 9 subscribers who rendered nothing are why the two differ,
# and they pay the same.
SUBSCRIBER_BASE = {
    "rc_proxy_active": 24, "mirror_active": 29, "rendered_in_30d": 20, "comped": 7,
    "source": "profiles, 2026-09-23; rc_proxy = pro_until > now() AND rc_product_id "
              "is not null. NOT read from RevenueCat.",
}

# THE DENOMINATOR FOR A CONVERSION RATE IS THE ACTIVE POPULATION, NOT EVERY
# PROFILE EVER CREATED. 22,594 profiles exist; 1,995 of them rendered in the
# window (1,975 free + 20 paid). 24/22,594 is 0.11% and 24/1,995 is 1.2% —
# the same fact, two orders of magnitude apart, and only the second is the
# ~1% anyone means. Stated so the rate below cannot be read against the wrong
# denominator.
ACTIVE_POPULATION = 1995
PROFILES_TOTAL = 22594
CONVERSION_SWEEP = (0.01, 0.02, 0.03, 0.05)


def current_conversion():
    return SUBSCRIBER_BASE["rc_proxy_active"] / ACTIVE_POPULATION


def subscribers_at(rate):
    """How many subscribers a conversion rate implies over the active base."""
    return rate * ACTIVE_POPULATION


def free_videos_each(rate, free_videos=None):
    """Free videos carried per subscriber, with FREE VOLUME HELD CONSTANT.

    Holding it constant is the ruling and it is the conservative half: in
    reality a converting user stops being free volume, so this OVERSTATES the
    load at higher rates rather than flattering it.
    """
    fv = FREE_LOAD["free_videos_30d"] if free_videos is None else free_videos
    n = subscribers_at(rate)
    return float("inf") if n <= 0 else fv / n


def margin_at_conversion(tier, rate, c, usd_per_credit, cut):
    """Margin per subscriber per month at a given conversion rate."""
    price, videos, _g = TIERS[tier]
    net = net_of_cut(price, cut)
    own = FREE_LOAD["paid_videos_per_user"] * c * usd_per_credit
    free = free_videos_each(rate) * c * usd_per_credit
    return {"tier": tier, "rate": rate, "net": net, "own": own, "free_share": free,
            "margin": net - own - free}


def break_even_conversion(tier, c, usd_per_credit, cut):
    """-> the conversion rate at which this tier exactly carries the free tier.

    THE QUESTION IN ITS OWN UNITS. Margin is zero when the free share equals
    what is left after the store's cut and the subscriber's own usage:

        net - own - (FREE_VIDEOS * c * $) / subscribers = 0
        subscribers = FREE_VIDEOS * c * $ / (net - own)
        rate        = subscribers / ACTIVE_POPULATION

    Returns None when (net - own) <= 0 — a tier that cannot cover even its
    OWN usage never breaks even at any conversion rate, and reporting a rate
    there would be reporting a root that does not exist. That is the
    UNDECIDABLE case, not a large number.
    """
    price, _v, _g = TIERS[tier]
    net = net_of_cut(price, cut)
    own = FREE_LOAD["paid_videos_per_user"] * c * usd_per_credit
    headroom = net - own
    if headroom <= 0:
        return None
    subs = (FREE_LOAD["free_videos_30d"] * c * usd_per_credit) / headroom
    return subs / ACTIVE_POPULATION


# ── THE FIRST MEASURED POINTS, FUNDED RUN 1 (2026-09-24) ──────────────────
#
# Real ChatCut credits consumed by one finished edit, read as the delta of two
# credit reads across the run. These are the first non-hypothetical numbers in
# this file.
#
#     credits   source      orientation
#       1.66     20.4 s     vertical
#       2.64     55.9 s     landscape
#
# TWO POINTS, AND THEY DIFFER IN TWO VARIABLES. The longer edit is also the
# landscape one, so the 0.98-credit gap cannot be attributed to duration: an
# orientation difference would produce the same table. Fitting a line through
# them gives 1.10 + 0.0276/s with ZERO residual — because two points always
# do — and a zero residual here is arithmetic, not agreement.
#
# This repo has the rule already: never infer a universal shape from one
# sampled instance. Two instances that vary together are the same trap wearing
# a second data point, and it is worse than one because it looks like a trend.
#
# SO THE FIT IS REPORTED AND NOT USED. What the two points DO establish, with
# no model at all, is a floor and a ceiling for a typical edit — roughly 1.7 to
# 2.6 credits — and that is enough to price against until a third point that
# varies ONE variable arrives. The separating run is a landscape source at ~20s
# or a vertical one at ~56s; either one turns two confounded points into an
# answer.
MEASURED_EDITS = (
    # (chatcut_credits, source_seconds, orientation, run, request)
    (1.66, 20.4, "vertical", "funded run 1",
     "cut the dead air and make it punchy, and put captions on it"),
    (2.64, 55.9, "landscape", "funded run 1",
     "cut the dead air and make it punchy, and put captions on it"),
    (1.04, 20.4, "vertical", "run 3b",
     "make it hype with pop-up graphics and sound effects"),
)

# ── 3b IS THE THIRD POINT AND IT ISOLATES ONE VARIABLE ────────────────────
#
# Rows 1 and 3 share DURATION (20.4s) and ORIENTATION (vertical) and differ
# only in the REQUEST. That is the separating run the two-point note asked
# for, arriving from a direction nobody planned:
#
#     1.66 credits   "cut the dead air and make it punchy, and put captions on it"
#     1.04 credits   "make it hype with pop-up graphics and sound effects"
#
# -0.62 credits, -37%, attributable to REQUEST SHAPE alone. And the sign is
# the surprise: the graphics-heavy request that placed 6 graphics, 6 sounds
# and 24 caption cards cost LESS than the one that placed none of them. Cost
# is not tracking what was produced.
#
# WHAT IT DOES NOT SETTLE. Rows 1 and 2 still vary duration AND orientation
# together, so the per-second slope remains confounded — one isolated pair
# does not un-confound a different pair. CONFOUNDED stays True, and it is
# computed from the two rows implied_per_second() actually reads rather than
# from a feeling that we now know more.


# ── RE-EDITS COST CHATCUT CREDITS AND THE USER PAYS ZERO ──────────────────
#
# Measured by B1, 2026-09-24, on the ChatCut re-edit path:
#
#     0.76 credits   "make the captions bigger"          39.6s
#     0.28 credits   "remove the second graphic"         38.4s
#
# Both preserved the edit. The second removed the graphic AND its paired
# sound — 6/6 down to 5/5 — and kept all 24 caption cards.
#
# THIS IS THE NUMBER THE CAP DECISION TURNS ON, and it is not the one the
# policy is written in. `reedit_free_cap` charges the USER 0 credits up to ten
# per video. It does not make the re-edit free: WE pay ChatCut 0.28-0.76 every
# time, and a cap of ten authorises up to ten of them.
#
#     first edit          1.04 - 1.66
#     10 re-edits         2.80 - 7.60
#     ---------------------------------
#     per video           3.84 - 9.26     against 1.04 - 1.66 for the edit alone
#
# So the CAP, not the edit, dominates cost per video at the top of its range —
# a video with ten re-edits costs between 2.3x and 5.6x one without. That is
# the arithmetic to set the number against, and it is why the cap is config
# rather than a constant.
#
# AND THE CHEAPER RE-EDIT IS THE ONE THAT DID MORE. "Remove the second
# graphic" restructured the timeline for 0.28; "make the captions bigger"
# changed one property for 0.76. Same direction as the 3b finding: cost tracks
# REQUEST SHAPE, not what was produced.
MEASURED_REEDITS = (
    # (chatcut_credits, wall_seconds, request)
    (0.76, 39.6, "make the captions bigger"),
    (0.28, 38.4, "remove the second graphic"),
)


def reedit_range():
    """-> (low, high) ChatCut credits per re-edit, measured only."""
    cs = [c for c, _w, _r in MEASURED_REEDITS]
    return (min(cs), max(cs))


def cost_per_video(cap, first_edit=None):
    """-> (low, high) ChatCut credits for one video at a given free-re-edit cap.

    THE CAP IS AN AUTHORISATION, NOT A FORECAST. This is what the cap PERMITS,
    not what an average user spends — nobody has measured how many re-edits a
    real user takes. Reporting it as an expectation would be a judgement
    wearing a measurement's clothes; it is a CEILING and it is labelled one.
    """
    lo_e, hi_e = measured_credit_range() if first_edit is None else first_edit
    lo_r, hi_r = reedit_range()
    n = max(0, int(cap or 0))
    return (lo_e + n * lo_r, hi_e + n * hi_r)


def request_shape_delta():
    """-> (low, high, delta) over rows sharing duration AND orientation.

    The one comparison in this table where a single variable moves. Returns
    None when no such pair exists, rather than reaching for the nearest two
    rows — a pair assembled by relaxing the criterion is the confound again.
    """
    by_source = {}
    for c, s_, o, _run, req in MEASURED_EDITS:
        by_source.setdefault((s_, o), []).append((c, req))
    for _k, rows in sorted(by_source.items()):
        if len(rows) >= 2:
            lo = min(rows)[0]
            hi = max(rows)[0]
            return (lo, hi, hi - lo)
    return None


def measured_credit_range():
    """-> (low, high) ChatCut credits per finished edit, from measurement only.

    NOT a model and deliberately not one. The range is what two points support;
    a slope is what they only appear to support.
    """
    cs = [row[0] for row in MEASURED_EDITS]
    return (min(cs), max(cs))


def implied_per_second():
    """-> (slope, intercept, CONFOUNDED) from the two points, for reporting.

    The third element is the point of the function: it is True whenever the
    points do not isolate duration, and a caller that ignores it is quoting a
    duration rate that may be an orientation rate.
    """
    if len(MEASURED_EDITS) < 2:
        return (None, None, True)
    (c1, s1, o1, _r1, _q1), (c2, s2, o2, _r2, _q2) = (MEASURED_EDITS[0],
                                                     MEASURED_EDITS[1])
    if s2 == s1:
        return (None, None, True)
    slope = (c2 - c1) / (s2 - s1)
    return (slope, c1 - slope * s1, o1 != o2)


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
        print("CONVERSION SWEEP — free volume held constant at %d videos/month."
              % FREE_LOAD["free_videos_30d"])
        print("Base: %d subscribers (RC proxy) over %d active users = %.2f%% today."
              % (SUBSCRIBER_BASE["rc_proxy_active"], ACTIVE_POPULATION,
                 current_conversion() * 100))
        print("Also on record: %d active by our mirror, %d rendered in 30d, %d comped.\n"
              % (SUBSCRIBER_BASE["mirror_active"], SUBSCRIBER_BASE["rendered_in_30d"],
                 SUBSCRIBER_BASE["comped"]))
        upc3 = USD_PER_CREDIT["Plus 400/800 annual"]
        cut3 = CHANNEL_CUT["App Store, year 1 (30%)"]
        print("  %-7s %6s %11s   %s" % ("rate", "subs", "free each", "margin per subscriber per month"))
        print("  %-7s %6s %11s   %10s %10s %10s %10s"
              % ("", "", "", "pro mo", "pro yr", "max mo", "max yr"))
        for c3 in (0.5, 1.0, 2.0):
            print("  --- at %.1f credits/edit" % c3)
            for r in (current_conversion(),) + CONVERSION_SWEEP:
                ms = [margin_at_conversion(t, r, c3, upc3, cut3)["margin"]
                      for t in ("pro monthly", "pro annual", "max monthly", "max yearly")]
                print("  %6.2f%% %6.0f %11.1f   %10.2f %10.2f %10.2f %10.2f"
                      % (r * 100, subscribers_at(r), free_videos_each(r), *ms))
            print()
        print("=" * 78)
        print("BREAK-EVEN CONVERSION — the rate at which the free tier pays for itself.\n")
        print("  %-14s %s" % ("tier", "credits per edit"))
        print("  %-14s %10s %10s %10s %10s" % ("", "0.5", "1.0", "2.0", "4.0"))
        for t in ("pro monthly", "pro annual", "max monthly", "max yearly"):
            cells = []
            for c3 in (0.5, 1.0, 2.0, 4.0):
                r = break_even_conversion(t, c3, upc3, cut3)
                cells.append("never" if r is None else "%.1f%%" % (r * 100))
            print("  %-14s %10s %10s %10s %10s" % (t, *cells))
        print("\n  'never' = the tier cannot cover even its own usage at that cost,")
        print("  so no conversion rate rescues it. Today's rate is %.2f%%." % (current_conversion() * 100))
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
