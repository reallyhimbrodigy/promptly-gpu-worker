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
