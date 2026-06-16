"""Pydantic schemas for Remotion render inputs.

Single source of truth for the SHAPES that flow from Python (handler.py)
to Remotion (src/remotion/src/types.ts). Mirrors `types.ts` field-for-field.
Validated at JSON-emit time so any shape mismatch raises a clear Python
error BEFORE Remotion is invoked — turning the entire class of "Python
emits something Remotion's React tree can't render" bugs (today's
/tmp absolute path through staticFile, the empty notifications array
through Notification.slice, etc) into immediate boundary failures
instead of opaque renderer crashes.

When `types.ts` changes, these models change with it. The smoke test
(scripts/smoke.sh) renders against the actual bundled types, so any
divergence between this file and types.ts surfaces at smoke time.

Naming: fields use the same camelCase keys Remotion consumes. Python's
attribute access is camelCase too — uglier than snake_case but avoids
alias plumbing and makes the JSON shape obvious from the Python code.
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from type_registries import (
    VALID_CAPTION_STYLES,
    VALID_MG_TYPES,
    VALID_TIGHT_CUT_OVERLAYS,
    VALID_TRANSITION_TYPES,
    VALID_ZOOM_TYPES,
)

# ── Vocabulary ──────────────────────────────────────────────────────────────
# Component-type Literals derive from the canonical frozensets in
# type_registries.py — single source of truth for both handler.py (Python
# validation) and this module (render-input validation). Adding a new
# component type means editing type_registries only; this Literal updates
# automatically and Pydantic accepts the same set both sides validate.
#
# `Literal[tuple(sorted(...))]` is the Python 3.10+ derivation pattern:
# Literal's subscript collapses a tuple of strings into the equivalent
# `Literal["a", "b", ...]` form. Verified at import — Pydantic v2
# accepts it identically to a hand-written Literal.
MGAnchor = Literal[
    "center", "top", "bottom", "left", "right",
    "top-left", "top-right", "bottom-left", "bottom-right",
]

ZoomType = Literal[tuple(sorted(VALID_ZOOM_TYPES))]

TransitionType = Literal[tuple(sorted(VALID_TRANSITION_TYPES))]

TightCutOverlayType = Literal[tuple(sorted(VALID_TIGHT_CUT_OVERLAYS))]

# Render-input never carries the renderer "none" sentinel — CaptionSpec is
# only emitted when there's a real style — so subtract it before deriving.
CaptionStyle = Literal[tuple(sorted(VALID_CAPTION_STYLES - {"none"}))]

MotionGraphicType = Literal[tuple(sorted(VALID_MG_TYPES))]

CaptionPosition = Literal["top", "center", "bottom"]

# Model base — extra="forbid" means any field Python emits that Remotion
# doesn't know about is a validation error (catches typos and stale fields).
class _RemotionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Clips & transitions ─────────────────────────────────────────────────────
class ZoomEventSpec(_RemotionModel):
    startMs: int
    durationMs: int
    scale: Optional[float] = None
    originX: Optional[float] = None
    originY: Optional[float] = None


class ZoomEffectSpec(_RemotionModel):
    type: ZoomType
    events: List[ZoomEventSpec] = Field(default_factory=list)
    firstStage: Optional[float] = None
    secondStage: Optional[float] = None
    windowScale: Optional[float] = None
    borderWidth: Optional[float] = None
    borderColor: Optional[str] = None
    bgScale: Optional[float] = None
    edgeBlur: Optional[float] = None
    frameLines: Optional[bool] = None
    maxBarHeight: Optional[float] = None


class ClipSpec(_RemotionModel):
    id: str
    startFromFrames: int
    playbackRate: float
    durationInFrames: int
    zoomEffect: Optional[ZoomEffectSpec] = None
    # Optional pre-extracted source URL for Remotion-rendered zoom clips.
    # The ABE zoom components play their `src` from frame 0 with no seek
    # or playback-rate prop, so the pipeline materializes a frame-accurate
    # per-clip mp4 (source[startFromFrames..+durationInFrames*playbackRate])
    # and passes its staticFile() URL here. When set, the Remotion clip
    # renderer uses this src instead of the top-level sourceUrl and ignores
    # startFromFrames/playbackRate (the file is already trimmed and speed-
    # adjusted). When None, the clip is rendered by FFmpeg (no zoom path).
    src: Optional[str] = None


class TransitionSpec(_RemotionModel):
    afterClipIndex: int
    type: TransitionType
    durationInFrames: int
    clipAStartFromFrames: int
    clipBStartFromFrames: int
    clipAPlaybackRate: float
    clipBPlaybackRate: float
    direction: Optional[Literal["left", "right", "up", "down"]] = None
    palette: Optional[Literal["warm", "gold", "cool", "magenta"]] = None
    intensity: Optional[float] = None
    separatorShadow: Optional[bool] = None
    title: Optional[str] = None
    label: Optional[str] = None
    variant: Optional[Literal["full", "half-top", "half-bottom"]] = None
    theme: Optional[Literal["dark", "light"]] = None
    accentColor: Optional[str] = None
    titleColor: Optional[str] = None
    labelColor: Optional[str] = None
    showDivider: Optional[bool] = None
    assetPath: Optional[str] = None
    frameBackground: Optional[str] = None
    caption: Optional[str] = None
    showBookmark: Optional[bool] = None
    showGrid: Optional[bool] = None
    advanceFrames: Optional[int] = None
    flashColor: Optional[str] = None


# Tight-cut overlay — overlay-on-top-of-hard-cut decoration. atFrame is
# the OUTPUT frame the hard cut sits on. The overlay window is centered
# on that frame (atFrame - durationInFrames/2 → atFrame + durationInFrames/2).
# Outside the window the React component returns null — no time inserted,
# no audio touched, no clip-A/clip-B blending. The underlying composite
# (FFmpeg base + alpha overlay) plays its real frames including the hard
# cut; this overlay sits ABOVE the alpha-overlay's transparent canvas
# and only paints during its window.
#
# durationInFrames is PER-TYPE, set by the Python emit:
#   LightLeak / ShutterFlash / NewspaperWipe → 11 frames (180ms @ 60fps)
#   SceneTitle                               → 72 frames (1200ms @ 60fps)
# SceneTitle's typographic panel needs the longer hold so the title text
# is readable through the 0.32–0.68 progress hold window.
#
# title + label are SceneTitle-only — the typographic panel needs at minimum
# the title string (one to three uppercase words like "ACT TWO" or "THE PIVOT").
# label is the optional kicker above the divider ("CHAPTER", "PART II", etc.).
# Both fields are ignored when type is anything other than SceneTitle.
# Validated at the application layer (handler.py): SceneTitle without a title
# is rejected; the other three reject title/label entirely.
class TightCutOverlaySpec(_RemotionModel):
    atFrame: int
    type: TightCutOverlayType
    durationInFrames: int
    title: Optional[str] = None
    label: Optional[str] = None


# ── B-roll ─────────────────────────────────────────────────────────────────
class BrollSpec(_RemotionModel):
    src: str
    fromFrame: int
    durationInFrames: int
    seekFromSeconds: float
    brollFps: float
    playbackRate: float


# ── Captions ───────────────────────────────────────────────────────────────
class TikTokToken(_RemotionModel):
    text: str
    fromMs: int
    toMs: int


class TikTokPage(_RemotionModel):
    text: str
    startMs: int
    durationMs: int
    tokens: List[TikTokToken]


class CaptionPositionSegment(_RemotionModel):
    fromFrame: int
    toFrame: int
    position: CaptionPosition


class CaptionSpec(_RemotionModel):
    style: CaptionStyle
    pages: List[TikTokPage]
    keywords: List[str]
    positionSegments: List[CaptionPositionSegment]
    extraProps: Optional[Dict[str, Any]] = None


# ── Motion graphics ─────────────────────────────────────────────────────────
class MotionGraphicSpec(_RemotionModel):
    type: MotionGraphicType
    fromFrame: int
    durationInFrames: int
    props: Dict[str, Any] = Field(default_factory=dict)


# ── Text overlays (discriminated by variant) ────────────────────────────────
class _TextOverlayBase(_RemotionModel):
    fromFrame: int
    durationInFrames: int


class _StickyNoteEntry(_RemotionModel):
    text: str
    color: str
    rotation: float


class StickyNoteOverlay(_TextOverlayBase):
    variant: Literal["sticky_note"]
    notes: List[_StickyNoteEntry]


class QuoteCardOverlay(_TextOverlayBase):
    variant: Literal["quote_card"]
    quote: str
    attribution: str


class CaptionMatchOverlay(_TextOverlayBase):
    variant: Literal["caption_match"]
    text: str
    position: CaptionPosition


TextOverlaySpec = Annotated[
    Union[StickyNoteOverlay, QuoteCardOverlay, CaptionMatchOverlay],
    Field(discriminator="variant"),
]


# ── Composition inputs ──────────────────────────────────────────────────────
OutroKind = Literal["none", "fade_black", "fade_white"]


class PromptlyRenderInput(_RemotionModel):
    sourceUrl: str
    fps: float
    width: int
    height: int
    totalDurationInFrames: int
    clips: List[ClipSpec]
    transitions: List[TransitionSpec]
    broll: List[BrollSpec]
    caption: CaptionSpec
    textOverlays: List[TextOverlaySpec]
    motionGraphics: List[MotionGraphicSpec]
    # Tight-cut overlays sit on TIGHT BOUNDARIES (hard cuts with no handle
    # room). The PromptlyOverlay React tree iterates this list and renders
    # the named overlay centered on each atFrame. Empty by default — the
    # field is strictly additive, so an empty array means no behavior
    # change vs the pre-overlay pipeline.
    tightCutOverlays: List[TightCutOverlaySpec] = Field(default_factory=list)
    outro: Optional[OutroKind] = None


# ── Micro-segments (discriminated by type) ─────────────────────────────────
class MicroSegmentSpec(_RemotionModel):
    type: Literal["transition", "zoom_clip"]
    outputStartFrame: int
    durationInFrames: int
    transition: Optional[TransitionSpec] = None
    clip: Optional[ClipSpec] = None


class PromptlyMicroSegmentsInput(_RemotionModel):
    sourceUrl: str
    fps: float
    width: int
    height: int
    totalDurationInFrames: int
    segments: List[MicroSegmentSpec]


