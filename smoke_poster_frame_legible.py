#!/usr/bin/env python3
"""A menu component draws a legible picture of itself at frame 0, default props, no source.

WHY FRAME 0 IS THE ONE THAT MATTERS, measured 2026-09-21.

ChatCut renders a motion graphic's preview frames through the OPEN EDITOR'S web
renderer. `inspect_asset` with `sourceFrameCount` on a motion graphic returns a
`frames` object, and from this connector it comes back:

    "frames": {"status": "unavailable",
               "reason": "...No open ChatCut editor is available to render this
                          motion graphic... this connector renders frames with
                          the open tab's web renderer and does not render them
                          in the cloud on its own."}

That is a STATE, not an absence. The surface exists. Their agent runs with an
open editor by definition, so it CAN be shown rendered frames of our components
through exactly this path — and the frame it is most likely to be shown is the
first one.

So a component that is blank at frame 0 is a component their agent picks from an
empty square, and no amount of naming fixes that.

TWO SHAPES MAKE A POSTER BLANK, and EmojiCard had BOTH at once:

  1. AN OPACITY RAMP THAT STARTS AT ZERO. It read
     `fade = Math.min(Math.max(enter * 1.35, 0), 1)` where `enter` is a spring,
     and a spring is 0 on frame 0 — so card, badge and caption were fully
     transparent on the exact frame a poster is taken from. This also broke
     the lane's own caption law: the six sibling text components ease POSITION
     and never opacity, because FRAME-1-IS-FINAL for readable text.

  2. AN ERROR STRING AS THE WHOLE-COMPONENT FALLBACK. `still` is an image
     property whose registered default is the empty string, so a default
     placement took the `if (!still)` branch — and that branch rendered the
     words "NO STILL". The picture of the component was an error message.

The second is the more general defect: every one of these bodies has a bail-out
branch for its missing content, and a bail-out branch reached BY THE DEFAULTS is
not an error path, it is the poster.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BODIES = os.path.join(HERE, "port", "bodies")
sys.path.insert(0, HERE)
import lane_contract as lc                                     # noqa: E402

# An opacity ramp is the EFFECT of these, not a defect. Each is an overlay whose
# whole job is a ramp; a poster of one at frame 0 is correctly near-invisible
# because at frame 0 the effect has not happened. They are not text components
# and nobody picks them from a tile expecting to read them.
PINNED_OPACITY_RAMP = {
    "ShutterFlashOverlay": "the flash IS an opacity ramp; peak 0.82 is the component",
    "LightLeakOverlay": "the leak IS an opacity ramp; l2 peak 0.70 is the component",
    "DipToBlack": "the dip IS an opacity ramp, and its midpoint is deliberately black",
    "ShutterFlash": "as ShutterFlashOverlay; out of scope on usage",
    "CardSwipe": "opacityA/opacityB carry the swap between two clips",
    "ZoomThrough": "opacityA/opacityB carry the swap; found by widening the scope "
                   "to renderable, which is the pin working rather than a hole",
    "FilmStrip": "advancing frames fade between cells",
    "CrossfadeZoom": "a crossfade is an opacity ramp by definition",
    "Stack": "the incoming card fades over the outgoing one",
    "DepthPull": "the haze and orbs fade in and out across the pull",
}

FAILS = []


def leg(name, ok, got):
    print("  %-40s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def strip_comments(src):
    r"""Remove // and /* */ so no leg can match its own prose.

    L2 and L3 both did, and L3 was WRONG because of it: PlainText's body carries
    the sentence "opacity: this repo's caption law is FRAME-1-IS-FINAL", and a
    bare `opacity:\s*[A-Za-z_]` matched that comment. A pin for PlainText — a
    component that ramps no opacity at all — therefore read as LIVE, and the
    stale-pin leg could not fire. The check was reading the argument ABOUT the
    code instead of the code.
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def fallback_renders_only_a_string(src):
    """-> the error text, if a whole-component bail-out returns bare text.

    The shape is a `return (` inside an `if (!x) {` guard whose JSX contains a
    short ALL-CAPS string and no structural element of the component. Matched on
    the string because that is the thing that is wrong: a word where a picture
    should be.
    """
    out = []
    for m in re.finditer(r"if \(!\s*[A-Za-z_.]+\s*\)\s*\{\s*return \((.{0,400}?)\);\s*\}",
                         src, re.S):
        block = m.group(1)
        for t in re.findall(r">\s*\n?\s*([A-Z][A-Z ]{2,30})\s*\n?\s*<", block):
            out.append(t.strip())
    return out


