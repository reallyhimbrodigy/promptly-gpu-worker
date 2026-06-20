"""Canonical type vocabularies for the Promptly pipeline.

Single source of truth for every component-type taxonomy used at the
Python validation layer:

  • VALID_CAPTION_STYLES     — caption components (12 + "none" sentinel)
  • VALID_TRANSITION_TYPES   — transition components (handle-required, CUT BOUNDARIES)
  • VALID_TIGHT_CUT_OVERLAYS — overlay-on-top-of-hard-cut decorations
                               (TIGHT BOUNDARIES, no handle, no time inserted —
                               render as a decoration layer over an unmodified
                               hard cut at the cut frame, 180ms window)
  • VALID_ZOOM_TYPES         — zoom components
  • VALID_MG_TYPES           — motion-graphic components

Both handler.py and render_schemas.py import from this module — Pydantic
Literals in each derive via `Literal[tuple(sorted(VALID_*))]` so adding
a new component type means editing ONE set here, not coordinating four
duplicates across two files (the failure mode that surfaced 2026-06-14
during the DipToBlack rollout — three production crashes from drift
between hardcoded copies).

Leaf module by design: imports NOTHING from the project. Both handler.py
(which imports render_schemas.py) and render_schemas.py can import here
without circulating.

Frozensets, not sets — these are vocabularies, not mutable collections.
"""

VALID_CAPTION_STYLES = frozenset({
    "PaperII",
    "Prime", "TypewriterReveal", "CinematicLetterpress", "Cove",
    "EditorialPop", "Illuminate", "Lumen",
    "Passage", "Pulse", "Quintessence", "Serif",
    # Renderer skips caption rendering entirely when style == "none"
    # (user explicit opt-out in vibe or re-edit). Kept here so the
    # Pydantic Literal accepts the sentinel; the TS-side CaptionStyle
    # Literal omits it because CaptionSpec is only emitted with a
    # real style.
    "none",
})

VALID_TRANSITION_TYPES = frozenset({
    "CardSwipe", "ZoomThrough", "SlideOver", "Stack", "CrossfadeZoom",
    "ShutterFlash", "StepPush", "NewspaperWipe", "FilmStrip",
    "SceneTitle", "DipToBlack",
})

# Overlay-on-top-of-hard-cut decorations. Render path is DISTINCT from
# transitions: no handle frames consumed, no clip-A/clip-B blending, no
# time inserted into the timeline. The decoration sits ON TOP of an
# unmodified hard cut for an 11-frame window (180ms at 60fps) centered
# on the cut. Names overlap with the transition registry intentionally
# (LightLeak, ShutterFlash both exist as full handle-required transitions
# too) — the dispatch is by FIELD (`_tight_cut_overlay` vs
# `transition_out`) and by BOUNDARY TYPE (TIGHT vs CUT), not by name.
# Adding a third overlay means editing this set only.
VALID_TIGHT_CUT_OVERLAYS = frozenset({
    "LightLeak", "ShutterFlash", "NewspaperWipe", "SceneTitle",
})

# Mechanism / effect phrases that count as a tight-cut-overlay COMMITMENT in
# editorial_vision (separate from naming a specific TYPE — those are matched
# via VALID_TIGHT_CUT_OVERLAYS lowercased substring). Single source of truth
# for two consumers:
#   1. The HOW TO PLACE TIGHT-CUT OVERLAYS prompt section embeds these as the
#      coherence-rule's EFFECT/MECHANISM examples — Gemini sees them as the
#      patterns its vision text should/should-not include depending on whether
#      it intends to emit an overlay.
#   2. The recipe-eval reconciliation pass (_reconcile_tight_cut_overlays in
#      handler.py) substring-matches vision text against these to detect the
#      "vision claims an overlay but the array is empty" contradiction and
#      trigger a focused re-ask.
# Both consumers MUST read from this constant — hand-maintaining parallel
# phrase lists would drift the detector away from what the prompt taught
# Gemini to recognize, defeating the re-ask's purpose.
#
# Tuple (not frozenset) so the order matches what gets rendered into the
# prompt prose. Sorted iteration would be fine for detection but would
# cosmetically shift the coherence rule's example order on every refactor.
TIGHT_CUT_OVERLAY_MECHANISM_PHRASES = (
    "decorate tight cuts",
    "punctuate the hard cuts",
    "kinetic decoration at the cuts",
)

VALID_ZOOM_TYPES = frozenset({
    "SmoothPush", "SnapReframe", "FocusWindow", "StepZoom", "LetterboxPush",
    "StageZoom", "DepthPull",
})

VALID_MG_TYPES = frozenset({
    "AnnotationArrow", "ChatThread",
    "Notification", "ProgressBar", "QuoteCard", "RecordingFrame",
    "StatCard", "StickyNotes", "Toggle",
    "TweetBubble", "InstagramComment", "IMessageBubble", "TikTokComment",
})
