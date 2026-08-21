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


# ── MECHANICAL GAP-FILL — free, instant, claim-anchored ──────────────────────
# MEASURED 2026-08-20: 13 of 24 unbiased real sources (54%) have ZERO scdet shot
# changes. For over half of traffic the picture NEVER CHANGES ON ITS OWN, so
# every visual change has to be manufactured — and recipe_eval already reports
# the consequence, e.g. "FAIL [dead-zone] 11.6s with no visual event ... the
# swipe happens here", logged and ignored on every job.
#
# WHY MECHANICAL AND NOT A SECOND MODEL CALL. A repair re-ask is a second Gemini
# call on every job that trips, and on a 54%-single-shot population that is most
# of them — roughly the price of the planning call again, against a $0.10/job
# and 90s law. This runs AFTER the plan, in Python, and costs $0.
#
# THE FOUR CONSTRAINTS, each enforced below rather than intended:
#   FREE      — the image is a frame of the user's own video. No fetch, no
#               generation, no quota, no network.
#   INSTANT   — no I/O of any kind on this path.
#   ANCHORED  — the claim is the WORDS THE SPEAKER IS SAYING in that gap,
#               verbatim from the transcript. Not summarised, not invented.
#   NOT THIN  — the still IS the source, so it cannot be irrelevant to the
#               video the way a stock clip can.
#
# EVIDENCECARD ONLY, AND THE OTHER TWO ARE REFUSED ON PURPOSE. DeviceMockup
# needs a screen to be on camera and EmojiCard needs an emoji that means
# something — neither is derivable from a transcript, so filling with them would
# be the pipeline asserting something it cannot check. That is the thin-b-roll
# failure wearing a different hat.
_GAPFILL_MIN_GAP_S = 5.0        # the 5-7s cadence floor; below this, no hole
_GAPFILL_DURATION_S = 1.6       # long enough to read, short enough to not stall
_GAPFILL_OPENING_GUARD_S = 3.0  # the opening belongs to the speaker (b-roll law)
_GAPFILL_MAX = 6                # never carpet a video with cards
_GAPFILL_MIN_CLAIM_WORDS = 3    # fewer words than this is not a claim

# ── THE ENGLISH-ONLY LIMIT ON MECHANICAL B-ROLL FILL ────────────────────────
# A CONSTRAINT ON THE CAPABILITY, not a detail. Filling a gap with a CARD is
# language-agnostic: the still is the user's own frame and the claim is their
# own words, verbatim, in any script. Filling a gap with B-ROLL is not — it
# needs a stock-library QUERY, and the library is English.
#
# On cada6a1b (Arabic) a mechanical keyword is unbuildable: copying the words
# into a Pexels query returns nothing, and inventing an English phrase from
# Arabic speech requires a MODEL CALL — which breaks both constraints this
# feature is built on ($0/instant, no new model) and is precisely the thin-b-roll
# assertion the honest-fallback path exists to prevent.
#
# THE MODEL CAN do it (it once emitted "luxury modern apartment living room
# interior dubai skyline view daylight 4k" from this same Arabic speech). The
# MECHANICAL path cannot. So:
#
#   ANY SCRIPT      -> cards. Always available, always honest.
#   LATIN/ENGLISH   -> cards + b-roll may mix.
#   NON-LATIN       -> cards ONLY, and the b-roll half of any mix silently
#                      does not exist. Never report a mixed-arm result as
#                      applying to non-Latin traffic.
#
# Measured population note: of 179 usable transcripts, roughly HALF were
# non-Latin (25/25 in the first 50 sampled). So this limit is not an edge case —
# it decides what the mix can be for about half of real traffic.
_GAPFILL_BROLL_MIN_LATIN = 0.8


def _is_latin_transcript(words):
    """Can a stock-library query be built from these words at all?"""
    txt = " ".join(str(w.get("word") or "") for w in (words or [])
                   if isinstance(w, dict))
    tot = sum(ch.isalpha() for ch in txt)
    if not tot:
        return False
    latin = sum(ch.isascii() and ch.isalpha() for ch in txt)
    return (latin / tot) >= _GAPFILL_BROLL_MIN_LATIN


_GAPFILL_STOP = frozenset("""
a an the and or but so because if then than that this these those there here
i me my we our you your he she it they them his her its their of to in on at
for with from into onto by about over under up down off out through is are was
were be been being am do does did done doing has have had having will would can
could may might shall should must just really very quite not no as too also
""".split())


def _broll_keyword_from_words(words, i0, i1):
    """A stock query from the speaker's own CONTENT words. Returns None when
    too few survive — an empty window beats a lying cutaway."""
    toks = []
    for j in range(i0, min(i1 + 1, len(words))):
        w = "".join(ch for ch in str(words[j].get("word") or "").lower()
                    if ch.isalnum() or ch == "'")
        if w and w not in _GAPFILL_STOP and len(w) > 2:
            toks.append(w)
    seen, out = set(), []
    for t in toks:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return " ".join(out[:8]) if len(out) >= 3 else None


