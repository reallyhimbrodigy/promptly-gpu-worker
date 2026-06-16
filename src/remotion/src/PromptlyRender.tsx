import React from "react";
import {
  AbsoluteFill,
  Sequence,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
  interpolate,
} from "remotion";
import type {
  PromptlyRenderProps,
  PromptlyMicroSegmentsProps,
  BrollSpec,
  ClipSpec,
  TransitionSpec,
  CaptionSpec,
  MotionGraphicSpec,
  TextOverlaySpec,
  TightCutOverlaySpec,
  TightCutOverlayType,
  TikTokPageLike,
} from "./types";

// Tight-cut overlay dispatcher — renders OverlayCutEffect components
// ON TOP of the alpha overlay's transparent canvas. Each entry is local
// to its window (component returns null outside it). See
// transitions/overlays/OverlayCutEffect.tsx for the window math.
import {
  OverlayCutEffect,
  type OverlayCutEffectType,
} from "./transitions/overlays/OverlayCutEffect";

// PascalCase (canonical from Python / VALID_TIGHT_CUT_OVERLAYS) →
// lowercase (OverlayCutEffect's internal dispatch key). The internal
// component's type kept lowercase so the signed-off isolation test
// composition (Root.tsx OverlayCutTest) and its captured render
// commands continue to work unchanged.
const OVERLAY_TYPE_MAP: Record<TightCutOverlayType, OverlayCutEffectType> = {
  LightLeak: "lightleak",
  ShutterFlash: "shutterflash",
  NewspaperWipe: "newspaperwipe",
  SceneTitle: "scenetitle",
};

// Caption styles. All render through PromptlyOverlay's transparent canvas
// and composite onto the source via FFmpeg in a single final encode.
import {
  PaperII,
  Prime, TypewriterReveal, CinematicLetterpress, Cove,
  EditorialPop, Illuminate, Lumen,
  MagazineCutout, Passage, Pulse, Quintessence, Serif,
} from "./captions";

// Transitions — all 12
import {
  CardSwipe, ZoomThrough, SlideOver, Stack, CrossfadeZoom,
  ShutterFlash, LightLeak, StepPush, NewspaperWipe, FilmStrip, SceneTitle,
  DipToBlack,
} from "./transitions";

// Zoom effects — all 7
import {
  SmoothPush, SnapReframe, FocusWindow, StepZoom, LetterboxPush,
  StageZoom, DepthPull,
} from "./zoom";

// Motion graphics — 14 components total (10 standalone + 4 SpeechBubble variants).
import {
  AnnotationArrow, QuoteCard, StatCard,
  Notification, ProgressBar, ChatThread,
  StickyNotes, Toggle, RecordingFrame,
  TweetBubble, InstagramComment, IMessageBubble, TikTokComment,
} from "./motion-graphics";

// ─── Component maps ────────────────────────────────────────────────────────
const CAPTION_MAP: Record<string, React.FC<any>> = {
  PaperII,
  Prime, TypewriterReveal, CinematicLetterpress, Cove,
  EditorialPop, Illuminate, Lumen,
  MagazineCutout, Passage, Pulse, Quintessence, Serif,
};

const TRANSITION_MAP: Record<string, React.FC<any>> = {
  CardSwipe, ZoomThrough, SlideOver, Stack, CrossfadeZoom,
  ShutterFlash, LightLeak, StepPush, NewspaperWipe, FilmStrip, SceneTitle,
  DipToBlack,
};

const ZOOM_MAP: Record<string, React.FC<any>> = {
  SmoothPush, SnapReframe, FocusWindow, StepZoom, LetterboxPush,
  StageZoom, DepthPull,
};

const MG_MAP: Record<string, React.FC<any>> = {
  AnnotationArrow, QuoteCard, StatCard,
  Notification, ProgressBar, ChatThread,
  StickyNotes, Toggle, RecordingFrame,
  TweetBubble, InstagramComment, IMessageBubble, TikTokComment,
};

