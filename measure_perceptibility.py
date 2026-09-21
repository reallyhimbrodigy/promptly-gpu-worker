#!/usr/bin/env python3
"""THE PERCEPTIBILITY TEST, run on the amber screen composite.

Ruled by Zac 2026-09-21: LightLeakOverlay's 0.82 was BORROWED from
ShutterFlashOverlay, so measure it — "the same perceptibility test
ShutterFlashOverlay got in June — speaker legible through the effect at peak —
on the amber screen composite. Then it's a number, not a guess."

WHAT IS MEASURED. Retained detail: the RMS of the high-pass luma (luma minus a
blurred copy) of the composite, over the same quantity for the clean frame.
That is a direct proxy for "is there still visible texture in the face" — it
ignores the overall brightness shift, which is the EFFECT, and counts only the
modulation, which is the PICTURE.

WHY IT CANCELS CONTENT. The criterion is a RATIO taken against the same frame,
so the source's own detail divides out. This repo has twice set an absolute
threshold from one draw and had the arms swap sides on different content; a
ratio within one measurement has no population constant to mis-fit.

THE REFERENCE IS SHUTTERFLASH AT ITS ACCEPTED 0.82, NOT A NUMBER I CHOSE. Its
wash is #ffffff composited NORMALLY, so retention is exactly 1 - peak = 0.18,
and that value is the one judged acceptable in June after 0.95 was judged a
blown exposure. Every LightLeak candidate is scored against that same bar on
that same frame.

THE BOUND IS THE WORST PIXEL, NOT THE AVERAGE. l1 and l2 are travelling radial
glows; where their centres coincide the two screens stack. Averaging over the
frame would report a comfortable number for a component that erases the face at
the bloom. So the composites here are evaluated at FULL gradient alpha — the
worst case the component can actually produce — and that is stated rather than
hidden in a mean.

MODEL, AND ITS LIMIT, STATED. The blends are the W3C formulae for screen and
soft-light applied per channel at the layer opacities the body declares, over a
real frame of the real source. It does NOT model the 28-40px blur, the gradient
falloff, or the two blooms' exact overlap geometry — all of which make the real
frame KINDER than this bound. So the k it returns is conservative by
construction: safe to ship, and to be confirmed against Builder 1's render.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
REF_RETENTION = None  # measured from ShutterFlash at its registered peak


def luma(a):
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def detail_rms(rgb01):
    """RMS of the high-pass luma — the visible texture, brightness removed."""
    y = luma(rgb01)
    im = Image.fromarray((np.clip(y, 0, 1) * 255).astype(np.uint8))
    lo = np.asarray(im.filter(ImageFilter.GaussianBlur(radius=4)), dtype=np.float64) / 255.0
    return float(np.sqrt(np.mean((y - lo) ** 2)))


def hexrgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64) / 255.0


def screen(s, b):
    return 1.0 - (1.0 - s) * (1.0 - b)


def soft_light(s, b):
    d = np.where(s <= 0.25, ((16 * s - 12) * s + 4) * s, np.sqrt(np.clip(s, 0, 1)))
    return np.where(b <= 0.5,
                    s - (1 - 2 * b) * s * (1 - s),
                    s + (2 * b - 1) * (d - s))


def over(s, blended, alpha):
    return (1.0 - alpha) * s + alpha * blended


def shutterflash(src, peak, color="#ffffff"):
    """The wash only: a flat colour composited NORMALLY at `peak`."""
    return over(src, np.broadcast_to(hexrgb(color), src.shape), peak)


def lightleak(src, l2_peak, intensity=1.0, palette="warm", blend="registered"):
    """Worst-case stack at full gradient alpha, the bound at the coincident bloom.

    blend="registered" IS THE ONE THAT MATTERS, AND IT IS THE DEFAULT.

    CHATCUT STRIPS mixBlendMode AT REGISTRATION. Read back from the registered
    asset on 2026-09-21: all three declarations gone, with the source comments
    still saying "drawn in `screen`". That is a FIFTH auto-rewrite alongside the
    props-fallback strip, the nested ({item}) injection, <img> -> <Img>, and the
    trailing newline — and it is the only one that silently changes what the
    component LOOKS LIKE rather than how it is written.

    My first measurement modelled the DESIGN (screen + soft-light) and solved
    0.71. The registered runtime composites NORMALLY, which is far heavier, and
    the rendered still is the tiebreaker: it showed the picture all but gone,
    which is what the normal model predicts (0.033 retained) and not what the
    screen model predicts (0.069 at the same value, on a bar of 0.18).
    The frame is evidence FOR the normal model. `blend="designed"` is kept only
    so the two can be compared and the gap stays visible.
    """
    pal = {"warm": {"primary": "#FF8A30", "secondary": "#FFB870", "highlight": "#FFE2B0"},
           "gold": {"primary": "#FFC93C", "secondary": "#FFE070", "highlight": "#FFF7C8"},
           "cool": {"primary": "#5BC8FF", "secondary": "#A8DCFF", "highlight": "#E0F2FF"},
           "magenta": {"primary": "#E64FA1", "secondary": "#F593C5", "highlight": "#FFD6EB"}}[palette]
    out = src
    sec = np.broadcast_to(hexrgb(pal["secondary"]), src.shape)
    pri = np.broadcast_to(hexrgb(pal["primary"]), src.shape)
    hi = np.broadcast_to(hexrgb(pal["highlight"]), src.shape)
    if blend == "designed":
        out = over(out, soft_light(out, sec), 0.30 * intensity)
        out = over(out, screen(out, pri), 0.85 * intensity)
        out = over(out, screen(out, hi), l2_peak * intensity)
    else:
        # mixBlendMode is gone by the time this renders: every layer is a plain
        # alpha composite of a flat-ish colour over the picture.
        out = over(out, sec, 0.30 * intensity)
        out = over(out, pri, 0.85 * intensity)
        out = over(out, hi, l2_peak * intensity)
    return np.clip(out, 0, 1)


def main():
    frame = sys.argv[1] if len(sys.argv) > 1 else None
    if not frame or not os.path.exists(frame):
        print("HARNESS FAILURE: need a clean source frame as argv[1]")
        return 2
    src = np.asarray(Image.open(frame).convert("RGB"), dtype=np.float64) / 255.0
    base = detail_rms(src)
    if base <= 1e-6:
        # A FLAT FRAME CANNOT MEASURE PERCEPTIBILITY. Dividing by it would make
        # every composite look perfectly legible.
        print("HARNESS FAILURE: the reference frame has no detail to retain (rms=%.6f)" % base)
        return 2
    print("clean frame: %s   detail rms %.5f" % (os.path.basename(frame), base))

    sf = detail_rms(shutterflash(src, 0.82)) / base
    sf95 = detail_rms(shutterflash(src, 0.95)) / base
    print()
    print("REFERENCE — ShutterFlashOverlay, white wash, normal blend:")
    print("   peak 0.82 (accepted June 2026)   retained detail %.4f   <- the bar" % sf)
    print("   peak 0.95 (judged a blown exposure) retained %.4f" % sf95)

    print()
    print("LightLeakOverlay, warm palette, intensity 1.0, worst-case bloom:")
    rows = []
    for k in [1.00, 0.82, 0.70, 0.60, 0.50, 0.40, 0.30, 0.20, 0.10, 0.05, 0.0]:
        r = detail_rms(lightleak(src, k)) / base
        rows.append((k, r))
        flag = "PASSES" if r >= sf else "below the bar"
        print("   l2 peak %.2f   retained detail %.4f   %s" % (k, r, flag))

    # solve for the largest k meeting the bar, by bisection on a monotone curve
    lo, hi = 0.0, 1.0
    if detail_rms(lightleak(src, 0.0)) / base < sf:
        print("\n   NO k SATISFIES THE BAR — even with l2 fully off, l1 and the wash")
        print("   alone retain %.4f against a bar of %.4f. The defect is not l2 only."
              % (detail_rms(lightleak(src, 0.0)) / base, sf))
        solved = None
    else:
        for _ in range(40):
            mid = (lo + hi) / 2
            if detail_rms(lightleak(src, mid)) / base >= sf:
                lo = mid
            else:
                hi = mid
        solved = lo
        print("\n   SOLVED: l2 peak %.3f is the largest value that keeps the picture" % solved)
        print("   as legible as ShutterFlash at its accepted 0.82.")

    out = {
      "_what": "perceptibility of the source through the effect, at the peak of each overlay",
      "_metric": "RMS of high-pass luma (radius-4 gaussian), composite / clean. Brightness removed; texture counted.",
      "_why_a_ratio": "taken against the same frame so the source's own detail divides out — no absolute threshold fitted to one draw",
      "_bound": "evaluated at FULL gradient alpha with l1 and l2 coincident: the worst pixel the component can produce, not the frame mean",
      "_model_limits": "does not model the 28-40px blur, the radial falloff, or the real overlap of the two blooms — all of which make the rendered frame KINDER than this bound, so the result is conservative",
      "_reference_frame": os.path.basename(frame),
      "_clean_detail_rms": round(base, 6),
      "shutterflash_0.82_retained": round(sf, 4),
      "shutterflash_0.95_retained": round(sf95, 4),
      "lightleak_ladder": [{"l2_peak": k, "retained": round(r, 4)} for k, r in rows],
      "solved_l2_peak": (round(solved, 3) if solved is not None else None),
      "l1_and_wash_alone_retained": round(detail_rms(lightleak(src, 0.0)) / base, 4),
    }
    p = os.path.join(HERE, "measured", "PERCEPTIBILITY_2026-09-21.json")
    json.dump(out, open(p, "w"), indent=2)
    open(p, "a").write("\n")
    print("\n   written to %s" % os.path.relpath(p, HERE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
