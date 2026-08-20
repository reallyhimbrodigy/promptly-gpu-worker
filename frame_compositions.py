#!/usr/bin/env python3
"""THE GENERATION-FREE COMPOSITIONS — specs, built from the design system.

Insert scenes that need NO image model, NO Vertex call, NO quota, NO new
dependency and NO asset pipeline. Two are built on a frame of the USER'S OWN
video; one is pure type.

WHY THIS FAMILY. Measured 2026-08-19: on real footage the planner reaches for
StatCard and Stamp UNPROMPTED — twice on one source, hard enough to hit the
placement wall — while asking for zero generated_scenes even with the directive
on, the premium path live and reference stills in the payload. These are the
component family it is actually asking for, and they GROUND IN SOMETHING IT CAN
SEE, which is the property a generated scene lacks: a word index pointing at a
frame that certainly exists, instead of an invented background/subject/motion
triple for an image model.

They also cannot produce the decline that invalidated four corpora
(`source_shows_it`), because the still IS the source.

═══ SPEC-BUILT, LIKE D AND F — NOT AUTHORED BY THE MODEL ═══════════════════════

`build_brand_specs` is the precedent: the model supplies COPY, the pipeline
supplies COLOUR, TYPE SIZE and SAFE ZONES from the design system. A component
that picks its own colour is a second design system competing with the real one
— right in every cert, wrong on every video (brand_components.py). So the model
asks for a composition and names its content; everything visual is derived here.

THE INVARIANTS (ART_DIRECTION.md), applied once, in this file:

  palette membership   bg/fg/accent come from design_system["palette"] — the
                       deterministic extractor, never a hardcoded brand colour
  contrast floor §2.4  a soft drop shadow (~2% of cap height offset, ~35%
                       opacity, blur ~4% of cap height) OR a contrasting
                       outline — NEVER NEITHER. Emitted here so no component
                       can forget it.
  tilt + overlap §4    5-8 degrees, hard edge, real shadow: a physical object on
                       a surface. "A stack of centred, non-overlapping boxes
                       reads as a slide."
  card entrances §1    CORRECTED 2026-08-20. frame-1-is-final is a CAPTION law
                       (the caption text layer); it was wrongly applied to these
                       cards. REF-2's cards animate in — so each spec names an
                       arrival (ENTRANCE) the renderer eases, velocity-caps and
                       motion-blurs. The RESTING frame is still the §4
                       composition, unchanged.
"""
from typing import Any, Dict, Optional

# §4: a physical print on a surface, never a floating layer.
TILT_DEG = {"EvidenceCard": -6.0, "DeviceMockup": 5.0,
            "EmojiCard": -7.0}
# Entrances — CORRECTED 2026-08-20. frame-1-is-final is a CAPTION law (the
# caption text layer; four passes, the owner's eye). It was wrongly carried onto
# these CARDS, which shipped `entrance: "none"` and popped on with zero motion.
# REF-2's cards animate in, so each names an arrival the renderer eases,
# velocity-caps (MAX_ENTRANCE_STEP 1/6) and motion-blurs. `none` stays static.
ENTRANCE = {"EvidenceCard": "rise", "DeviceMockup": "rise", "EmojiCard": "scale"}
# Cap-height fractions from §2.4, applied to the type size the design system
# hands us rather than to a hardcoded pixel value.
_SHADOW_OFFSET_FRAC = 0.02
_SHADOW_BLUR_FRAC = 0.04
_SHADOW_OPACITY = 0.35


def _palette(design_system):
    p = (design_system or {}).get("palette") or {}
    return (p.get("bg") or "#0E0E12", p.get("fg") or "#FFFFFF",
            p.get("accent") or "#F5A11E")


def _type_px(design_system, key, fallback):
    ts = (design_system or {}).get("type_scale") or {}
    try:
        return int(ts.get(key) or fallback)
    except Exception:
        return fallback


def _legibility(cap_px):
    """§2.4 — the contrast floor, as a spec the renderer cannot omit.

    Returned as NUMBERS, not a CSS string: the renderer composes them, and a
    cert can assert the floor is present without parsing style text.
    """
    return {
        "shadow_offset_px": max(1, round(cap_px * _SHADOW_OFFSET_FRAC)),
        "shadow_blur_px": max(2, round(cap_px * _SHADOW_BLUR_FRAC)),
        "shadow_opacity": _SHADOW_OPACITY,
    }