def plan_gap_fills(plan, words, min_gap_s=None, max_fills=None, mode="cards"):
    """Return [{start_word_index, end_word_index, at_seconds, claim, gap}] —
    EvidenceCards that close the plan's own visual dead gaps.

    Decides NOTHING about rendering; the caller builds the specs and ledgers.
    Returns a parallel `declines` list so a gap left open is attributable.
    """
    import recipe_eval as _re
    min_gap_s = _GAPFILL_MIN_GAP_S if min_gap_s is None else min_gap_s
    max_fills = _GAPFILL_MAX if max_fills is None else max_fills
    fills, declines = [], []
    if not words:
        return fills, declines

    # ITERATIVE, BECAUSE ONE FILL DOES NOT CLOSE A GAP — IT SPLITS IT.
    # The first cut of this filled each gap's midpoint ONCE and returned: a
    # 31.9s hole got a single card and stayed a 15.9s hole on both sides, which
    # closes nothing and would still fail the dead-zone bar. Each placed card
    # becomes an event, so the gaps are RECOMPUTED and the largest remaining one
    # is filled next — the loop targets max_dead_gap_s directly and stops when
    # the cadence is met or the cap binds.
    _synthetic = {"motion_graphics": list(plan.get("motion_graphics") or []),
                  "text_overlays": list(plan.get("text_overlays") or []),
                  "broll_clips": list(plan.get("broll_clips") or []),
                  "transitions": list(plan.get("transitions") or []),
                  "emphasis_moments": list(plan.get("emphasis_moments") or [])}
    _seen_anchor = set()
    while len(fills) < max_fills:
        gaps = _re.visual_gaps(_synthetic, words, min_gap_s)
        if not gaps:
            break
        g0, g1, glen = max(gaps, key=lambda g: g[2])   # always the worst one
        lo = max(g0, _GAPFILL_OPENING_GUARD_S)
        if g1 - lo < min_gap_s * 0.5:
            declines.append({"gap": (g0, g1), "reason": "inside_opening_guard"})
            break
        mid = lo + (g1 - lo) / 2.0
        idx = [i for i, w in enumerate(words)
               if float(w.get("start") or 0.0) >= mid]
        if not idx or idx[0] in _seen_anchor:
            declines.append({"gap": (g0, g1), "reason": "no_word_at_anchor"})
            break
        i0 = idx[0]
        i1 = min(len(words) - 1, i0 + 7)
        claim = " ".join(str(words[j].get("word") or "")
                         for j in range(i0, i1 + 1)).strip()
        if len(claim.split()) < _GAPFILL_MIN_CLAIM_WORDS:
            declines.append({"gap": (g0, g1), "reason": "no_claim_text"})
            break
        _seen_anchor.add(i0)
        # MIXED MODE: alternate b-roll / card across gaps. B-roll is MOTION —
        # a held card cannot raise frame-to-frame change, which is the gap the
        # cards-only arm could not close. The language guard is enforced here,
        # not assumed: on a non-Latin transcript there is no honest query, so
        # every gap falls back to a card and the arm is cards-only by
        # construction (see _GAPFILL_BROLL_MIN_LATIN).
        _kind = "card"
        if mode == "mixed" and (len(fills) % 2 == 0) and _is_latin_transcript(words):
            _kw = _broll_keyword_from_words(words, i0, i1)
            if _kw:
                _kind = "broll"
                fills.append({
                    "kind": "broll", "keyword": _kw,
                    "start_word_index": i0, "end_word_index": i1,
                    "at_seconds": round(float(words[i0].get("start") or mid), 3),
                    "gap_s": glen,
                })
                _synthetic["broll_clips"].append({"start_word_index": i0})
                continue
            declines.append({"gap": (g0, g1), "reason": "no_honest_broll_query"})
        fills.append({
            "kind": "card",
            "start_word_index": i0,
            "end_word_index": i1,
            "at_seconds": round(float(words[i0].get("start") or mid), 3),
            "claim": claim,
            "gap_s": glen,
        })
        # the card is now an event — the next iteration sees a smaller hole
        _synthetic["motion_graphics"].append({"start_word_index": i0})
    else:
        # loop exited on the cap, not on "no gaps left" — say so, per the
        # no-silent-caps rule.
        _left = _re.visual_gaps(_synthetic, words, min_gap_s)
        if _left:
            declines.append({"gap": (_left[0][0], _left[0][1]),
                             "reason": f"max_fills_reached ({max_fills}); "
                                       f"{len(_left)} gap(s) left open"})
    return fills, declines
