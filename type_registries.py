"""Canonical type vocabularies for the Promptly pipeline.

Single source of truth for every component-type taxonomy used at the
Python validation layer:

  • VALID_CAPTION_STYLES   — caption components (13 + "none" sentinel)
  • VALID_TRANSITION_TYPES — transition components
  • VALID_ZOOM_TYPES       — zoom components
  • VALID_MG_TYPES         — motion-graphic components

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
    "MagazineCutout", "Passage", "Pulse", "Quintessence", "Serif",
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
