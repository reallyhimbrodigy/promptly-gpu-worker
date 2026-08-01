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
// Python maps its safe-zone anchors (upper_third_safe, center, lower_third_safe)
// into this vocabulary before emitting the spec, and merges the mapped value
// into `props.anchor`. Side anchors (left/right) were removed — MGs always
// render horizontally centered. Face-relative anchoring is not supported by the
// motion-graphics pack — each component uses its own canvas-scale resolveMGPosition.
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
  // When set, the clip plays this pre-extracted source instead of seeking
  // into the composition-level sourceUrl. Frame 0 of this file is the
  // clip's first kept frame, already speed-adjusted, so the ABE zoom
  // components receive `src` only — no startFrom, no playbackRate.
  src?: string;
}

export interface ZoomEffectSpec {
  type: ZoomType;
  events: ZoomEventSpec[];
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
  | "DepthPull"
  | "StagedPush";

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
  | "StepPush"
  | "FilmStrip"
  | "DipToBlack";

// ── Tight-cut overlays ───────────────────────────────────────────────────────
// Overlay-on-top-of-hard-cut decoration for TIGHT BOUNDARIES (cuts where the
// audio gap is too small for a handle-required TransitionSpec). The overlay
// renders ON TOP of the unmodified hard cut in PromptlyOverlay's transparent
// canvas, in a window centered on atFrame. The cut itself plays straight
// underneath — no time inserted, no audio touched, no clipA/clipB blending.
//
// Render path is DISTINCT from TransitionSpec — these never appear in
// PromptlyMicroSegments and never participate in handle-frame math.
export type TightCutOverlayType =
  | "LightLeak"
  | "ShutterFlash"
 ;

export interface TightCutOverlaySpec {
  /** OUTPUT-timeline frame the hard cut sits on. Overlay window is centered
   *  on this frame: [atFrame - durationInFrames/2, atFrame + durationInFrames/2). */
  atFrame: number;
  type: TightCutOverlayType;
  /** Window length in output frames. Per-type:
   *  LightLeak / ShutterFlash = 11 (~180ms @ 60fps),
   *  longer hold for the title text to be readable). */
  durationInFrames: number;
}

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

// ── Generated scenes (Phase E · composed premium graphics) ──────────────────
// A GeneratedScene is composited from separate layers (background world →
// subject still → text → motion), NOT a flat image. Mirrors render_schemas.py.
export type GenSceneBackgroundKind = "generated" | "gradient" | "solid";
export type GenSceneEntrance = "fade" | "float" | "rise" | "scale" | "slide";
export type GenSceneEasing = "ease" | "linear" | "spring";
export type GenSceneAnchor = "upper_third_safe" | "center" | "lower_third_safe";

export interface GenSceneBackgroundSpec {
  kind: GenSceneBackgroundKind;
  paletteRef?: string | null;
  generationPrompt?: string | null;
  colors?: string[] | null;
}

export interface GenSceneSubjectSpec {
  /** Generated still URL (filled in Sub-step 3 by _generate_image + staging).
   *  Null until then; the layer draws a placeholder box when absent. */
  imageUrl?: string | null;
  generationPrompt: string;
  anchor: GenSceneAnchor;
  scale?: number | null;
}

export interface GenSceneTextLayerSpec {
  /** FROM-KNOWN-INPUTS-ONLY (transcript / user string) — never model-invented. */
  content: string;
  styleRef?: string | null;
  anchor: GenSceneAnchor;
  /** Lumen designed scenes: scene-local frame this word POPS on (VO word onset
   * projected onto the one shared clock). Absent → staggered default. */
  popFrame?: number | null;
}

/** TypoStat data fields — the stat arrives as DATA, never as prompt text. */
export interface GenSceneStatSpec {
  value?: number | null;
  prefix?: string | null;
  suffix?: string | null;
  label?: string | null;
  supporting_line?: string | null;
}

export interface GenSceneMotionSpec {
  entrance: GenSceneEntrance;
  easing: GenSceneEasing;
  motionBlur: boolean;
}

export interface GeneratedSceneSpec {
  fromFrame: number;
  durationInFrames: number;
  background: GenSceneBackgroundSpec;
  subject: GenSceneSubjectSpec;
  textLayers: GenSceneTextLayerSpec[];
  motion: GenSceneMotionSpec;
  /** Lumen DESIGNED scenes (Increment 3): typed compositions — typography,
   * palette, motion in code; the model contributes at most a hero asset.
   * Absent/null → the legacy full-frame GeneratedScene path. */
  /** ORIGIN index into the plan's generated_scenes (judge/degrade mapping). */
  sceneIndex?: number | null;
  sceneType?: "typo_stat" | "hero_object" | "photo_card" | null;
  /** TypoStat: the stat as data fields. */
  stat?: GenSceneStatSpec | null;
  /** TypoStat: scene-local frame the count LANDS its final value on (the
   * emphasis word's onset, shared clock — the Flare value-landing doctrine). */
  landFrame?: number | null;
  /** PhotoCard: staged card imagery URLs (user-provided or fetched). */
  photos?: string[] | null;
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
  | "Prime"
  | "TypewriterReveal"
  | "Cove"
  | "Lumen"
  | "Pulse"
  | "Quintessence"
  | "TwoTone"
  | "Gadzhi"
  | "CleanCut";

/**
 * SPEAKER-FOLLOWING CAPTIONS (Zac 2026-07-26, DARK): a per-page vertical anchor
 * pinning the caption block to the smoothed speaker head. `topPx` is the caption
 * block's top in canonical 1080x1920 canvas px. Present only when
 * PROMPTLY_SPEAKER_CAPTIONS is on; absent (undefined) → the style falls back to
 * its fixed `position` slot exactly as before. Horizontal is untouched.
 */
export interface CaptionAnchor {
  topPx: number;
}

export interface CaptionPositionSegment {
  fromFrame: number;
  toFrame: number;
  position: "top" | "center" | "bottom";
  anchor?: CaptionAnchor;
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
  | "RecordingFrame"
  | "StatCard"
  | "StickyNotes"
  | "TweetBubble"
  | "InstagramComment"
  | "IMessageBubble"
  | "TikTokComment"
  | "Timeline"
  | "Reticle"
  | "RankedList"
  | "PullQuote"
  | "PillCluster"
  | "Stamp"
  | "BarRace"
  | "SectionDivider"
  | "EditorialQuote"
  | "StepDivider"
  | "DropBanner"
  | "DropCard"
  | "PillMarquee"
  | "TimelineRoadmap"
  | "MouseDrag";

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
  | "sticky_note"
  | "caption_match";

interface TextOverlayBase {
  fromFrame: number;
  durationInFrames: number;
}

export interface StickyNoteOverlay extends TextOverlayBase {
  variant: "sticky_note";
  notes: Array<{ text: string; color: string; rotation: number }>;
}

export interface CaptionMatchOverlay extends TextOverlayBase {
  variant: "caption_match";
  text: string;
  position: "top" | "center" | "bottom";
}

export type TextOverlaySpec =
  | StickyNoteOverlay
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
  /** Generated composed scenes (Phase E). Empty by default — `[]` means no
   *  behavior change vs the pre-GeneratedScene pipeline (mirrors tightCutOverlays). */
  generatedScenes?: GeneratedSceneSpec[];
  caption?: CaptionSpec | null;   // W1: absent = caption-less render (first-class)
  textOverlays: TextOverlaySpec[];
  motionGraphics: MotionGraphicSpec[];
  /** Tight-cut overlay decorations. Empty by default — when Python emits no
   *  tight-cut overlay (the common case), this is `[]` and PromptlyOverlay's
   *  z-stack behaves identically to the pre-overlay pipeline. */
  tightCutOverlays?: TightCutOverlaySpec[];
  outro?: "none" | "fade_black" | "fade_white";
  /** Flare motion-token system (Workstream D). Absent/false = legacy
   *  per-component motion (today's exact pixels); true = shared SNAP/SETTLE/
   *  GLIDE tokens. ONE reversible flag for the whole system so the before/after
   *  is a true A/B — see motion-graphics/shared/motion.ts. Never touches the
   *  caption text layer (FRAME-1-IS-FINAL). Worker sets it from MOTION_TOKENS. */
  motionTokens?: boolean;
  /** Re-sprung zoom settle (Zac 2026-07-31). Absent/false = today's exact
   *  pixels: SnapReframe/FocusWindow keep overshootClamping:true (the frozen
   *  hard-stop "de-sprung" settle). true = clamp removed + damping lowered
   *  (SnapReframe 28→22 ζ≈0.881, FocusWindow 24→19.5 ζ≈0.869; mass UNTOUCHED so
   *  ω_n and speed are preserved) → smooth exponential settle, peak ≥9.6 frames
   *  @30fps (above the stepped-render floor). ONE reversible flag, default OFF,
   *  so the before/after is a true A/B. See zoom/shared/resprung-flag.tsx. */
  resprungZooms?: boolean;
  /** Workstream D2 — MOTION BLUR. Absent/false = NO new motion blur added
   *  anywhere (byte-identical to pre-D2; the existing Lumen / generated-scene
   *  blur is on its OWN path and is unaffected by this flag). true = wrap
   *  Flare's moving elements — component entrances/exits, composite zoom moves,
   *  transitions, and b-roll cutaway pushes — in CameraMotionBlur. Mirrors
   *  motionTokens: ONE reversible flag, default OFF, so the before/after is a
   *  true A/B. Never a global full-video blur (only motion-bearing elements).
   *  Worker sets it from MOTION_BLUR. See motion-graphics/shared/motion-blur.tsx. */
  motionBlur?: boolean;
  /** Optional per-render overrides so the parent can sweep the blur tunables
   *  WITHOUT recompiling. Omitted → MOTION_BLUR_DEFAULTS (samples=6,
   *  shutterAngle=180 — the 180° film convention). `samples` is the cost knob
   *  (render cost scales ~linearly with it); `shutterAngle` sets the smear
   *  SPREAD only and costs nothing extra. */
  motionBlurSamples?: number;
  motionBlurShutterAngle?: number;
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
  /** Workstream D2 — MOTION BLUR (see PromptlyRenderInput.motionBlur). This is
   *  the composition that renders transitions and composite zoom moves — every
   *  segment here IS motion — so the flag threads here too. Absent/false =
   *  byte-identical. Overrides fall through to MOTION_BLUR_DEFAULTS. */
  motionBlur?: boolean;
  /** Re-sprung zoom settle (see PromptlyRenderInput.resprungZooms). This is the
   *  composition that mounts SnapReframe/FocusWindow via ClipRenderer, so the
   *  flag threads here. Absent/false = today's clamped pixels. */
  resprungZooms?: boolean;
  motionBlurSamples?: number;
  motionBlurShutterAngle?: number;
}

export interface PromptlyMicroSegmentsProps {
  input: PromptlyMicroSegmentsInput;
}