// ─── Per-clip renderer ─────────────────────────────────────────────────────
// Zoom clips render via the ABE.zip zoom components UNMODIFIED. Those
// components accept `src` + `events` + their component-specific extras only —
// no startFrom, no playbackRate. The pipeline pre-extracts a per-clip source
// file (frame 0 = clip's first kept frame, already speed-adjusted) and puts
// its URL in `clip.src`, so the component just plays it from frame 0 as
// designed. The component renderer never wraps or intercepts the components.
//
// Non-zoom clips (no zoomEffect) don't reach this renderer at all — they're
// rendered directly by FFmpeg in the final composite step.
const ClipRenderer: React.FC<{ clip: ClipSpec; sourceUrl: string }> = ({
  clip, sourceUrl,
}) => {
  if (clip.zoomEffect && clip.src) {
    const ZoomComp = ZOOM_MAP[clip.zoomEffect.type];
    if (ZoomComp) {
      const { type: _t, events, ...extraZoomProps } = clip.zoomEffect;
      return (
        <ZoomComp
          src={resolveSrc(clip.src)}
          events={events}
          {...extraZoomProps}
        />
      );
    }
  }
  return (
    <AbsoluteFill>
      <OffthreadVideo
        src={sourceUrl}
        startFrom={clip.startFromFrames}
        playbackRate={clip.playbackRate}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
    </AbsoluteFill>
  );
};

// ─── Per-transition renderer ───────────────────────────────────────────────
const TransitionRenderer: React.FC<{
  transition: TransitionSpec; sourceUrl: string;
}> = ({ transition, sourceUrl }) => {
  const frame = useCurrentFrame();
  const progress = interpolate(
    frame, [0, transition.durationInFrames], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const Comp = TRANSITION_MAP[transition.type];
  if (!Comp) {
    return (
      <AbsoluteFill>
        <OffthreadVideo
          src={sourceUrl}
          startFrom={transition.clipBStartFromFrames}
          playbackRate={transition.clipBPlaybackRate}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>
    );
  }
  const {
    type: _t, afterClipIndex: _a, durationInFrames: _d,
    clipAStartFromFrames, clipBStartFromFrames,
    clipAPlaybackRate, clipBPlaybackRate,
    ...extraProps
  } = transition;
  return (
    <Comp
      clipA={sourceUrl}
      clipB={sourceUrl}
      startFromA={clipAStartFromFrames}
      startFromB={clipBStartFromFrames}
      playbackRateA={clipAPlaybackRate}
      playbackRateB={clipBPlaybackRate}
      progress={progress}
      {...extraProps}
    />
  );
};

// ─── Captions: one Series segment per position window ──────────────────────
const CaptionSegmentRenderer: React.FC<{
  style: CaptionSpec["style"];
  pages: TikTokPageLike[];
  keywords: string[];
  extraProps?: Record<string, unknown>;
  position: "top" | "center" | "bottom";
  segmentStartFrame: number;
  segmentDurationInFrames: number;
  fps: number;
}> = ({
  style, pages, keywords, extraProps, position,
  segmentStartFrame, segmentDurationInFrames, fps,
}) => {
  const Comp = CAPTION_MAP[style];
  if (!Comp) return null;
  const segStartMs = Math.round((segmentStartFrame / fps) * 1000);
  const segEndMs = Math.round(((segmentStartFrame + segmentDurationInFrames) / fps) * 1000);
  const clippedPages: TikTokPageLike[] = [];
  // Each caption page belongs to exactly one position segment — the one
  // whose time window contains the page's MIDPOINT. Half-open interval
  // [segStartMs, segEndMs) ensures exactly-one assignment when adjacent
  // segments share a boundary (which they do by construction in the
  // synthesize-from-changes derivation in handler.py).
  //
  // Without this midpoint check, pages whose time window OVERLAPS a
  // segment boundary were being rendered in BOTH segments at different
  // positions — causing visible duplicate captions, animation restarts
  // mid-page, and the same word appearing at bottom AND center
  // simultaneously during the overlap. Same bug class as the word-
  // duplication fix in project_words_to_output (handler.py).
  for (const page of pages) {
    const pMid = page.startMs + page.durationMs / 2;
    if (pMid < segStartMs || pMid >= segEndMs) continue;
    const localStart = page.startMs - segStartMs;
    // Shift page AND tokens by segStartMs so both end up in segment-local
    // coordinates. The components compute (token.fromMs - pageStartMs) to
    // derive page-local time for word activation animations — this works
    // when:
    //   • page.startMs - segStartMs (positive case): pageStartMs is
    //     segment-relative; tokens shifted by segStartMs are also
    //     segment-relative; difference is page-relative.
    //   • localStart < 0 (page straddles segment boundary, midpoint puts
    //     it in this segment): pageStartMs clamps to 0; tokens shifted
    //     by segStartMs are segment-relative; difference equals the
    //     segment-relative token time, which IS the correct activation
    //     point inside the rendered page Sequence (since the page now
    //     starts at segment frame 0).
    // Using `segStartMs` as the delta — NOT `page.startMs - max(0,
    // localStart)` — keeps both branches consistent. The earlier formula
    // delayed tokens by up to (segStartMs − page.startMs) ms in the
    // straddling case, producing visible caption stacking and lag.
    const tokenDelta = segStartMs;
    clippedPages.push({
      ...page,
      startMs: Math.max(0, localStart),
      tokens: page.tokens.map((t) => ({
        ...t,
        fromMs: t.fromMs - tokenDelta,
        toMs: t.toMs - tokenDelta,
      })),
    });
  }
  if (!clippedPages.length) return null;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <Comp
        pages={clippedPages}
        keywords={keywords}
        position={position}
        {...(extraProps ?? {})}
      />
    </AbsoluteFill>
  );
};

