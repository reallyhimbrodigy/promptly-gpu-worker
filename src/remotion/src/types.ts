/**
 * Production render input — the single shape Python emits and the
 * <PromptlyRender> composition consumes.
 *
 * Times are FRAMES unless named *Ms* or *Seconds*. Everything is pre-resolved
 * on the Python side from canonical time maps and the pre-computed face
 * trajectory; Remotion does not compute timing or placement math — it only
 * renders exactly what the spec says.
 */

// ── MG anchor vocabulary (matches the pack's MGAnchor type) ──────────────────
// Python maps its safe-zone anchors (upper_third_safe, center, lower_third_safe,
// left_safe, right_safe) into this vocabulary before emitting the spec, and
// merges the mapped value into `props.anchor`. Face-relative anchoring is not
// supported by the motion-graphics pack — each component uses its own
// canvas-scale resolveMGPosition.
export type MGAnchor =
  | "center"
  | "top"
  | "bottom"
  | "left"
  | "right"
  | "top-left"
  | "top-right"
  | "bottom-left"
  | "bottom-right";

// ── Clip and transition shapes ───────────────────────────────────────────────
export interface ClipSpec {
  id: string;
  startFromFrames: number;
  playbackRate: number;
  durationInFrames: number;
  zoomEffect?: ZoomEffectSpec;
}

export interface ZoomEffectSpec {
  type: ZoomType;
  events: ZoomEventSpec[];
  firstStage?: number;
  secondStage?: number;
  windowScale?: number;
  borderWidth?: number;
  borderColor?: string;
  bgScale?: number;
  edgeBlur?: number;
  frameLines?: boolean;
  maxBarHeight?: number;
}

export interface ZoomEventSpec {
  startMs: number;
  durationMs: number;
  scale?: number;
  originX?: number;
  originY?: number;
}

export type ZoomType =
  | "SmoothPush"
  | "SnapReframe"
  | "FocusWindow"
  | "StepZoom"
  | "LetterboxPush"
  | "StageZoom"
  | "DepthPull";

export interface TransitionSpec {
  afterClipIndex: number;
  type: TransitionType;
  durationInFrames: number;
  clipAStartFromFrames: number;
  clipBStartFromFrames: number;
  clipAPlaybackRate: number;
  clipBPlaybackRate: number;
  direction?: "left" | "right" | "up" | "down";
  palette?: "warm" | "gold" | "cool" | "magenta";
  intensity?: number;
  separatorShadow?: boolean;
  title?: string;
  label?: string;
  variant?: "full" | "half-top" | "half-bottom";
  theme?: "dark" | "light";
  accentColor?: string;
  titleColor?: string;
  labelColor?: string;
  showDivider?: boolean;
  assetPath?: string;
  frameBackground?: string;
  caption?: string;
  showBookmark?: boolean;
  showGrid?: boolean;
  advanceFrames?: number;
  flashColor?: string;
}

export type TransitionType =
  | "CardSwipe"
  | "ZoomThrough"
  | "SlideOver"
  | "Stack"
  | "CrossfadeZoom"
  | "ShutterFlash"
  | "LightLeak"
  | "StepPush"
  | "NewspaperWipe"
  | "FilmStrip"
  | "SceneTitle";

// ── B-roll cutaway ───────────────────────────────────────────────────────────
// Rendered by Remotion's BrollLayer inside PromptlyOverlay (alpha layer)
// as a split-screen inset that slides up from below to occupy the bottom
// half of the canvas. `src` is the staged basename in the bundle public
// dir (handler.py _stage_file). `seekFromSeconds` is the canonical seek
// field — converted to OffthreadVideo's `startFrom` (frames) by
// BrollLayer via Math.round(seekFromSeconds * fps). `brollFps` is no
// longer used (OffthreadVideo handles fps mismatch automatically) but
// stays in the schema for parity with persistence + observability.
export interface BrollSpec {
  src: string;
  fromFrame: number;
  durationInFrames: number;
  seekFromSeconds: number;
  brollFps: number;
  playbackRate: number;
}

// ── Captions ─────────────────────────────────────────────────────────────────
export interface TikTokTokenLike {
  text: string;
  fromMs: number;
  toMs: number;
}

export interface TikTokPageLike {
  text: string;
  startMs: number;
  durationMs: number;
  tokens: TikTokTokenLike[];
}

export type CaptionStyle =
  | "PaperII"
  | "Prime"
  | "TypewriterReveal"
  | "CinematicLetterpress"
  | "Cove"
  | "EditorialPop"
  | "Illuminate"
  | "Lumen"
  | "MagazineCutout"
  | "Passage"
  | "Pulse"
  | "Quintessence"
  | "Serif"
  | "GlitchHighlight"
  | "NegativeFlash"
  | "Prism";

export interface CaptionPositionSegment {
  fromFrame: number;
  toFrame: number;
  position: "top" | "center" | "bottom";
}

export interface CaptionSpec {
  style: CaptionStyle;
  pages: TikTokPageLike[];
  keywords: string[];
  /** Per-segment position. Covers the full composition, no gaps. */
  positionSegments: CaptionPositionSegment[];
  extraProps?: Record<string, unknown>;
}

// ── Motion graphics ──────────────────────────────────────────────────────────
export type MotionGraphicType =
  | "AnnotationArrow"
  | "ChatThread"
  | "Notification"
  | "ProgressBar"
  | "QuoteCard"
  | "RecordingFrame"
  | "StatCard"
  | "StickyNotes"
  | "Toggle"
  | "TornPaper"
  | "TweetBubble"
  | "InstagramComment"
  | "IMessageBubble"
  | "TikTokComment";

