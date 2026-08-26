#!/usr/bin/env python3
"""THE INVARIANTS LAYER. `[ART_DIRECTION §1.1, §2, §5, §6]`

One implementation of the rules that bind EVERY component, so a component
cannot improvise its own geometry, its own contrast, or its own colours.

WHY THIS FILE EXISTS. The art-direction inventory (2026-08-17) found 34 of 37
motion-graphic files authored by an agent, zero references cited, and zero
commits saying "this looked wrong, here is a better design". The diagnosis was
NOT too many styles — the owner ruled that the variety IS the product. It was
that BOTH layers were missing: no art direction per style, and no invariants in
shared code, so each component improvised.

THE SPLIT (ART_DIRECTION §1.1):

    INVARIANTS      geometry, rhythm, legibility, motion law, palette lock
                    -> here, one implementation, nobody may vary them
    ART DIRECTION   the distinctive look of each style
                    -> per-component, against a named reference, deliberately
                       different

WHAT IS DELIBERATELY *NOT* HERE. Base colour and case were considered as
invariants and moved to the STYLE layer by owner ruling: forcing `#FEFCFD` and
one case rule onto every component would flatten TwoTone and Gadzhi into
near-copies — the rejected consolidation arriving by the back door. They are
replaced by the two rules below, which constrain the same surface without
dictating the look:

    contrast floor      a style may use any colour; it may not use one you
                        cannot read
    palette membership  a style may pair the job's colours however it likes; it
                        may not introduce one the rest of the edit never sees
"""

# ── §2.1 GEOMETRY — measured off golden/lumen-refs, expressed as frame fractions
# so they are resolution-independent and correct on landscape too.
CAP_HEIGHT_PCT = 0.045          # normal word, fraction of FRAME HEIGHT (~58px @1280)
HERO_MULTIPLE = 2.5             # a stated number renders at 2.5x normal
HERO_CAP_HEIGHT_PCT = CAP_HEIGHT_PCT * HERO_MULTIPLE   # ~0.1125, matches the ~11.5% measured
VERTICAL_ANCHOR_PCT = 0.53      # centre-band. The lower-third assumption is RETIRED.
MAX_WORDS_PER_PAGE = 3          # 1-3, never a full sentence

# ── §2.4 LEGIBILITY ──────────────────────────────────────────────────────────
# 4.5:1 is the WCAG AA floor for normal text. Type over arbitrary footage has a
# harder job than type on a web page, so this is a FLOOR and not a target.
MIN_CONTRAST_RATIO = 4.5
# Large text (hero numbers) may use the AA-large floor — it is physically more
# legible at the same ratio.
MIN_CONTRAST_RATIO_LARGE = 3.0
SHADOW_OFFSET_PCT_OF_CAP = 0.02
SHADOW_BLUR_PCT_OF_CAP = 0.04
SHADOW_OPACITY = 0.35

# ── §5 RHYTHM ────────────────────────────────────────────────────────────────
MOTION_DENSITY_PER_S = 3.5      # moving samples/second, counting every motion kind
STILLNESS_CEILING_S = 3.5       # no dead stretch longer than this

# ── §6 BRAND ─────────────────────────────────────────────────────────────────
PALETTE_MAX_COLOURS = 3         # 2-3, derived per job, held across every element
NAME_PLATE_APPEAR_S = 1.0       # within the first ~3s
NAME_PLATE_HOLD_S = 2.75        # 2.5-3s


def _hex_to_rgb(c):
    """'#RRGGBB' or 'RRGGBB' -> (r, g, b) 0-255. None on anything unparseable —
    never a guessed colour, because a wrong colour silently passes a contrast
    check that should have failed."""
    if not isinstance(c, str):
        return None
    s = c.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        return None
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _relative_luminance(rgb):
    """WCAG 2.x relative luminance."""
    out = []
    for v in rgb:
        v = v / 255.0
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    r, g, b = out
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg, bg):
    """WCAG contrast ratio between two colours, 1.0-21.0. None if either is
    unparseable — an UNMEASURED contrast is never reported as a passing one."""
    a, b = _hex_to_rgb(fg), _hex_to_rgb(bg)
    if a is None or b is None:
        return None
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def clears_contrast_floor(fg, bg, large=False):
    """§2.4. Returns (ok, ratio, floor). ok is False when unmeasurable — a
    colour pair we cannot evaluate does not get the benefit of the doubt."""
    floor = MIN_CONTRAST_RATIO_LARGE if large else MIN_CONTRAST_RATIO
    r = contrast_ratio(fg, bg)
    if r is None:
        return False, None, floor
    return (r >= floor), round(r, 2), floor


def palette_colours(design_system):
    """Every colour the job's palette legitimately contains, lowercased."""
    if not isinstance(design_system, dict):
        return set()
    pal = design_system.get("palette")
    if not isinstance(pal, dict):
        return set()
    out = set()
    for v in pal.values():
        if isinstance(v, str) and _hex_to_rgb(v):
            out.add(v.strip().lower())
        elif isinstance(v, (list, tuple)):
            for x in v:
                if isinstance(x, str) and _hex_to_rgb(x):
                    out.add(x.strip().lower())
    return out


def in_palette(colour, design_system, tolerance=0):
    """§6 palette membership. A component using an off-palette colour is a
    defect — it breaks §1's 'one hand' across the edit.

    `tolerance` allows computed tints/shades: max per-channel distance in 0-255.
    0 means exact membership.
    """
    c = _hex_to_rgb(colour)
    if c is None:
        return False
    pal = palette_colours(design_system)
    if not pal:
        return False
    for p in pal:
        q = _hex_to_rgb(p)
        if q is None:
            continue
        if all(abs(c[i] - q[i]) <= tolerance for i in range(3)):
            return True
    return False


def cap_height_px(frame_height, hero=False):
    """§2.1 as pixels for a given canvas. The ONE conversion — a component that
    computes its own type size is exactly what this layer exists to prevent."""
    pct = HERO_CAP_HEIGHT_PCT if hero else CAP_HEIGHT_PCT
    return round(float(frame_height) * pct)


def check_spec(spec, design_system, frame_height=1920):
    """Audit one component spec against the invariants.

    Returns a list of violation strings — EMPTY means it conforms. Deliberately
    returns findings rather than raising: a component that breaks an invariant
    must be visible in the ledger, and the caller decides whether that is a drop
    or a repair. Silence is the one outcome that is not allowed.
    """
    out = []
    if not isinstance(spec, dict):
        return ["spec is not a dict"]
    for key, val in spec.items():
        if not (isinstance(val, str) and val.strip().startswith("#")):
            continue
        if not in_palette(val, design_system, tolerance=0):
            out.append(f"{key}={val} is not a member of the job palette "
                       f"(§6 palette lock: one hand across the edit)")
    fg = spec.get("nameColor") or spec.get("color") or spec.get("textColor")
    bg = spec.get("backdrop") or spec.get("backgroundColor")
    if fg and bg:
        ok, ratio, floor = clears_contrast_floor(fg, bg)
        if not ok:
            out.append(f"contrast {ratio} < {floor} for {fg} on {bg} "
                       f"(§2.4 legibility floor)")
    return out
