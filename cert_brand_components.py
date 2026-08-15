#!/usr/bin/env python3
"""NAME-PLATE (D) + END-CARD (F) cert — offline, $0, no Gemini, no render.

The canon rule applies: the references define the bar. Both components exist to
be SEEN, so the properties asserted here are the ones a viewer would notice —
type that is legible rather than astronomical, a card that ends with the edit
rather than after it, and a colour that came from this video rather than from a
constant.

  python3 cert_brand_components.py
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


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    import design_system as ds
    import brand_components as bc

    V = ds.build_design_system(video_path=None, canvas=(1080, 1920))
    L = ds.build_design_system(video_path=None, canvas=(1920, 1080))

    print("=== ARM 1: UNITS — type_scale is PIXELS, not a ratio to re-multiply ===")
    np_v = bc.build_name_plate(V, "Dana Reyes", role="Managing Partner")
    ec_v = bc.build_end_card(V, "LegalSoft", subline="legalsoft.com", duration_s=42.0)
    # The bug this arm exists for produced name_px=192000 — px multiplied by
    # height a second time. Anything above the canvas is nonsense by definition.
    check("name_px is legible, not astronomical",
          8 <= np_v["style"]["name_px"] <= V["canvas"]["height"] // 4,
          f"name_px={np_v['style']['name_px']}")
    check("role_px is smaller than name_px (hierarchy, not decoration)",
          np_v["style"]["role_px"] < np_v["style"]["name_px"], str(np_v["style"]))
    check("headline_px is legible",
          8 <= ec_v["style"]["headline_px"] <= V["canvas"]["height"] // 3,
          f"headline_px={ec_v['style']['headline_px']}")
    check("headline is LARGER than the name-plate name (the card is the moment)",
          ec_v["style"]["headline_px"] > np_v["style"]["name_px"])

    print("\n=== ARM 2: the colour is THIS VIDEO'S, never invented locally ===")
    check("name-plate accent == the design system's accent",
          np_v["style"]["accent"] == V["palette"]["accent"])
    check("end-card field IS the accent (the one moment brand owns the frame)",
          ec_v["style"]["background"] == V["palette"]["accent"])
    check("end-card foreground is the palette's, not a constant",
          ec_v["style"]["color"] == V["palette"]["bg"])
    fake = {"palette": {"accent": "#123456", "fg": "#FFFFFF", "bg": "#000000"},
            "type_scale": V["type_scale"], "safe": V["safe"], "canvas": V["canvas"]}
    check("a DIFFERENT palette produces a different plate (not memoised/constant)",
          bc.build_name_plate(fake, "X")["style"]["accent"] == "#123456")

    print("\n=== ARM 3: NO DESIGN SYSTEM -> NO COMPONENT (byte-identical to today) ===")
    for bad, why in ((None, "None"), ({}, "empty"),
                     ({"palette": {}}, "no accent"),
                     ({"palette": {"accent": "#F06D1F"}}, "no type scale")):
        check(f"returns None when the design system is {why}",
              bc.build_name_plate(bad, "Dana") is None
              and bc.build_end_card(bad, "LegalSoft") is None)
    check("no NAME -> no plate (a nameless plate is a coloured bar)",
          bc.build_name_plate(V, "") is None and bc.build_name_plate(V, "   ") is None)
    check("no HEADLINE -> no card", bc.build_end_card(V, None) is None)
    both = bc.build_brand_specs(None, name="X", headline="Y")
    check("build_brand_specs keeps a stable shape with None values",
          set(both) == {"name_plate", "end_card"} and both["name_plate"] is None)

    print("\n=== ARM 4: LANDSCAPE is a first-class canvas, not a rescaled vertical ===")
    np_l = bc.build_name_plate(L, "Dana Reyes", role="Managing Partner")
    check("landscape type is SMALLER (shorter canvas), not identical",
          np_l["style"]["name_px"] < np_v["style"]["name_px"],
          f"{np_l['style']['name_px']} vs {np_v['style']['name_px']}")
    check("vertical carries the platform-UI doctrine",
          np_v["safe"]["doctrine"] == "platform_ui_exclusion", str(np_v["safe"]))
    check("landscape carries the BROADCAST doctrine — a different danger",
          np_l["safe"]["doctrine"] == "broadcast_title_safe", str(np_l["safe"]))
    check("placement is FRACTIONAL, so it survives the canvas change",
          np_v["anchor"]["y_fraction"] == np_l["anchor"]["y_fraction"])

    print("\n=== ARM 5: the end-card ENDS with the edit, never after it ===")
    for dur in (12.0, 42.0, 90.0):
        ec = bc.build_end_card(V, "LegalSoft", duration_s=dur)
        end = ec["start_s"] + ec["hold_s"]
        check(f"duration {dur}s: card ends at {end:.2f}s, inside the edit", end <= dur,
              f"start={ec['start_s']} hold={ec['hold_s']}")
    short = bc.build_end_card(V, "LegalSoft", duration_s=1.0)
    check("an edit SHORTER than the card still yields start_s >= 0 (never negative)",
          short["start_s"] >= 0, str(short["start_s"]))
    check("no duration -> start_s is None, not a guess",
          bc.build_end_card(V, "LegalSoft")["start_s"] is None)

    print("\n=== ARM 6: deterministic — two runs of one edit cannot disagree ===")
    a = bc.build_brand_specs(V, name="Dana Reyes", role="Partner",
                             headline="LegalSoft", duration_s=42.0)
    b = bc.build_brand_specs(V, name="Dana Reyes", role="Partner",
                             headline="LegalSoft", duration_s=42.0)
    check("same inputs -> identical specs", a == b)
    check("an empty role is DROPPED, not rendered blank",
          bc.build_name_plate(V, "Dana", role="   ")["role"] is None)

    print()
    if FAILURES:
        print(f"BRAND-COMPONENTS CERT: {len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("BRAND-COMPONENTS CERT: ALL PASS (units are px, colour is the video's, "
          "no-design-system is byte-identical, landscape is first-class, the card "
          "ends inside the edit, deterministic)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
