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
    "Prime", "TypewriterReveal", "Cove", "Lumen", "Pulse", "Quintessence",
    # Batch 2 — 4 net-new styles (both tiers).
    "TwoTone", "CleanCut",
    # Directive #12 promotions (from the ABE archive):
    "Gadzhi",
    # Renderer skips caption rendering entirely when style == "none"
    # (user explicit opt-out in vibe or re-edit). Kept here so the
    # Pydantic Literal accepts the sentinel; the TS-side CaptionStyle
    # Literal omits it because CaptionSpec is only emitted with a
    # real style.
    "none",
})

VALID_TRANSITION_TYPES = frozenset({
    "CardSwipe", "ZoomThrough", "SlideOver", "Stack", "CrossfadeZoom",
    "ShutterFlash", "StepPush", "FilmStrip",
    "DipToBlack",
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
    "LightLeak", "ShutterFlash",
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
    # Job b89287c4 (2026-06-20) emitted editorial_vision text "tight-cut
    # punctuation overlays to drive the pace" — a textbook vision-claims-
    # but-array-empty contradiction that the re-ask should have caught
    # but didn't, because none of the original three phrases substring-
    # matched. The phrases below are how Gemini actually writes overlay
    # commitments in production; without them in this constant, the
    # detector ran no-op on the exact failure case it was built for.
    "tight-cut overlay",
    "tight-cut overlays",
    "tight cut overlay",
    "tight cut overlays",
    "tight-cut punctuation",
)

VALID_ZOOM_TYPES = frozenset({
    "SmoothPush", "SnapReframe", "FocusWindow", "StepZoom", "LetterboxPush",
    "DepthPull",
    # StagedPush — the multi-stage emphasis zoom (2-3 part stepped push-in). A RESERVED
    # high-impact move: a short punchy phrase of 2-3 CONSECUTIVE building emphasis words
    # gets a smooth-fast push completing on each word, then an adaptive release. The
    # emphasis carries 2-3 word_indices (the stage anchors); the pipeline derives stages.
    "StagedPush",
})

VALID_MG_TYPES = frozenset({
    "AnnotationArrow", "ChatThread",
    "Notification", "ProgressBar", "RecordingFrame",
    "StatCard", "StickyNotes",
    "TweetBubble", "InstagramComment", "IMessageBubble", "TikTokComment",
    # Batch 2 — 16 net-new (IconLabel DELETED, Zac ruling 2026-07-11: 'unnecessary and unprofessional in any scenario') motion graphics (both tiers). MGs carry a generic
    # `props` dict, so adding the type here is the whole schema seam: the
    # Pydantic + render Literals derive from this frozenset; render_schemas /
    # PostCutPlan / EditPlan accept the new types automatically.
    "Timeline", "Reticle", "RankedList",
    "PullQuote", "PillCluster", "Stamp", "BarRace", "SectionDivider",
    "EditorialQuote", "StepDivider", "DropBanner", "DropCard", "PillMarquee",
    "TimelineRoadmap", "MouseDrag",
    # ── BRAND COMPONENTS D + F (2026-08-16) [§3.1 PHASE 1.3] ────────────────
    # The name-plate and the end-card: the first Phase 1 components a VIEWER CAN
    # SEE. Registering them here is the whole schema seam — handler's _MG_TYPES
    # and render_schemas.MotionGraphicType both derive from this frozenset, so
    # one edit makes them requestable in every mirror at once.
    #
    # THEY ARE REQUESTED BY COPY, NOT BY NAME. The model fills PostCutPlan
    # .brand_copy (speaker_name / speaker_role / brand_name / handle /
    # brand_subline) and the pipeline builds the specs from the DESIGN SYSTEM —
    # colour, type size and safe zones all derived from the user's own footage.
    # A component that picks its own colour is a second design system competing
    # with the real one: right in every cert, wrong on every video. These names
    # exist here so the RENDERER can dispatch them, which is the link that was
    # missing while everything else was green.
    "NamePlate", "EndCard",
    # ── THE FOUR GENERATION-FREE COMPOSITIONS (2026-08-19) ─────────────────
    # No image model, no Vertex call, no quota, no asset pipeline. Two are built
    # on a frame of the USER'S OWN video; two are pure type. SPEC-BUILT like D+F
    # — the model supplies content, frame_compositions.py derives every visual
    # from the design system, so MG_MAP dispatches ADAPTERS, never the bare
    # components (the NamePlate lesson: a bare component renders an empty card).
    #
    # WHY THIS FAMILY: measured 2026-08-19, the planner reaches for StatCard and
    # Stamp UNPROMPTED on real footage while asking for zero generated_scenes
    # with the directive on and stills in the payload. These ground in something
    # it can SEE — a word index pointing at a frame that certainly exists.
    "EvidenceCard", "DeviceMockup", "EmojiCard",
})

# ── Generated scenes (Phase E · composed premium graphics) ──────────────────
# The enumerated dimensions of a GeneratedScene element (background world,
# entrance motion, easing). Pydantic/TS Literals derive from these the same way
# the component types above do — single source of truth. Registered in Sub-step
# 2 INERT (no recipe emits a GeneratedScene yet).
VALID_GENSCENE_BACKGROUNDS = frozenset({"gradient", "solid", "generated"})
VALID_GENSCENE_ENTRANCES = frozenset({"slide", "scale", "float", "fade", "rise"})
VALID_GENSCENE_EASINGS = frozenset({"spring", "ease", "linear"})
