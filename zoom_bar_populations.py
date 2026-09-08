#!/usr/bin/env python3
"""The scale-fit bar across three populations. It does not hold.

MEASURED 2026-09-08. v1 arms rendered here through the REAL renderer — seven
zoom types, both arms, two sources, 28 renders. ZAC REAL is the table from
e2d86de, measured earlier by the same method and NOT re-measured today; it is
labelled so wherever it appears.

RESULT AGAINST THE PRE-REGISTERED FALSIFIER (real > bar, passthrough < bar,
and >= 2.0 dB of margin on both sides or NOT VALIDATED):

    v1 talking_head   FocusWindow real -12.57 vs bar -8.0    *** FAILS ***
                      a correctly applied zoom called NOT APPLIED
    v1 pet_video      7/7 correct, worst-real margin 1.74 dB  NOT VALIDATED
                      under the 2.0 dB I registered in advance
    13/14 correct

WHY, AND IT IS THE SAME SHAPE AS THE DEFECT IT REPLACED. The absolute geometry
bar was fitted to synthetic content and inverted on real footage. The scale-fit
ratio was then fitted to REAL footage — and it does not hold on the v1 corpus the
rounds actually run on. One level up, same error: a constant fitted to the
population in front of you.

The raw delta leaves no room. Across all three populations the only window that
separates every real from every passthrough is (-16.58, -12.57): 4.01 dB wide,
best case 2.00 dB either side, and the shipped bar of -8.0 sits OUTSIDE it.

    population              intrinsic   reals              passes
    ZAC REAL talking_head     19.13     -3.89 ..  +1.88    -19.86 .. -16.58
    v1 talking_head           26.60    -12.57 ..  -4.38    -30.48
    v1 pet_video              29.79     -6.26 ..  -2.30    -31.42

NORMALISING BY THE SOURCE'S OWN RESPONSIVENESS opens it up. delta + intrinsic:

    ZAC REAL talking_head     reals  15.24 .. 21.01   passes  -0.73 .. +2.55
    v1 talking_head           reals  14.03 .. 22.22   passes  -3.88
    v1 pet_video              reals  23.53 .. 27.49   passes  -1.63
    window 2.55 .. 14.03 — 11.48 dB wide, 5.74 either side of 8.29

2.9x the margin of the best possible raw constant, and it makes sense: the
delta's other term IS the intrinsic figure, so subtracting it removes the content
dependence the ratio was supposed to cancel and did not.

NOT ADOPTED HERE, DELIBERATELY. Three populations is what fitted the last two
bars, and I have now watched that fail twice. The normaliser is also empirical
rather than principled — intrinsic is measured at 1.10x while the arms run at
1.22x — so it needs validating on a corpus, not on the three clips that happen
to be in front of me. Proposed to Builder-1 with the numbers; theirs to accept
with corpus evidence, or to refuse.

RESULT ACROSS ALL FIVE (2026-09-08), and it INVERTS the proposal:

    RAW delta                 worst real -12.57  best pass -15.73  window +3.16
                              a bar exists at -14.15, margin 1.58 either side
    delta + intrinsic         worst real   3.65  best pass   4.03  window -0.38
                              NO BAR EXISTS — the populations OVERLAP

The normaliser does not merely fail to help; it makes the instrument
UNSEPARABLE, while the raw delta keeps a (thin) window. v2-geometry is why:
its raw reals (-3.54..+0.59) sit almost exactly where Zac's real footage sits
(-3.89..+1.88), so the two behave the SAME — and their intrinsics are 7.19 and
19.13, so adding intrinsic drives them 12 dB APART. The term does not cancel
content here; it injects a difference that the raw measurement did not have.

BUT THE VERDICT HINGES ON ONE NUMBER AND WE DISAGREE ABOUT IT.
    intrinsic 7.19  (mine, measured IN THE ARM WINDOW)  -> window -0.38, refuted
    intrinsic 13.80 (Builder-1's)                       -> window +6.23, holds
6.6 dB apart, and the margin at stake is ~5. Unresolved; nothing ships on it.

Mine is measured at the timestamps the arms actually render (0.15-0.75s), where
the source reads 7.18-7.20 — a 0.02 dB span. Measured across the WHOLE clip it
reads 7.17 with one outlier of 19.36 from a later scene, so that source is not
homogeneous and "its intrinsic" is not a single number. Which window you sample
decides the answer, and the arms only ever see the first 1.2s.

That method-dependence is itself an argument against the normaliser: a term
whose value moves 6.6 dB with sampling choice, used to buy a 5 dB margin, is not
a mechanism yet.

RUN: python3 zoom_bar_populations.py
"""
# FOURTH AND FIFTH POPULATIONS, rendered 2026-09-08 through the real renderer
# (28 more arms, 0 failures) at Builder-1's request. v2-geometry is the
# EXTRAPOLATION test — its intrinsic sits BELOW the three fitted populations, so
# a normaliser that holds there is doing real work rather than interpolating.
POP = {
    "v2-geometry talking_head": (7.19,
        [0.07, 0.01, -3.54, -0.01, -0.98, 0.59, 0.17], [-20.93] * 7),
    "heldout mandelbrot": (19.76,
        [-2.94, -2.94, -4.02, -2.92, -2.81, -3.08, -3.44], [-15.73] * 7),
    "ZAC REAL talking_head": (19.13,
        [1.35, 1.88, -3.89, 1.52, -0.91, -2.00, 1.33],
        [-17.36, -16.68, -19.86, -18.76, -16.58, -17.91, -17.85]),
    "v1 talking_head": (26.60,
        [-4.59, -4.55, -12.57, -4.55, -4.38, -6.73, -5.48], [-30.48] * 7),
    "v1 pet_video": (29.79,
        [-5.48, -5.46, -2.38, -5.45, -2.38, -2.30, -6.26], [-31.42] * 7),
}
TYPES = ["SmoothPush", "SnapReframe", "FocusWindow", "StepZoom",
         "LetterboxPush", "DepthPull", "StagedPush"]


def window(shift):
    lo = min(min(r) + shift * i for _, (i, r, _p) in POP.items())
    hi = max(max(p) + shift * i for _, (i, _r, p) in POP.items())
    return lo, hi


if __name__ == "__main__":
    for label, shift in (("RAW delta", 0), ("delta + intrinsic", 1)):
        lo, hi = window(shift)
        print(f"{label}: window ({hi:.2f}, {lo:.2f})  width {lo - hi:.2f} dB  "
              f"midpoint {(lo + hi) / 2:.2f}  margin {(lo - hi) / 2:.2f} either side")
    print("\nshipped bar -8.0 is inside the raw window: "
          f"{window(0)[1] < -8.0 < window(0)[0]}")