const CaptionsLayer: React.FC<{ caption: CaptionSpec; fps: number }> = ({
  caption, fps,
}) => {
  if (!caption.pages.length || !caption.positionSegments.length) return null;
  return (
    <>
      {caption.positionSegments.map((seg, i) => {
        const dur = seg.toFrame - seg.fromFrame;
        if (dur <= 0) return null;
        return (
          <Sequence
            key={`cap-seg-${i}`}
            from={seg.fromFrame}
            durationInFrames={dur}
          >
            <CaptionSegmentRenderer
              style={caption.style}
              pages={caption.pages}
              keywords={caption.keywords}
              extraProps={caption.extraProps}
              position={seg.position}
              segmentStartFrame={seg.fromFrame}
              segmentDurationInFrames={dur}
              fps={fps}
            />
          </Sequence>
        );
      })}
    </>
  );
};

// ─── Text overlay variants ─────────────────────────────────────────────────
const buildOverlayPage = (
  text: string,
  durationInFrames: number,
  fps: number,
): TikTokPageLike => {
  const tokens: TikTokPageLike["tokens"] = [];
  const words = text.trim().split(/\s+/).filter(Boolean);
  if (!words.length) {
    return { text: "", startMs: 0, durationMs: 0, tokens: [] };
  }
  const totalMs = Math.max(400, Math.round((durationInFrames / fps) * 1000));
  const revealMs = Math.max(200, Math.round(totalMs * 0.6));
  const perWord = Math.max(80, Math.round(revealMs / words.length));
  let cursor = 0;
  for (const w of words) {
    const from = cursor;
    const to = Math.min(totalMs, cursor + perWord);
    tokens.push({ text: w, fromMs: from, toMs: to });
    cursor = to;
  }
  if (tokens.length) tokens[tokens.length - 1].toMs = totalMs;
  return { text: text.trim(), startMs: 0, durationMs: totalMs, tokens };
};

const TextOverlayRenderer: React.FC<{
  overlay: TextOverlaySpec;
  captionStyle: CaptionSpec["style"];
  captionExtraProps?: Record<string, unknown>;
  captionKeywords: string[];
  fps: number;
}> = ({ overlay, captionStyle, captionExtraProps, captionKeywords, fps }) => {
  const ovDurMs = Math.round((overlay.durationInFrames / fps) * 1000);
  if (overlay.variant === "sticky_note") {
    return (
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <StickyNotes
          startMs={0}
          durationMs={ovDurMs}
          notes={overlay.notes}
        />
      </AbsoluteFill>
    );
  }
  if (overlay.variant === "quote_card") {
    return (
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <QuoteCard
          startMs={0}
          durationMs={Math.round((overlay.durationInFrames / fps) * 1000)}
          quote={overlay.quote}
          attribution={overlay.attribution}
        />
      </AbsoluteFill>
    );
  }
  // caption_match
  const Comp = CAPTION_MAP[captionStyle];
  if (!Comp) return null;
  const page = buildOverlayPage(overlay.text, overlay.durationInFrames, fps);
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <Comp
        pages={[page]}
        keywords={captionKeywords}
        position={overlay.position}
        {...(captionExtraProps ?? {})}
      />
    </AbsoluteFill>
  );
};

const TextOverlaysLayer: React.FC<{
  overlays: TextOverlaySpec[];
  captionStyle: CaptionSpec["style"];
  captionExtraProps?: Record<string, unknown>;
  captionKeywords: string[];
  fps: number;
}> = ({ overlays, captionStyle, captionExtraProps, captionKeywords, fps }) => (
  <>
    {overlays.map((ov, i) => (
      <Sequence
        key={`txt-${i}`}
        from={ov.fromFrame}
        durationInFrames={ov.durationInFrames}
      >
        <TextOverlayRenderer
          overlay={ov}
          captionStyle={captionStyle}
          captionExtraProps={captionExtraProps}
          captionKeywords={captionKeywords}
          fps={fps}
        />
      </Sequence>
    ))}
  </>
);

