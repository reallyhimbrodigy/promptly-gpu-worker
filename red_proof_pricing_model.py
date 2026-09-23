#!/usr/bin/env python3
"""RED proof for smoke_pricing_model.py — mutations aimed at the arithmetic."""
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_pricing_model.py")
MODEL = os.path.join(HERE, "pricing_model.py")


def _env():
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


MUTATIONS = [
    # CONVERTING MAKES IT WORSE. free_videos_each multiplies instead of
    # divides, so a higher rate raises the load — inverted, and invisible in
    # a table of plausible numbers.
    ("converting_raises_the_load",
     "    return float(\"inf\") if n <= 0 else fv / n",
     "    return float(\"inf\") if n <= 0 else fv * n",
     "L10 more_subscribers_means_less_load_each",
     lambda s: "else fv / n" in s),
    # THE RATE IS MEASURED AGAINST EVERY PROFILE EVER CREATED. 24/22,594 is
    # 0.11%, the same fact two orders of magnitude from the one anyone means.
    ("conversion_measured_against_all_profiles",
     "ACTIVE_POPULATION = 1995",
     "ACTIVE_POPULATION = 22594",
     "L11 conversion_is_against_the_active_population",
     lambda s: "ACTIVE_POPULATION = 1995" in s),
    # THE BASE SWAPS TO THE 20 WITH VIDEOS. Every margin improves, and the 9
    # subscribers who rendered nothing — and pay the same — vanish.
    ("base_swaps_to_the_ones_with_videos",
     '    "rc_proxy_active": 24, "mirror_active": 29,',
     '    "rc_proxy_active": 20, "mirror_active": 29,',
     "L12 subscriber_base_is_the_rc_proxy",
     lambda s: '"rc_proxy_active": 24,' in s),
    # A ROOT THAT DOES NOT EXIST IS REPORTED AS A BIG NUMBER. UNDECIDABLE
    # folded into "merely difficult", in the column Zac will read first.
    ("no_break_even_reported_as_a_rate",
     "    if headroom <= 0:\n        return None",
     "    if headroom <= 0:\n        return 9.99",
     "L13 no_break_even_is_none_not_a_number",
     lambda s: "if headroom <= 0:" in s),
    # THE CUT APPLIED THE WRONG WAY ROUND. Inflates every margin in the
    # table and reads entirely plausibly — a 30% cut becoming a 30% bonus.
    ("cut_becomes_a_bonus",
     "    return price * (1.0 - cut)",
     "    return price * (1.0 + cut)",
     "L6 every_channel_cut_reduces_revenue",
     lambda s: "price * (1.0 - cut)" in s),
    # THE FREE LOAD IS DIVIDED BY THE FREE USERS INSTEAD OF THE PAYERS.
    # Understates it by ~99x and still looks like a per-user number.
    ("free_load_divided_by_the_wrong_population",
     '    return (fv * c * usd_per_credit) / pu',
     '    return (fv * c * usd_per_credit) / FREE_LOAD["free_users"]',
     "L7 free_load_is_per_paying_subscriber",
     lambda s: "(fv * c * usd_per_credit) / pu" in s),
    # ZERO PAYERS READS AS ZERO LOAD — the free tier costing nothing at the
    # exact moment it costs everything.
    ("no_payers_reads_as_no_cost",
     "    if pu <= 0:\n        return float(\"inf\")",
     "    if pu <= 0:\n        return 0.0",
     "L8 no_payers_is_not_free",
     lambda s: 'if pu <= 0:' in s),
    # THE FREE SHARE IS DROPPED FROM THE MARGIN. Every tier turns profitable
    # and nothing in the row says a subtraction went missing.
    ("margin_forgets_the_free_tier",
     '    return {"tier": tier, "list": price, "net_of_cut": net, "videos_used": used,\n'
     '            "own_usage_cost": own, "free_load_share": free,\n'
     '            "margin": net - own - free}',
     '    return {"tier": tier, "list": price, "net_of_cut": net, "videos_used": used,\n'
     '            "own_usage_cost": own, "free_load_share": free,\n'
     '            "margin": net - own}',
     "L9 true_margin_subtracts_cut_usage_and_free",
     lambda s: '"margin": net - own - free}' in s),
    # THE PEG DRIFTS FROM WHAT WE CHARGE. Every number in the model would then
    # be quoted against a currency we do not use, and each one looks fine.
    ("peg_drifts_from_credit_prices",
     "OUR_PER_THEIRS = 10                  # the peg: 10 of ours = 1 of theirs",
     "OUR_PER_THEIRS = 12                  # the peg: 10 of ours = 1 of theirs",
     "L0 the_peg_matches_what_we_charge",
     lambda s: "OUR_PER_THEIRS = 10" in s),
    # ceil BECOMES round. Under-prices a video every time, and the edit still
    # succeeds, so nothing surfaces it — the same defect as a rounded-down row
    # in credit_prices.py, one layer up.
    ("x10_rounds_instead_of_ceils",
     "    return math.ceil(chatcut_credits_per_edit * OUR_PER_THEIRS)",
     "    return round(chatcut_credits_per_edit * OUR_PER_THEIRS)",
     "L1 never_rounds_a_video_down",
     lambda s: "math.ceil(chatcut_credits_per_edit" in s),
    # BREAK-EVEN INVERTS. price * videos * rate instead of price / (...) —
    # a dearer credit then makes a tier look SAFER, and the sign of that error
    # is invisible in a table of plausible numbers.
    ("break_even_inverts",
     "        out.append((name, price, videos, price / (videos * usd_per_credit)))",
     "        out.append((name, price, videos, price * videos * usd_per_credit))",
     "L3 break_even_falls_as_credits_cost_more",
     lambda s: "price / (videos * usd_per_credit)" in s),
    # THE FREE TIER REPORTS 0 INSTEAD OF None. A 0 in a break-even column
    # reads as "breaks even immediately" rather than "never" — absence
    # rendered as a value, in a table about money.
    ("free_tier_break_even_becomes_zero",
     "            out.append((name, price, videos, None))",
     "            out.append((name, price, videos, 0.0))",
     "L4 free_tier_reports_no_break_even",
     lambda s: "videos, None))" in s),
    # THE MODEL STARTS WRITING. Zac ruled no constant moves until he has seen
    # this; a model that can write is one commit from moving one.
    ("the_model_gains_a_writer",
     "import math\nimport sys",
     "import math\nimport sys\nCOST_PER_RENDER = 10",
     "L5 the_model_writes_nothing",
     lambda s: "COST_PER_RENDER =" not in s),
]