def main():
    ls = lc.live_set()
    if ls["state"] != lc.MEASURED:
        print("HARNESS FAILURE: live_set is %s" % ls["state"])
        return 2
    menu = [n for n in ls["menu"] if os.path.exists(os.path.join(BODIES, n + ".jsx"))]

    # A CHECK OVER AN EMPTY POPULATION ASSERTS NOTHING.
    leg("L0 menu_bodies_present", len(menu) >= 5,
        "%d menu component(s) with a body here: %s" % (len(menu), ", ".join(sorted(menu))))
    if not menu:
        print("0/0 — refusing to report a pass over an empty menu")
        return 1

    # L1 NO MENU COMPONENT RENDERS AN ERROR STRING AS ITS POSTER.
    #
    # REACHABILITY IS THE WHOLE PROPERTY, and the first version of this leg did
    # not have it. It flagged every body carrying a bail-out branch and fired on
    # five that are fine: PlainText, CaptionMatch, LowerThird, QuoteCard and
    # StickyNotes all guard a prop whose REGISTERED DEFAULT is real copy, so a
    # default placement never reaches the branch. EmojiCard was the only true
    # positive, because `still` is an image prop whose default is the empty
    # string.
    #
    # A body carries no defaults by law — they live in the property table — so a
    # static read of a body cannot tell a reachable fallback from an unreachable
    # one. measured/REGISTERED_DEFAULTS.json is that missing half, read back off
    # the live project rather than assumed.
    reg = json.load(open(os.path.join(HERE, "measured", "REGISTERED_DEFAULTS.json")))
    defaults = reg["components"]
    bad, unrecorded = {}, []
    for n in sorted(menu):
        src = open(os.path.join(BODIES, n + ".jsx"), encoding="utf-8").read()
        hits = fallback_renders_only_a_string(src)
        if not hits:
            continue
        row = defaults.get(n)
        if row is None:
            # AN UNRECORDED DEFAULT IS NOT A PASS. It is a component whose
            # reachability nobody has measured, and silence there is how the
            # blank one got through the first time.
            unrecorded.append(n)
        elif not str(row.get("default", "")).strip():
            bad[n] = hits
    leg("L1 no_error_string_as_poster", not bad and not unrecorded,
        "reachable: %s | default UNRECORDED (not a pass): %s"
        % (bad or "none", unrecorded or "none"))

    # L1b THE DETECTOR CAN STILL SEE ONE. Break the pattern and L1 finds no
    # bail-out branches anywhere, then passes for the wrong reason — a clean
    # corpus and a blind detector are the same output. The canary is a string
    # this file owns, so it cannot go stale with the bodies.
    CANARY = ('  if (!text) {\n    return (\n      <div style={s}>\n'
              '        <div style={t}>\n          NO TEXT\n        </div>\n'
              '      </div>\n    );\n  }')
    leg("L1b detector_finds_a_known_positive",
        fallback_renders_only_a_string(CANARY) == ["NO TEXT"],
        "canary -> %s" % fallback_renders_only_a_string(CANARY))

    # L2 NO MENU COMPONENT COMPUTES ITS OPACITY AT ALL.
    #
    # THE FIRST VERSION LOOKED FOR THE WRONG THING and could not fire. It found
    # `opacity: <ident>`, then searched that identifier's DEFINITION for
    # `spring(` / `ease` / `interpolate(`. PlainText's is
    # `const ease = 1 - Math.pow(1 - t, 3)` — which mentions none of them,
    # because it IS the ease rather than a call to one. The mutation applied
    # `opacity: ease` and the leg stayed green.
    #
    # The law is simpler than the detection was: these components ease POSITION
    # and never opacity, because FRAME-1-IS-FINAL for readable text. So ANY
    # computed opacity on a menu component is the defect, whatever it is derived
    # from. A literal (`opacity: 1`) does not match; an identifier does. That
    # also catches the shape nobody has written yet — an opacity driven straight
    # off a prop — without needing to enumerate how it was produced.
    # SCOPED TO `renderable`, NOT `menu`, AND THE REASON IS STRUCTURAL.
    # live_set binds every DRAWS verdict to the sha of the body that drew it, so
    # editing a body drops that component OFF the menu until it is re-shot. A
    # menu-scoped leg therefore cannot see a body mutation — the mutation
    # removes its own target from the population. My red proof hit exactly that:
    # `opacity: ease` was spliced into PlainText, PlainText went STALE_BODY, and
    # the leg reported "none" truthfully about a menu that no longer contained
    # it. Two correct mechanisms composing into a blind spot.
    faders = {}
    for n in sorted(ls["renderable"]):
        if n in PINNED_OPACITY_RAMP:
            continue
        if not os.path.exists(os.path.join(BODIES, n + ".jsx")):
            continue
        src = strip_comments(open(os.path.join(BODIES, n + ".jsx"), encoding="utf-8").read())
        for m in re.finditer(r"opacity:\s*([A-Za-z_][A-Za-z0-9_.]*)", src):
            faders.setdefault(n, []).append(m.group(1))
    leg("L2 no_computed_opacity_outside_pins", not faders, "%s" % (faders or "none"))

    # L3 THE PINS ARE LIVE. A pin for a component that no longer ramps opacity
    # is a stale argument, and a stale note is read as fact by the next reader.
    stale = []
    for n in sorted(PINNED_OPACITY_RAMP):
        p = os.path.join(BODIES, n + ".jsx")
        if not os.path.exists(p):
            stale.append("%s (no body)" % n)
            continue
        if not re.search(r"opacity:\s*[A-Za-z_]",
                         strip_comments(open(p, encoding="utf-8").read())):
            stale.append(n)
    leg("L3 no_stale_opacity_pins", not stale, "stale: %s" % (stale or "none"))

    print("%d/%d legs ok" % (5 - len(FAILS), 5))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