def _base(kind, design_system, at_seconds, duration_s):
    bg, fg, accent = _palette(design_system)
    cap = _type_px(design_system, "display", 96)
    return {
        "kind": kind,
        "bg": bg, "fg": fg, "accent": accent,
        "cap_px": cap,
        "tilt_deg": TILT_DEG.get(kind, 0.0),
        "legibility": _legibility(cap),
        # SECONDS, derived by the worker from a word index via word_frame. The
        # renderer never sees a word index and never does clock arithmetic —
        # there is one clock in this pipeline and it is not in the renderer.
        "at_seconds": round(float(at_seconds or 0.0), 3),
        "duration_s": round(float(duration_s or 2.0), 3),
        # Spec-driven arrival (see ENTRANCE) — a real, eased, velocity-capped
        # card entrance. frame-1-is-final remains the CAPTION law, not a card one.
        "entrance": ENTRANCE.get(kind, "rise"),
    }


def build_evidence_card(design_system, at_seconds, claim, caption=None,
                        duration_s=2.0) -> Optional[Dict[str, Any]]:
    """A still of the user's own frame, held as evidence for what they just said.

    `claim` is the background type; `caption` overlaps the still in front. Three
    planes with occlusion in both directions, which is what stops it reading as
    a slide.
    """
    if not str(claim or "").strip():
        return None                      # no claim, no card — never fabricate
    s = _base("EvidenceCard", design_system, at_seconds, duration_s)
    s.update(claim=str(claim).strip()[:120],
             caption=(str(caption).strip()[:80] if caption else None),
             still_width_pct=58)
    return s


def build_device_mockup(design_system, at_seconds, label=None,
                        duration_s=2.0) -> Optional[Dict[str, Any]]:
    """The user's own frame inside a drawn phone shell. The shell is DRAWN, never
    an asset: an image would need fetching, versioning and a failure mode."""
    s = _base("DeviceMockup", design_system, at_seconds, duration_s)
    s.update(label=(str(label).strip()[:60] if label else None),
             shell_radius_px=46, still_width_px=430)
    return s



def build_emoji_card(design_system, at_seconds, emoji, words=None,
                     duration_s=2.0) -> Optional[Dict[str, Any]]:
    """REF-2's TOP SECRET folder: an emoji, a tilt, a shadow and two words.

    Noto Color Emoji is ALREADY IN THE IMAGE (the caption stack uses it), so
    this composition adds no font, no asset and no dependency — which is the
    whole reason it belongs in a generation-free set.
    """
    e = str(emoji or "").strip()
    if not e:
        return None
    w = [x for x in (str(words or "").split() if isinstance(words, str)
                     else list(words or []))][:2]
    s = _base("EmojiCard", design_system, at_seconds, duration_s)
    s.update(emoji=e[:8], words=w, emoji_px=int(_type_px(design_system, "display", 96) * 3.2))
    return s


BUILDERS = {
    "EvidenceCard": build_evidence_card,
    "DeviceMockup": build_device_mockup,
    "EmojiCard": build_emoji_card,
}


def build_frame_composition(kind, design_system, at_seconds, props,
                            duration_s=2.0) -> Optional[Dict[str, Any]]:
    """kind + model-supplied CONTENT -> a spec with all visuals derived here.

    Returns None when the content the composition needs is absent — the same
    drop-never-fabricate rule the component contract uses everywhere else.
    """
    fn = BUILDERS.get(kind)
    if fn is None:
        return None
    p = dict(props or {})
    try:
        if kind == "EvidenceCard":
            return fn(design_system, at_seconds, p.get("claim"),
                      caption=p.get("caption"), duration_s=duration_s)
        if kind == "DeviceMockup":
            return fn(design_system, at_seconds, label=p.get("label"),
                      duration_s=duration_s)
        if kind == "EmojiCard":
            return fn(design_system, at_seconds, p.get("emoji"),
                      words=p.get("words"), duration_s=duration_s)
    except Exception:
        return None
    return None