def run():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True,
                       env=_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def failed(out, phrase):
    return any(phrase in ln and "FAIL" in ln for ln in out.splitlines())


def main():
    rc, out = run()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-700:])
        return 2
    print("baseline green.\n")
    raw = io.open(MODEL, encoding="utf-8").read()
    red, vacuous = 0, []
    for name, old, new, phrase, pre in MUTATIONS:
        if raw.count(old) != 1:
            print("  %-38s HARNESS FAILURE: anchor %dx" % (name, raw.count(old)))
            continue
        if not pre(raw):
            vacuous.append(name)
            print("  %-38s VACUOUS   precondition false" % name)
            continue
        io.open(MODEL, "w", encoding="utf-8").write(raw.replace(old, new, 1))
        rc2, out2 = run()
        io.open(MODEL, "w", encoding="utf-8").write(raw)
        ok = rc2 != 0 and failed(out2, phrase)
        red += 1 if ok else 0
        print("  %-38s %s   rc=%d leg_failed=%s"
              % (name, "RED " if ok else "NOT RED", rc2, failed(out2, phrase)))
    if io.open(MODEL, encoding="utf-8").read() != raw:
        print("\nHARNESS FAILURE: residue left in the model")
        return 2
    print("\n%d/%d RED-proven%s" % (red, len(MUTATIONS),
          ("; VACUOUS: " + ", ".join(vacuous)) if vacuous else ""))
    return 0 if (MUTATIONS and red == len(MUTATIONS) and not vacuous) else 1


if __name__ == "__main__":
    sys.exit(main())
