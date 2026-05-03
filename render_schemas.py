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

# ── Vocabulary ──────────────────────────────────────────────────────────────
MGAnchor = Literal[
    "center", "top", "bottom", "left", "right",
    "top-left", "top-right", "bottom-left", "bottom-right",
]

ZoomType = Literal[
    "SmoothPush", "SnapReframe", "FocusWindow", "StepZoom",
    "LetterboxPush", "StageZoom", "DepthPull",
]

TransitionType = Literal[
    "CardSwipe", "ZoomThrough", "SlideOver", "Stack", "CrossfadeZoom",
    "ShutterFlash", "LightLeak", "StepPush", "NewspaperWipe", "FilmStrip",
    "SceneTitle",
]

CaptionStyle = Literal[
    "PaperII", "Prime", "TypewriterReveal", "CinematicLetterpress", "Cove",
    "EditorialPop", "Illuminate", "Lumen", "MagazineCutout", "Passage",
    "Pulse", "Quintessence", "Serif",
    "GlitchHighlight", "NegativeFlash", "Prism",
]

MotionGraphicType = Literal[
    "AnnotationArrow", "ChatThread", "Notification", "ProgressBar",
    "QuoteCard", "RecordingFrame", "StatCard", "StickyNotes", "Toggle",
    "TornPaper", "TweetBubble", "InstagramComment", "IMessageBubble",
    "TikTokComment",
]

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


class TornPaperOverlay(_TextOverlayBase):
    variant: Literal["torn_paper"]
    topText: str
    bottomText: str


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
    Union[TornPaperOverlay, StickyNoteOverlay, QuoteCardOverlay, CaptionMatchOverlay],
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


# ── Blend captions only (second-pass composition) ───────────────────────────
class PromptlyBlendCaptionsOnlyInput(_RemotionModel):
    videoUrl: str
    fps: float
    width: int
    height: int
    totalDurationInFrames: int
    caption: CaptionSpec
    captionMatchOverlays: List[CaptionMatchOverlay]
    # Optional: absolute composition frame at which videoUrl frame 0 plays.
    # Used by the pipelined chunked-blend path so each chunk can read its
    # corresponding composite chunk (chunk-local video) instead of the
    # concat'd silent intermediate. Defaults to 0 (single-pass / un-pipelined).
    videoStartFrame: Optional[int] = None
