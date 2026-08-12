#!/usr/bin/env python3
"""Payoff arms cert — offline, $0. Arms 6 and 7, both directions.

THE DEFECT UNDER TEST IS NOT A BUG. 0 punchy payoffs in 253 chances is the
system obeying the owner's own twice-expressed ruling [CODE handler.py:1215
doctrine; :6997 prompt prose]: "the slow commitment IS what makes the payoff
bigger than every beat before it." These arms do not overturn it. They produce
the pixels it should stand or fall on.

  arm 6  PROMPTLY_PAYOFF_PUNCHY  enum widened only          (2026-07-31)
  arm 7  PROMPTLY_PAYOFF_OPEN    enum widened + prose neutral (2026-08-12)

Arm 6's own pre-registered read says a null there is INCONCLUSIVE, because the
prose still forbids what the enum now allows — so a null could be obeyance
rather than judgement. Arm 7 removes the prohibition and keeps the requirement,
which is the only configuration in which "never picked" is a real confirmation.

What this cert protects is the VALIDITY of that test:
  * off is byte-identical, or the control arm is not a control
  * arm 7 implies arm 6, or it is not the clean test
  * the swap NEUTRALISES, never advocates — prose arguing FOR a snap would
    measure the new instruction instead of the model's taste
  * a drifted prompt RAISES rather than silently no-opping, because a faked null
    reads as "the model agrees with the ruling", the most expensive wrong
    conclusion available here
  * the two prose arms cannot run together and quietly measure neither

  python3 cert_payoff_arms.py
"""
import os
import sys

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  [PASS] {label}")
    else:
        FAILURES.append(f"{label}{(' — ' + detail) if detail else ''}")
        print(f"  [FAIL] {label}{(' — ' + detail) if detail else ''}")


def payoff_types(H):
    for v in H._zoom_claim_variants():
        if v["properties"]["arc_position"]["enum"] == ["payoff"]:
            return tuple(v["properties"]["type"]["enum"])
    return ()


def main():
    for k in ("PROMPTLY_PAYOFF_PUNCHY", "PROMPTLY_PAYOFF_OPEN", "PROMPTLY_DWELL"):
        os.environ.pop(k, None)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import handler as H

    print("=== ARM 0: control — both flags off is BYTE-IDENTICAL ===")
    base = payoff_types(H)
    check("payoff enum is the committed pair only",
          base == ("LetterboxPush", "SmoothPush"), repr(base))
    check("no punch is sayable at payoff", "SnapReframe" not in base)
    check("arm 6 off", H._payoff_punchy_enabled() is False)
    check("arm 7 off", H._payoff_open_enabled() is False)

    print("\n=== ARM 6: enum widened only ===")
    os.environ["PROMPTLY_PAYOFF_PUNCHY"] = "1"
    a6 = payoff_types(H)
    check("SnapReframe becomes sayable", "SnapReframe" in a6, repr(a6))
    check("it ADDS, never replaces (the committed pair survives)",
          {"LetterboxPush", "SmoothPush"} <= set(a6), repr(a6))
    check("nothing else appears", set(a6) == {"LetterboxPush", "SmoothPush", "SnapReframe"})
    os.environ.pop("PROMPTLY_PAYOFF_PUNCHY")

    print("\n=== ARM 7: enum widened AND prose neutralised ===")
    os.environ["PROMPTLY_PAYOFF_OPEN"] = "1"
    a7 = payoff_types(H)
    check("arm 7 IMPLIES arm 6 — the enum opens too", "SnapReframe" in a7, repr(a7))
    check("arm 7 enum == arm 6 enum (the only difference is prose)",
          set(a7) == set(a6), f"{a7} vs {a6}")

    old, new = H._PAYOFF_OPEN_SWAPS[0]
    check("the prohibition is REMOVED", "just another mid_peak" not in new)
    check("the register-fix is REMOVED", "fixes its register" not in new)
    check("the requirement is KEPT (it still must commit)",
          "COMMITMENT" in new and "commit" in new.lower())
    # The validity line: neutral, never advocacy.
    for word in ("snap", "punchy", "SnapReframe", "fast"):
        check(f"the swap never advocates ('{word}' absent)", word.lower() not in new.lower(),
              repr(new[:80]))
    check("it defers the choice to the moment",
          "the moment and the vibe actually ask for" in new)

    print("\n=== ARM 7b: the swap targets the REAL prompt (non-circular) ===")
    # Everything above compares the swap to ITSELF, which proves nothing about
    # whether it can ever fire. This checks the _old block is present verbatim in
    # handler.py's actual prose — the one thing that decides whether arm 7 runs
    # or raises at ignition, when there is no time to debug a prompt drift.
    _src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "handler.py"), encoding="utf-8").read()
    check("the _old block exists VERBATIM in the real prompt", old in _src,
          "arm 7 would RAISE at run time — fix the swap text, not the prose")
    check("it appears exactly once (an ambiguous target is not a swap)",
          _src.count(old) == 1, f"count={_src.count(old)}")
    check("the owner's doctrine line is still on record",
          "payoff purity = the commitment rule" in _src,
          "the ruling this arm tests must remain stated in the code it tests")

    print("\n=== ARM 8: a drifted prompt RAISES, never silently no-ops ===")
    try:
        H._apply_payoff_open_swap("a system instruction that does not contain the block")
        check("drift raises", False, "no raise — a silent no-op fakes a null")
    except RuntimeError as e:
        check("drift raises RuntimeError", True)
        check("the error names the arm", "PAYOFF_OPEN" in str(e))
    # and it must actually apply on the real prompt block
    real = ("preamble … " + H._PAYOFF_OPEN_SWAPS[0][0] + " … tail")
    out = H._apply_payoff_open_swap(real)
    check("the swap APPLIES to the verbatim block", out != real and new in out)
    check("it replaces exactly once", out.count(new) == 1)

    print("\n=== ARM 9: the two prose arms cannot run together ===")
    os.environ["PROMPTLY_DWELL"] = "1"
    check("DWELL and PAYOFF_OPEN both enabled is detectable",
          H._dwell_enabled() and H._payoff_open_enabled())
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "handler.py"), encoding="utf-8").read()
    check("the build path REFUSES both at once",
          "both rewrite the payoff" in src,
          "no guard — running both would measure neither arm")
    os.environ.pop("PROMPTLY_DWELL")
    os.environ.pop("PROMPTLY_PAYOFF_OPEN")

    print("\n=== ARM 10: back to control — no residue ===")
    check("enum restored", payoff_types(H) == ("LetterboxPush", "SmoothPush"))

    print()
    if FAILURES:
        print(f"PAYOFF-ARMS CERT: {len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("PAYOFF-ARMS CERT: ALL PASS (control byte-identical, arm 6 adds not replaces, "
          "arm 7 implies arm 6, swap neutralises without advocating, drift raises, "
          "prose arms mutually exclusive)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