// ─── Motion graphics ───────────────────────────────────────────────────────
const MotionGraphicRenderer: React.FC<{
  spec: MotionGraphicSpec;
  fps: number;
}> = ({ spec, fps }) => {
  const Comp = MG_MAP[spec.type];
  if (!Comp) return null;
  return (
    <Comp
      startMs={0}
      durationMs={Math.round((spec.durationInFrames / fps) * 1000)}
      {...spec.props}
    />
  );
};

const MotionGraphicsLayer: React.FC<{
  items: MotionGraphicSpec[];
  fps: number;
}> = ({ items, fps }) => (
  <>
    {items.map((mg, i) => (
      <Sequence
        key={`mg-${i}`}
        from={mg.fromFrame}
        durationInFrames={mg.durationInFrames}
      >
        <MotionGraphicRenderer spec={mg} fps={fps} />
      </Sequence>
    ))}
  </>
);

const resolveSrc = (s: string): string => {
  if (!s) return s;
  if (/^[a-z][a-z0-9+.-]*:/i.test(s) || s.startsWith("//")) return s;
  return staticFile(s);
};

// ─── B-roll layer (full-frame cutaway) ────────────────────────────────────
//
// B-roll replaces the entire canvas during its window — same as a standard
// short-form B-roll cutaway in TikTok/Reels/YouTube edits. The speaker's
// audio continues over the B-roll; the speaker's video disappears for the
// duration. Source is 9:16 (1080x1920); `objectFit: cover` crops to fit
// arbitrary aspect ratios so we always fill the canvas without letterbox.
//
// Z-order: B-roll sits UNDER captions in PromptlyOverlay so dialogue stays
// readable through the cutaway. Captions auto-flip to "top" during B-roll
// windows (Python pipeline; see _force_top_position_during_broll) so they
// land in the upper third where they don't compete with the B-roll subject.
//
// Boundary fade: ~67ms in, ~67ms out, fps-aware (was hardcoded at 4 frames,
// which doubled to 133ms at the comp's 30fps and made B-roll feel delayed
// against word-onset). Tight enough to feel like a hard cut, soft enough to
// avoid harsh boundary artifacts on the encoder.

