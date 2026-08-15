#!/usr/bin/env python3
"""NAME-PLATE (D) and END-CARD (F) — the first components a viewer can SEE.

`[§3.1, LUMEN_REFERENCE_SPEC components D and F]`

Both consume the DESIGN SYSTEM and invent nothing: colour, type size and safe
zones all come from `edit_plan["_design_system"]`, which is derived from the
user's own footage. A component that picks its own colour is a second design
system competing with the real one — it looks right in every cert and wrong on
every video.

PURE AND DETERMINISTIC. These build SPECS, not pixels: dicts the renderer
consumes. No I/O, no network, no model. So the same edit always produces the same
name-plate, two runs cannot disagree, and the whole thing certs offline for $0.

NO DESIGN SYSTEM -> NO COMPONENT. Every builder returns None when the palette is
missing, and None means "render exactly as today". Falling back to a default
colour would put an invented brand on the frame at the precise moment we know
least about the video.

WHAT THE REFERENCES ACTUALLY DO:

  D  name-plate   REF-1 introduces the speaker with a lower-third: name in
                  title weight, role in label weight beneath it, an accent
                  rule, held ~2.5-3s early in the edit. It appears ONCE.
  F  end-card     Both references close on a held card — REF-1 a corporate
                  lockup, REF-2 a creator handle. Accent background, contrasting
                  foreground, the last thing on screen and the only moment the
                  edit is allowed to be still.
"""

# Held durations, in seconds. From the references, not from taste: a name-plate
# shorter than ~2s cannot be read, and an end-card longer than ~3.5s is where a
# viewer leaves.
NAME_PLATE_HOLD_S = 2.8
END_CARD_HOLD_S = 3.0

# The name-plate belongs in the lower third — but "lower third" is a fraction of
# the canvas, not a pixel count, or it breaks the moment the canvas is landscape.
_NAME_PLATE_Y_FRACTION = 0.72

# An end-card that starts before the speech ends talks over the payoff.
_END_CARD_MIN_LEAD_S = 0.25


def _ds_parts(design_system):
    """(palette, type_scale, safe, canvas) or None if the system is unusable.

    NOTE ON UNITS, learned the expensive way: `type_scale` is ALREADY IN PIXELS
    (title=100 on a 1920-tall canvas); `type_ratios` holds the fractions
    (title=0.052). Multiplying type_scale by the height again produced
    name_px=192000 — a caption taller than a hundred screens. The design system
    resolves the ratios ONCE, against the canvas it was built for, which is
    exactly so consumers do not each re-derive them and drift.""" 
    if not isinstance(design_system, dict):
        return None
    pal = design_system.get("palette") or {}
    ts = design_system.get("type_scale") or {}
    safe = design_system.get("safe") or {}
    canvas = design_system.get("canvas") or {}
    if not pal.get("accent") or not ts.get("title") or not canvas.get("height"):
        return None
    return pal, ts, safe, canvas


def build_name_plate(design_system, name, role=None, start_s=0.0,
                     hold_s=NAME_PLATE_HOLD_S):
    """Component D. -> spec dict, or None when it must not render.

    None is returned for a missing design system AND for a missing name, because
    a name-plate with no name is a coloured bar that means nothing.
    """
    parts = _ds_parts(design_system)
    if parts is None:
        return None
    name = str(name or "").strip()
    if not name:
        return None
    pal, ts, safe, canvas = parts
    return {
        "kind": "name_plate",
        "name": name,
        # An empty role is dropped rather than rendered blank — the reference
        # lower-third is name-only when there is no role.
        "role": (str(role).strip() or None) if role else None,
        "start_s": round(float(start_s), 3),
        "hold_s": round(float(hold_s), 3),
        "style": {
            # px, straight from the design system — NOT re-multiplied by height.
            "name_px": int(ts["title"]),
            "role_px": int(ts.get("label") or round(ts["title"] * 0.4)),
            "color": pal.get("fg"),
            "accent": pal["accent"],
            "backdrop": pal.get("bg"),
        },
        # Fractional, so a landscape canvas places it correctly instead of
        # inheriting a vertical pixel constant.
        "anchor": {"x_fraction": None, "y_fraction": _NAME_PLATE_Y_FRACTION},
        "safe": {"doctrine": safe.get("doctrine"), "x": safe.get("x"), "y": safe.get("y")},
        "source": "design_system",
    }


def build_end_card(design_system, headline, subline=None, duration_s=None,
                   hold_s=END_CARD_HOLD_S):
    """Component F. -> spec dict, or None when it must not render.

    `duration_s` is the edit's length. When given, the card is placed so it ENDS
    with the edit rather than starting at a guessed offset — an end-card that
    runs past the cut is a black frame with text on it.
    """
    parts = _ds_parts(design_system)
    if parts is None:
        return None
    headline = str(headline or "").strip()
    if not headline:
        return None
    pal, ts, safe, canvas = parts
    hold = round(float(hold_s), 3)
    start = None
    if duration_s is not None:
        try:
            start = round(max(0.0, float(duration_s) - hold - _END_CARD_MIN_LEAD_S), 3)
        except (TypeError, ValueError):
            start = None
    return {
        "kind": "end_card",
        "headline": headline,
        "subline": (str(subline).strip() or None) if subline else None,
        "start_s": start,
        "hold_s": hold,
        "style": {
            # The end card INVERTS: accent becomes the field, and the foreground
            # is whichever of bg/fg the palette already proved contrasts. This is
            # the one moment the brand colour owns the whole frame.
            "background": pal["accent"],
            "headline_px": int(ts.get("display") or ts["title"]),
            "subline_px": int(ts.get("body") or round(ts["title"] * 0.6)),
            "color": pal.get("bg"),
            "rule": pal.get("fg"),
        },
        "safe": {"doctrine": safe.get("doctrine"), "x": safe.get("x"), "y": safe.get("y")},
        "source": "design_system",
    }


def build_brand_specs(design_system, name=None, role=None, headline=None,
                      subline=None, duration_s=None):
    """Both components for one edit. Always a dict; either value may be None.

    Returning a dict with None values rather than omitting keys keeps the
    contract stable for the renderer and for the liveness counter, which needs to
    tell "not built" from "not asked for".
    """
    return {
        "name_plate": build_name_plate(design_system, name, role=role),
        "end_card": build_end_card(design_system, headline, subline=subline,
                                   duration_s=duration_s),
    }
