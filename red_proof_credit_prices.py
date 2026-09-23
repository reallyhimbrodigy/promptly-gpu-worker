#!/usr/bin/env python3
"""RED proof for smoke_credit_prices.py.

MUTATIONS AIMED AT THE MONEY. Each one is a way the table stops covering
ChatCut's real charge, and every one of them leaves a table that still looks
like a price list — which is the whole problem: an underpriced row succeeds.
"""
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_credit_prices.py")
WATCHED = ["credit_prices.py", "smoke_credit_prices.py"]


def _child_env():
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


MUTATIONS = [
    # ROUNDING DOWN. The single most plausible "tidy-up" anyone would make,
    # and every row it touches sells below cost while the edit succeeds.
    ("ceil_becomes_round", "credit_prices.py",
     "    return math.ceil(rate * OUR_PER_THEIRS), '%s %s (\"%s\")' % (rate, unit, words)",
     "    return int(rate * OUR_PER_THEIRS), '%s %s (\"%s\")' % (rate, unit, words)",
     "L1 no_row_is_priced_below_cost",
     lambda s: "math.ceil(rate * OUR_PER_THEIRS)" in s),
    # THE RESOLUTION COLLAPSES. One row per model, priced at the cheapest
    # resolution — the /pricing defect, imported.
    ("resolution_collapses_to_the_cheapest", "credit_prices.py",
     '    ("video", "Seedance 2.5", "1080p"):\n        (2.2175, "per second", "about 2.2175/sec"),',
     '    ("video", "Seedance 2.5", "1080p"):\n        (0.3982, "per second", "about 0.3982/sec"),',
     "L3 resolution_spread_is_preserved",
     lambda s: '(2.2175, "per second"' in s),
    # VOICEOVER PRICED AT THE BOTTOM OF ITS RANGE: every call above 0.28 is
    # sold below cost, and which end a call lands on is invisible to us.
    ("voiceover_priced_at_the_floor", "credit_prices.py",
     '        (0.80, "per 1,000 characters",',
     '        (0.28, "per 1,000 characters",',
     "L4 voiceover_priced_at_the_top_of_its_range",
     lambda s: '(0.80, "per 1,000 characters"' in s),
    # AN UNPRICED FEATURE GETS A GUESS. This is the error that costs money
    # rather than credibility: a real charge priced from an invented number.
    ("avatar_gets_an_invented_rate", "credit_prices.py",
     '    ("music", "AI Music", "per song"):',
     '    ("avatar", "AI Avatar", "per second"):\n        (0.5, "per second", "INVENTED"),\n'
     '    ("music", "AI Music", "per song"):',
     "L5 unpriced_features_are_off",
     lambda s: '"avatar"' not in s.split("CHATCUT_RATES = {")[1].split("}")[0]),
    # THE SOURCE BECOMES /pricing — the page that hides the resolution.
    ("source_becomes_the_pricing_page", "credit_prices.py",
     'SOURCE = "https://chatcut.io/docs/credits-policy"',
     'SOURCE = "https://chatcut.io/pricing"',
     "L7 source_is_the_credits_policy_page",
     lambda s: '/docs/credits-policy"' in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True,
                       env=_child_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def snapshot():
    return {q: open(os.path.join(HERE, q), "rb").read() for q in WATCHED}


def residue(base):
    return sorted(q for q, b in base.items()
                  if open(os.path.join(HERE, q), "rb").read() != b)


def leg_failed(out, phrase):
    for ln in out.splitlines():
        if phrase in ln and "FAIL" in ln:
            return True
    return False


def main():
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-900:])
        return 2
    print("baseline green.\n")
    base = snapshot()
    red, vacuous = 0, []
    for name, path, old, new, phrase, pre in MUTATIONS:
        src = io.open(os.path.join(HERE, path), encoding="utf-8").read()
        if src.count(old) != 1:
            print("  %-40s HARNESS FAILURE: anchor %dx" % (name, src.count(old)))
            continue
        if not pre(src):
            vacuous.append(name)
            print("  %-40s VACUOUS   precondition false" % name)
            continue
        io.open(os.path.join(HERE, path), "w", encoding="utf-8").write(
            src.replace(old, new, 1))
        rc2, out2 = run_smoke()
        io.open(os.path.join(HERE, path), "w", encoding="utf-8").write(src)
        ok = rc2 != 0 and leg_failed(out2, phrase)
        red += 1 if ok else 0
        print("  %-40s %s   rc=%d leg_failed=%s"
              % (name, "RED " if ok else "NOT RED", rc2, leg_failed(out2, phrase)))
    left = residue(base)
    if left:
        print("\nHARNESS FAILURE: residue on disk: %s" % ", ".join(left))
        return 2
    print("\n%d/%d RED-proven%s" % (red, len(MUTATIONS),
          ("; VACUOUS: " + ", ".join(vacuous)) if vacuous else ""))
    if vacuous or not (MUTATIONS and red == len(MUTATIONS)):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
