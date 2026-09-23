#!/usr/bin/env python3
"""Every credit we charge covers ChatCut's real charge, at every row."""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import credit_prices as cp                                     # noqa: E402

FAILS, NLEGS = [], 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-46s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    # L1 NO ROW IS ROUNDED DOWN. A row priced below cost loses money every
    # time it is used and the edit SUCCEEDS, so nothing ever surfaces it.
    under = [(k, v[0], cp.our_price(*k)[0]) for k, v in cp.CHATCUT_RATES.items()
             if cp.our_price(*k)[0] < v[0] * cp.OUR_PER_THEIRS]
    leg("L1 no_row_is_priced_below_cost", not under,
        "%d of %d row(s) under cost: %s"
        % (len(under), len(cp.CHATCUT_RATES), under or "none"))

    # L2 EVERY ROW IS KEYED BY RESOLUTION WHERE THE PAGE GIVES ONE. The whole
    # reason for this file: /pricing quotes seconds per plan and hides the
    # resolution, and 1080p Seedance 2.5 is 5.5x the 480p rate. One number per
    # model would be a price for whichever resolution the quote assumed.
    vids = [k for k in cp.CHATCUT_RATES if k[0] == "video"]
    models = {}
    for _f, m, r in vids:
        models.setdefault(m, set()).add(r)
    collapsed = [m for m, rs in models.items() if not rs]
    leg("L2 video_rows_are_keyed_by_resolution",
        bool(vids) and not collapsed and all(k[2] for k in vids),
        "%d video row(s) across %d model(s): %s"
        % (len(vids), len(models), {m: sorted(rs) for m, rs in sorted(models.items())}))

    # L3 THE SPREAD IS REAL AND THE TABLE CARRIES IT. Seedance 2.5 480p ->
    # 1080p is the ratio that makes a model-keyed price wrong; assert it is
    # still there, so collapsing the rows fails here rather than silently.
    lo = cp.CHATCUT_RATES[("video", "Seedance 2.5", "480p")][0]
    hi = cp.CHATCUT_RATES[("video", "Seedance 2.5", "1080p")][0]
    leg("L3 resolution_spread_is_preserved", round(hi / lo, 1) >= 5.0,
        "Seedance 2.5 1080p / 480p = %.2fx (%s -> %s)" % (hi / lo, lo, hi))

    # L4 VOICEOVER TAKES THE TOP OF ITS RANGE. The page says 0.28-0.80; which
    # end a given call lands on is not something we control or can see, so
    # pricing the bottom sells every call above 0.28 below cost.
    vo = cp.CHATCUT_RATES[("voiceover", "AI Voiceover", "per 1,000 characters")]
    leg("L4 voiceover_priced_at_the_top_of_its_range", vo[0] == 0.80,
        "rate=%s from %r" % (vo[0], vo[2]))

    # L5 AN UNPRICED FEATURE IS OFF, AND OFF BY ABSENCE. A hand-kept list is a
    # list someone must remember to update; is_priceable answers from the
    # table, so publishing a rate turns the feature on and nothing else moves.
    wrongly_on = [f for f in cp.UNPRICED if cp.is_priceable(f)]
    leg("L5 unpriced_features_are_off", bool(cp.UNPRICED) and not wrongly_on,
        "%d unpriced: %s | wrongly priceable: %s"
        % (len(cp.UNPRICED), sorted(cp.UNPRICED), wrongly_on or "none"))

    # L6 AND ASKING FOR ONE RETURNS A STATE, NEVER A NUMBER. A guessed price
    # for a real charge is the error that costs money rather than credibility.
    px, why = cp.our_price("avatar", "any", "any")
    leg("L6 an_unpriced_feature_returns_no_number",
        px is None and "UNPRICED" in why, "avatar -> %r (%s)" % (px, why[:48]))

    # L7 THE SOURCE IS THE POLICY PAGE, NAMED IN THE FILE. /pricing is the
    # surface that hides the resolution; a table that cannot say where it came
    # from is a table nobody can re-derive when a rate moves.
    leg("L7 source_is_the_credits_policy_page",
        cp.SOURCE.endswith("/docs/credits-policy") and bool(cp.READ_ON)
        and all(len(v[2]) > 0 for v in cp.CHATCUT_RATES.values()),
        "%s read %s; %d row(s) carry the page's own words"
        % (cp.SOURCE, cp.READ_ON, len(cp.CHATCUT_RATES)))

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
