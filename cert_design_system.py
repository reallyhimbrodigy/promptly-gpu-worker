#!/usr/bin/env python3
"""Design-system cert — offline, $0, calibrated on the real references [§3.1/§4.2].

THE CANON RULE: if the reference set fails a quality dimension, the DIMENSION is
broken, not the references. This cert exists because that already happened here.

The first palette extractor sampled only the opening seconds, returned five
near-identical whites for both references, found no chromatic swatch, and fired
its hue-rotation fallback — inventing a GREEN accent for REF-1, which
LUMEN_REFERENCE_SPEC §1.F documents as orange/blue/white. The reference was
right and the extractor was wrong. These assertions are what make that
un-repeatable.

  python3 cert_design_system.py
"""
import colorsys
import os
import sys

FAILURES = []
REFS = "golden/lumen-refs"


def check(label, cond, detail=""):
    if cond:
        print(f"  [PASS] {label}")
    else:
        FAILURES.append(f"{label}{(' — ' + detail) if detail else ''}")
        print(f"  [FAIL] {label}{(' — ' + detail) if detail else ''}")


def hue_deg(hexs):
    r, g, b = (int(hexs[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)[0] * 360.0


def sat(hexs):
    r, g, b = (int(hexs[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)[1]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    from design_system import build_design_system, safe_zones, TYPE_SCALE

    r1 = os.path.join(here, REFS, "ref1-legalsoft-corporate-landscape.mp4")
    r2 = os.path.join(here, REFS, "ref2-viral-creator-doc-vertical.mp4")
    if not (os.path.exists(r1) and os.path.exists(r2)):
        print("SKIP(no-refs) — reference goldens absent; palette calibration not verified.")
        return 0

    print("=== ARM 1: THE CANON RULE — REF-1's documented palette must extract ===")
    ds1 = build_design_system(r1, canvas=(1920, 1080), work_dir="/tmp/cert_ds1")
    p1 = ds1["palette"]
    print(f"       REF-1 bg={p1['bg']} accent={p1['accent']} swatches={p1['swatches']}")
    check("REF-1 palette is EXTRACTED, not the fallback",
          p1["source"] == "extracted",
          "the fallback firing on a real reference means the extractor failed")
    h = hue_deg(p1["accent"])
    check(f"REF-1 accent is ORANGE-family (hue {h:.0f}deg in 15-45), per §1.F",
          15 <= h <= 45,
          f"got hue {h:.0f}deg — §1.F documents orange/blue/white; a green/other "
          f"accent means the sample is unrepresentative, as it did the first time")
    check("REF-1 accent is genuinely chromatic (sat >= 0.35)", sat(p1["accent"]) >= 0.35,
          f"sat={sat(p1['accent']):.2f} — a near-grey is not an accent")
    _blues = [s for s in p1["swatches"] if 190 <= hue_deg(s) <= 250]
    check("REF-1 swatches also carry the BLUE half of its palette", bool(_blues),
          f"swatches={p1['swatches']}")

    print("\n=== ARM 2: canvas + doctrine follow the reference, not a constant ===")
    check("REF-1 reads landscape", ds1["canvas"]["orientation"] == "landscape")
    check("REF-1 gets BROADCAST title-safe (no app chrome to dodge)",
          ds1["safe"]["doctrine"] == "broadcast_title_safe")
    ds2 = build_design_system(r2, canvas=(1080, 1920), work_dir="/tmp/cert_ds2")
    check("REF-2 reads vertical", ds2["canvas"]["orientation"] == "vertical")
    check("REF-2 gets the PLATFORM-UI exclusion band",
          ds2["safe"]["doctrine"] == "platform_ui_exclusion")
    check("the two doctrines are genuinely different",
          ds1["safe"]["doctrine"] != ds2["safe"]["doctrine"])

    print("\n=== ARM 3: NO TEMPLATING — two videos, two palettes [§4.2] ===")
    check("the two references extract DIFFERENT palettes",
          ds1["palette"]["accent"] != ds2["palette"]["accent"]
          or ds1["palette"]["bg"] != ds2["palette"]["bg"],
          "identical palettes across different footage would BE a template")

    print("\n=== ARM 4: determinism — the differ depends on it ===")
    again = build_design_system(r1, canvas=(1920, 1080), work_dir="/tmp/cert_ds1b")
    check("same video in, same palette out", again["palette"] == p1,
          f"{again['palette']} vs {p1}")

    print("\n=== ARM 5: type scale is canvas-relative, never pixel constants ===")
    check("hero > display > title > body > label",
          TYPE_SCALE["hero"] > TYPE_SCALE["display"] > TYPE_SCALE["title"]
          > TYPE_SCALE["body"] > TYPE_SCALE["label"])
    check("landscape and vertical resolve to DIFFERENT pixel sizes",
          ds1["type_scale"]["hero"] != ds2["type_scale"]["hero"],
          "a pixel constant would make the same type look tiny on landscape")
    check("legibility floor: body >= 20px on the smaller canvas",
          min(ds1["type_scale"]["body"], ds2["type_scale"]["body"]) >= 20)

    print("\n=== ARM 6: fg is DERIVED for contrast, never picked ===")
    for _n, _ds in (("REF-1", ds1), ("REF-2", ds2)):
        _bg, _fg = _ds["palette"]["bg"], _ds["palette"]["fg"]
        _lb = sum(int(_bg[i:i + 2], 16) for i in (1, 3, 5)) / 765.0
        _lf = sum(int(_fg[i:i + 2], 16) for i in (1, 3, 5)) / 765.0
        check(f"{_n}: fg contrasts bg (delta {abs(_lf - _lb):.2f} >= 0.45)",
              abs(_lf - _lb) >= 0.45, f"bg={_bg} fg={_fg}")

    print()
    if FAILURES:
        print(f"DESIGN-SYSTEM CERT: {len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("DESIGN-SYSTEM CERT: ALL PASS (REF-1's documented orange extracts, blue in "
          "swatches, two canvases two doctrines, palettes differ per video, "
          "deterministic, type scale canvas-relative, fg derived for contrast)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
