#!/usr/bin/env python3
"""The fourth-population test for the normalised zoom bar. Falsifier FIRST.

WHY A FOURTH. The normaliser (delta + intrinsic) was proposed on three
populations and Builder-2 declined to ship it there — correctly, because three
populations is exactly what fitted the two bars that already failed: an absolute
bar fitted to synthetic that inverted on real, then a ratio fitted to real that
fails on the v1 corpus the rounds actually run on. Twice, a constant fitted to
the population in front of us.

WHY v2-GEOMETRY IS THE ONE THAT MATTERS. The three fitted populations span
intrinsic 19.13-29.79 dB. v2-geometry reads 13.80 — BELOW that range. A
normaliser that must also hold at 13.8 is being EXTRAPOLATED rather than
interpolated, and that is the only kind of evidence that distinguishes a term
doing real work from a curve through three points. The held-out mandelbrot at
19.89 sits inside the range and is the weaker of the two tests; it is included
because a different GENERATOR (fractal, not cellular automaton) is a different
population even at a similar intrinsic.

THE FALSIFIER IS WRITTEN HERE BEFORE THE ARMS EXIST, so it cannot be widened
to fit what comes back. That is the discipline that caught both previous bars —
Builder-2 pre-registered the v1 failure and then reported it against itself.

  SHIP only if, on BOTH new populations:
      every real arm      > bar + 2.0
      every passthrough   < bar - 2.0
  Anything else: NOT VALIDATED. The check stays unshipped and zoom goes
  UNMEASURED rather than mismeasured — a wrong zoom check costs a component
  edit on working code, which is what round 36 nearly bought.

  python3 zoom_bar_fourth_population.py            # show the falsifier
  python3 zoom_bar_fourth_population.py --check    # score it once ARMS is filled
"""
import sys

# From zoom_bar_populations.POP — the three the normaliser was fitted on.
FITTED = {
    "ZAC REAL talking_head": (19.13,
        [1.35, 1.88, -3.89, 1.52, -0.91, -2.00, 1.33],
        [-17.36, -16.68, -19.86, -18.76, -16.58, -17.91, -17.85]),
    "v1 talking_head": (26.60,
        [-4.59, -4.55, -12.57, -4.55, -4.38, -6.73, -5.48], [-30.48] * 7),
    "v1 pet_video": (29.79,
        [-5.48, -5.46, -2.38, -5.45, -2.38, -2.30, -6.26], [-31.42] * 7),
}

# The fourth population. intrinsic MEASURED; arms are None until rendered
# through the REAL renderer. None is not an empty list: a population whose arms
# were never rendered must not score as one that passed with nothing.
NEW = {
    "v2-geometry talking_head": {"intrinsic": 13.80, "reals": None, "passes": None,
                                 "src": "/tmp/fixtures_v2/talking_head.mp4",
                                 "note": "BELOW the fitted 19.13-29.79 range — "
                                         "the extrapolative test"},
    "held-out mandelbrot": {"intrinsic": 19.89, "reals": None, "passes": None,
                            "src": "/tmp/zoompop/heldout_mandelbrot.mp4",
                            "note": "different GENERATOR (fractal, not cellauto)"},
}
MARGIN = 2.0


def bar_from_fitted():
    reals = [min(r) + i for i, r, _p in FITTED.values()]
    passes = [max(p) + i for i, _r, p in FITTED.values()]
    lo, hi = min(reals), max(passes)
    return (lo + hi) / 2, lo, hi


def main():
    bar, lo, hi = bar_from_fitted()
    print(f"NORMALISED METRIC: delta + intrinsic")
    print(f"  fitted on 3 populations, intrinsic "
          f"{min(i for i, _, _ in FITTED.values()):.2f}-"
          f"{max(i for i, _, _ in FITTED.values()):.2f} dB")
    print(f"  window: passes < {hi:.2f}, reals > {lo:.2f}   "
          f"bar {bar:.2f}, margin {(lo - hi) / 2:.2f} either side")
    print(f"\nFALSIFIER (pre-registered): real > {bar + MARGIN:.2f}, "
          f"passthrough < {bar - MARGIN:.2f}")
    unrendered = [k for k, v in NEW.items() if v["reals"] is None]
    print(f"\nFOURTH POPULATION:")
    for k, v in NEW.items():
        state = "ARMS NOT RENDERED" if v["reals"] is None else "rendered"
        print(f"  {k:26} intrinsic {v['intrinsic']:5.2f}  {state}")
        print(f"      {v['note']}")
        print(f"      {v['src']}")
    if unrendered:
        print(f"\n  {len(unrendered)} population(s) UNRENDERED — VERDICT UNAVAILABLE.")
        print("  Not 'passed'. A population whose arms were never rendered scores")
        print("  nothing, and treating None as an empty pass is the failed-")
        print("  measurement-as-clean-result class this repo has hit four times.")
        return 2
    bad = []
    for k, v in NEW.items():
        for t, d in zip(("real",) * len(v["reals"]), v["reals"]):
            if d + v["intrinsic"] <= bar + MARGIN:
                bad.append(f"{k}: a real arm normalises to {d + v['intrinsic']:.2f} "
                           f"<= {bar + MARGIN:.2f}")
        for d in v["passes"]:
            if d + v["intrinsic"] >= bar - MARGIN:
                bad.append(f"{k}: a passthrough normalises to "
                           f"{d + v['intrinsic']:.2f} >= {bar - MARGIN:.2f}")
    if bad:
        print("\n  NOT VALIDATED:")
        for b in bad:
            print(f"    {b}")
        print("\n  The check stays unshipped. Zoom goes UNMEASURED rather than")
        print("  mismeasured.")
        return 1
    print("\n  VALIDATED on four populations with margin either side — ship it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