export interface MotionGraphicSpec {
  type: MotionGraphicType;
  fromFrame: number;
  durationInFrames: number;
  /** Props forwarded to the MG component. `props.anchor` (MGAnchor) is set by
   * Python; the component's resolveMGPosition places the content at that
   * flex-aligned corner of the 1080×1920 canvas. */
  props: Record<string, unknown>;
}

// ── Text overlays (discriminated by variant) ─────────────────────────────────
export type TextOverlayVariant =
  | "torn_paper"
  | "sticky_note"
  | "quote_card"
  | "caption_match";

interface TextOverlayBase {
  fromFrame: number;
  durationInFrames: number;
}

export interface TornPaperOverlay extends TextOverlayBase {
  variant: "torn_paper";
  topText: string;
  bottomText: string;
}

export interface StickyNoteOverlay extends TextOverlayBase {
  variant: "sticky_note";
  notes: Array<{ text: string; color: string; rotation: number }>;
}

export interface QuoteCardOverlay extends TextOverlayBase {
  variant: "quote_card";
  quote: string;
  attribution: string;
}

export interface CaptionMatchOverlay extends TextOverlayBase {
  variant: "caption_match";
  text: string;
  position: "top" | "center" | "bottom";
}

export type TextOverlaySpec =
  | TornPaperOverlay
  | StickyNoteOverlay
  | QuoteCardOverlay
  | CaptionMatchOverlay;

// ── Top-level composition input ──────────────────────────────────────────────
export interface PromptlyRenderInput {
  sourceUrl: string;
  fps: number;
  width: number;
  height: number;
  totalDurationInFrames: number;

  clips: ClipSpec[];
  transitions: TransitionSpec[];
  broll: BrollSpec[];
  caption: CaptionSpec;
  textOverlays: TextOverlaySpec[];
  motionGraphics: MotionGraphicSpec[];
  outro?: "none" | "fade_black" | "fade_white";
}

export interface PromptlyRenderProps {
  input: PromptlyRenderInput;
}

// ── PromptlyMicroSegments — batched Remotion-only video segments ─────────────
// Renders only the windows that can't be replicated faithfully in FFmpeg
// (transitions + composite zoom effects). Each segment is placed back-to-back
// in the composition timeline; Python knows the boundaries from outputStartFrame
// + durationInFrames and trims the segments back out in the final ffmpeg
// composite step. Black background, h264 (no alpha).
export interface MicroSegmentSpec {
  /** "transition" → render TransitionRenderer with the given transition spec.
   *  "zoom_clip"  → render ClipRenderer with the given clip spec (clip.zoomEffect
   *                 is what triggered Remotion-rendering this clip — typically
   *                 FocusWindow/LetterboxPush/DepthPull). */
  type: "transition" | "zoom_clip";
  outputStartFrame: number;
  durationInFrames: number;
  /** Set when type === "transition". */
  transition?: TransitionSpec;
  /** Set when type === "zoom_clip". */
  clip?: ClipSpec;
}

export interface PromptlyMicroSegmentsInput {
  sourceUrl: string;
  fps: number;
  width: number;
  height: number;
  /** Sum of all segment durations. */
  totalDurationInFrames: number;
  segments: MicroSegmentSpec[];
}

export interface PromptlyMicroSegmentsProps {
  input: PromptlyMicroSegmentsInput;
}

// ── PromptlyBlendCaptionsOnly — captions on top of finished video ────────────
// Used ONLY for caption styles that rely on CSS mixBlendMode (GlitchHighlight,
// NegativeFlash, Prism). The first pass (v62) renders the entire video with
// every other layer (clips, transitions, zoom, B-roll, MGs, non-caption_match
// text overlays, outro). This second pass takes that intermediate as the
// source video, draws the blend-mode captions and any caption_match text
// overlays on top so they have real video pixels to blend against, and emits
// a new video. Audio is muxed afterward.
//
// This composition only knows about the captions/caption_match overlays — it
// has no clip, transition, B-roll or MG state. That makes it a much smaller
// surface than the previous PromptlyBlendRender composition (which inlined
// every layer the v62 path already covers).
export interface PromptlyBlendCaptionsOnlyInput {
  videoUrl: string;
  fps: number;
  width: number;
  height: number;
  totalDurationInFrames: number;
  caption: CaptionSpec;
  /** caption_match-variant text overlays only — these render through the
   *  caption component and therefore also need video pixels underneath. Other
   *  variants (torn_paper / sticky_note / quote_card) are baked in by the
   *  v62 pass and must NOT be repeated here. */
  captionMatchOverlays: CaptionMatchOverlay[];
  /** Absolute composition frame at which the videoUrl's frame 0 should
   *  appear. Used by the pipelined chunked-blend path: each blend chunk
   *  K reads composite_chunk_K.mp4 (chunk-local video, frames 0..N/4-1
   *  internally) and renders against absolute composition frames
   *  K*N/4..K*N/4+N/4-1. With videoStartFrame=K*N/4 the OffthreadVideo
   *  is wrapped in a `<Sequence from={K*N/4}>` so its internal frame
   *  counter aligns with absolute composition time. Single-pass /
   *  un-pipelined renders default to 0. */
  videoStartFrame?: number;
}

export interface PromptlyBlendCaptionsOnlyProps {
  input: PromptlyBlendCaptionsOnlyInput;
}