const BrollClip: React.FC<{ spec: BrollSpec; fps: number }> = ({ spec, fps }) => {
  const frame = useCurrentFrame();

  const totalFrames = spec.durationInFrames;
  const fadeFrames = Math.max(1, Math.round(fps * 0.067));
  const fadeIn = interpolate(
    frame,
    [0, fadeFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const fadeOut = interpolate(
    frame,
    [totalFrames - fadeFrames, totalFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const opacity = Math.min(fadeIn, fadeOut);

  // Source resolution: handler.py stages B-roll files into /remotion/bundle/
  // public with a stage-key-prefixed basename; spec.src is just that basename.
  // resolveSrc → staticFile() resolves it to a public URL.
  const resolvedSrc = resolveSrc(spec.src);

  // OffthreadVideo `startFrom` is in COMPOSITION frames. Match Python's
  // int(round(seekFromSeconds * fps)) exactly — same rounding policy =
  // no drift between Python's framing and Remotion's seek.
  const startFromFrames = Math.round(spec.seekFromSeconds * fps);

  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity, backgroundColor: "#000" }}>
      <OffthreadVideo
        src={resolvedSrc}
        startFrom={startFromFrames}
        playbackRate={spec.playbackRate || 1.0}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
    </AbsoluteFill>
  );
};

const BrollLayer: React.FC<{
  items: BrollSpec[];
  fps: number;
}> = ({ items, fps }) => (
  <>
    {items.map((br, i) => (
      <Sequence
        key={`broll-${i}`}
        from={br.fromFrame}
        durationInFrames={br.durationInFrames}
      >
        <BrollClip spec={br} fps={fps} />
      </Sequence>
    ))}
  </>
);

// ─── Tight-cut overlay layer ───────────────────────────────────────────────
// Iterates the tightCutOverlays list and renders one OverlayCutEffect per
// entry. Each component reads useCurrentFrame() against the composition's
// absolute timeline; outside its window it returns null. atFrame is the
// COMPOSITION-time frame the hard cut sits on (Python emits this from
// the OUTPUT clip range — get_output_clip_ranges[i]["end"] in seconds
// times the composition fps).
//
// Strictly additive: an empty array produces zero DOM (the .map renders
// nothing). The pre-overlay behavior is exactly recoverable by emitting
// an empty list — pixel-identical, audio-identical baseline.
const TightCutOverlayLayer: React.FC<{
  overlays: TightCutOverlaySpec[];
}> = ({ overlays }) => {
  if (!overlays.length) return null;
  return (
    <>
      {overlays.map((ov, i) => (
        <OverlayCutEffect
          key={`tco-${i}-${ov.atFrame}`}
          type={OVERLAY_TYPE_MAP[ov.type]}
          atFrame={ov.atFrame}
          durationInFrames={ov.durationInFrames}
          title={ov.title}
          label={ov.label}
        />
      ))}
    </>
  );
};

// ─── PromptlyOverlay composition ───────────────────────────────────────────
// Renders ONLY the text/graphic overlay layer on a TRANSPARENT canvas:
// captions, motion graphics, text overlays. No video, no transitions, no
// zoom, no B-roll. Per-frame paint cost is tiny (small painted regions on
// transparent background).
//
// Output is encoded with alpha (ProRes 4444) so FFmpeg can composite it
// over the base in the final mux step.
export const PromptlyOverlay: React.FC<PromptlyRenderProps> = ({ input }) => {
  const { caption, motionGraphics, textOverlays, fps, broll, tightCutOverlays } = input;

  return (
    <AbsoluteFill style={{ background: "transparent" }}>
      {/* B-roll cutaways render at the BOTTOM of the overlay z-stack —
          under captions, text overlays, and MGs. Each B-roll fills the
          ENTIRE canvas during its window (full-frame cutaway, standard
          short-form B-roll convention). The speaker frame rendered by
          FFmpeg below this alpha overlay is fully covered for the duration
          of every B-roll window. Captions auto-flip to "top" during B-roll
          windows so they remain readable over the cutaway content. */}
      <BrollLayer items={broll ?? []} fps={fps} />
      {/* Captions on top — readable over speaker, B-roll, and any
          text-overlay/MG underneath. Universal text-stroke ensures contrast
          against arbitrary backgrounds (see captions/*.tsx). */}
      <CaptionsLayer caption={caption} fps={fps} />
      <TextOverlaysLayer
        overlays={textOverlays ?? []}
        captionStyle={caption.style}
        captionExtraProps={caption.extraProps}
        captionKeywords={caption.keywords}
        fps={fps}
      />
      <MotionGraphicsLayer items={motionGraphics} fps={fps} />
      {/* Tight-cut overlays render on TOP of every other layer. The flash /
          warm leak briefly washes through captions + MGs at the cut frame,
          masking the hard-cut discontinuity. Outside each 11-frame window
          the components return null (no z-stack cost). */}
      <TightCutOverlayLayer overlays={tightCutOverlays ?? []} />
    </AbsoluteFill>
  );
};

// ─── PromptlyMicroSegments composition ─────────────────────────────────────
// Renders ONLY the windows that FFmpeg can't replicate without visual drift:
//   - Every transition (CardSwipe, FilmStrip, SceneTitle, NewspaperWipe,
//     LightLeak, etc. — all 11 use bespoke React/CSS that has no faithful
//     FFmpeg analog).
//   - Composite-effect zoom clips (FocusWindow, LetterboxPush, DepthPull —
//     multi-layer overlays, blur masks, bokeh orbs, etc.).
// Pure scale-only zooms (SmoothPush, SnapReframe, StepZoom, StageZoom) and
// no-zoom clips are produced directly by FFmpeg in handler.py.
//
// Segments are concatenated end-to-end in the composition timeline so Python
// can render them all in ONE Remotion process (no per-segment subprocess
// startup tax) and then trim each segment back out by frame range using
// FFmpeg `trim` in the final composite step.
export const PromptlyMicroSegments: React.FC<PromptlyMicroSegmentsProps> = ({
  input,
}) => {
  const { sourceUrl, segments } = input;
  const resolvedSourceUrl = resolveSrc(sourceUrl);

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {segments.map((seg, i) => (
        <Sequence
          key={`micro-${i}`}
          from={seg.outputStartFrame}
          durationInFrames={seg.durationInFrames}
        >
          {seg.type === "transition" && seg.transition ? (
            <TransitionRenderer
              transition={seg.transition}
              sourceUrl={resolvedSourceUrl}
            />
          ) : null}
          {seg.type === "zoom_clip" && seg.clip ? (
            <ClipRenderer clip={seg.clip} sourceUrl={resolvedSourceUrl} />
          ) : null}
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

