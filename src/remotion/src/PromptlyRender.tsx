import React from "react";
import {
  AbsoluteFill,
  Sequence,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";
import type {
  PromptlyRenderProps,
  PromptlyMicroSegmentsProps,
  PromptlyBlendCaptionsOnlyProps,
  BrollSpec,
  CaptionMatchOverlay,
  ClipSpec,
  TransitionSpec,
  CaptionSpec,
  MotionGraphicSpec,
  TextOverlaySpec,
  TikTokPageLike,
} from "./types";

// Caption styles. NegativeFlash, Prism, GlitchHighlight use CSS mixBlendMode
// against video pixels and can ONLY render correctly when real pixels sit
// underneath the captions. The pipeline handles this in two passes:
//   1. v62 produces the full video without those captions (handler.py zeroes
//      out caption.pages and filters out caption_match text overlays from
//      PromptlyOverlay's input when the chosen style is a blend style).
//   2. PromptlyBlendCaptionsOnly takes the v62 output as `<OffthreadVideo>`
//      source and draws the blend-mode captions + caption_match overlays on
//      top so the existing mixBlendMode components have real frame content
//      to blend against. Output is muxed with audio as the only further step.
// Components themselves are dumb — they render whatever input they receive.
// Routing happens in handler.py.
import {
  PaperII,
  Prime, TypewriterReveal, CinematicLetterpress, Cove,
  EditorialPop, Illuminate, Lumen,
  MagazineCutout, Passage, Pulse, Quintessence, Serif,
  GlitchHighlight, NegativeFlash, Prism,
} from "./captions";

// Transitions — all 11
import {
  CardSwipe, ZoomThrough, SlideOver, Stack, CrossfadeZoom,
  ShutterFlash, LightLeak, StepPush, NewspaperWipe, FilmStrip, SceneTitle,
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
  TornPaper, StickyNotes, Toggle, RecordingFrame,
  TweetBubble, InstagramComment, IMessageBubble, TikTokComment,
} from "./motion-graphics";

// ─── Component maps ────────────────────────────────────────────────────────
const CAPTION_MAP: Record<string, React.FC<any>> = {
  PaperII,
  Prime, TypewriterReveal, CinematicLetterpress, Cove,
  EditorialPop, Illuminate, Lumen,
  MagazineCutout, Passage, Pulse, Quintessence, Serif,
  GlitchHighlight, NegativeFlash, Prism,
};

const TRANSITION_MAP: Record<string, React.FC<any>> = {
  CardSwipe, ZoomThrough, SlideOver, Stack, CrossfadeZoom,
  ShutterFlash, LightLeak, StepPush, NewspaperWipe, FilmStrip, SceneTitle,
};

const ZOOM_MAP: Record<string, React.FC<any>> = {
  SmoothPush, SnapReframe, FocusWindow, StepZoom, LetterboxPush,
  StageZoom, DepthPull,
};

const MG_MAP: Record<string, React.FC<any>> = {
  AnnotationArrow, QuoteCard, StatCard,
  Notification, ProgressBar, ChatThread,
  TornPaper, StickyNotes, Toggle, RecordingFrame,
  TweetBubble, InstagramComment, IMessageBubble, TikTokComment,
};

// ─── Per-clip renderer ─────────────────────────────────────────────────────
const ClipRenderer: React.FC<{ clip: ClipSpec; sourceUrl: string }> = ({
  clip, sourceUrl,
}) => {
  if (clip.zoomEffect) {
    const ZoomComp = ZOOM_MAP[clip.zoomEffect.type];
    if (ZoomComp) {
      const { type: _t, events, ...extraZoomProps } = clip.zoomEffect;
      return (
        <ZoomComp
          src={sourceUrl}
          startFrom={clip.startFromFrames}
          playbackRate={clip.playbackRate}
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
  if (overlay.variant === "torn_paper") {
    return (
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <TornPaper
          startMs={0}
          durationMs={ovDurMs}
          topText={overlay.topText}
          bottomText={overlay.bottomText}
        />
      </AbsoluteFill>
    );
  }
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

/** Returns true if [from, from+duration) overlaps any [start, end) in
 *  brollWindows. Used to suppress text-overlays / MGs that would otherwise
 *  render on top of B-roll cutaways. Half-open intervals so a window
 *  ending exactly when the overlay starts doesn't count as overlap. */
const overlapsAnyBroll = (
  from: number,
  duration: number,
  brollWindows: number[][] | undefined,
): boolean => {
  if (!brollWindows || brollWindows.length === 0) return false;
  const a = from;
  const b = from + duration;
  for (const win of brollWindows) {
    if (!Array.isArray(win) || win.length < 2) continue;
    const s = win[0];
    const e = win[1];
    if (a < e && b > s) return true;
  }
  return false;
};

const TextOverlaysLayer: React.FC<{
  overlays: TextOverlaySpec[];
  captionStyle: CaptionSpec["style"];
  captionExtraProps?: Record<string, unknown>;
  captionKeywords: string[];
  fps: number;
  brollWindows?: number[][];
}> = ({ overlays, captionStyle, captionExtraProps, captionKeywords, fps, brollWindows }) => (
  <>
    {overlays.map((ov, i) => {
      if (overlapsAnyBroll(ov.fromFrame, ov.durationInFrames, brollWindows)) {
        return null;
      }
      return (
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
      );
    })}
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
  brollWindows?: number[][];
}> = ({ items, fps, brollWindows }) => (
  <>
    {items.map((mg, i) => {
      if (overlapsAnyBroll(mg.fromFrame, mg.durationInFrames, brollWindows)) {
        return null;
      }
      return (
        <Sequence
          key={`mg-${i}`}
          from={mg.fromFrame}
          durationInFrames={mg.durationInFrames}
        >
          <MotionGraphicRenderer spec={mg} fps={fps} />
        </Sequence>
      );
    })}
  </>
);

const resolveSrc = (s: string): string => {
  if (!s) return s;
  if (/^[a-z][a-z0-9+.-]*:/i.test(s) || s.startsWith("//")) return s;
  return staticFile(s);
};

// ─── B-roll layer (split-screen with slide-up entrance) ───────────────────
//
// Each B-roll occupies the BOTTOM HALF of the canvas (1080×960 on a 1080×1920
// canvas) with the speaker frame visible above. Spring-driven entrance slides
// the inset up from off-canvas; linear-eased exit slides it back down.
// Source video is 9:16 — `objectFit: cover` crops vertically to fit the 9:8
// inset shape, preserving horizontal width.
//
// Z-order: B-roll sits UNDER text overlays / MGs / captions in PromptlyOverlay.
// The captions stay on top so the viewer can read dialogue during cutaways.
//
// Animation timing: 250ms entrance spring, 250ms linear exit. Tight enough
// to feel intentional, slow enough to read as motion (not a flash).

const BrollClip: React.FC<{ spec: BrollSpec; fps: number }> = ({ spec, fps }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  // Geometry: B-roll inset fills the bottom half of canvas.
  const insetHeight = Math.round(height / 2);
  const dockedY = height - insetHeight;     // top of inset when docked
  const offscreenY = height;                 // top of inset when fully off-canvas below

  // Animation timing.
  const enterFrames = Math.max(1, Math.round(fps * 0.25));   // 250ms slide-up
  const exitFrames  = Math.max(1, Math.round(fps * 0.25));   // 250ms slide-down

  // Spring-driven entrance — settles cleanly without bounce.
  const enterSpring = spring({
    fps,
    frame,
    config: { damping: 18, mass: 0.7, stiffness: 200, overshootClamping: true },
    durationInFrames: enterFrames,
  });

  // Linear-eased exit (last `exitFrames` of the sequence's duration).
  const totalFrames = spec.durationInFrames;
  const exitStart = totalFrames - exitFrames;
  const exitProgress = interpolate(
    frame,
    [exitStart, totalFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Compose the y-position. Entrance interpolates offscreen → docked; exit
  // interpolates docked → offscreen. The exit takes over once it has begun
  // (exitProgress > 0), keeping the animation monotonic.
  const enterY = interpolate(enterSpring, [0, 1], [offscreenY, dockedY]);
  const exitY = interpolate(exitProgress, [0, 1], [dockedY, offscreenY]);
  const y = exitProgress > 0 ? exitY : enterY;

  // Source resolution: handler.py stages B-roll files into /remotion/bundle/
  // public with a stage-key-prefixed basename; spec.src is just that basename.
  // resolveSrc → staticFile() resolves it to a public URL.
  const resolvedSrc = resolveSrc(spec.src);

  // OffthreadVideo `startFrom` is in COMPOSITION frames. Match Python's
  // int(round(seekFromSeconds * fps)) exactly — same rounding policy =
  // no drift between Python's framing and Remotion's seek.
  const startFromFrames = Math.round(spec.seekFromSeconds * fps);

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: 0,
          top: y,
          width,
          height: insetHeight,
          overflow: "hidden",
          // Subtle top-edge shadow only — sells the layer-on-top feel
          // without competing with the seam.
          boxShadow: "0 -8px 24px rgba(0,0,0,0.35)",
        }}
      >
        <OffthreadVideo
          src={resolvedSrc}
          startFrom={startFromFrames}
          playbackRate={spec.playbackRate || 1.0}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>
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

// ─── PromptlyOverlay composition ───────────────────────────────────────────
// Renders ONLY the text/graphic overlay layer on a TRANSPARENT canvas:
// captions, motion graphics, text overlays. No video, no transitions, no
// zoom, no B-roll. Per-frame paint cost is tiny (small painted regions on
// transparent background).
//
// Output is encoded with alpha (ProRes 4444) so FFmpeg can composite it
// over the base in the final mux step.
export const PromptlyOverlay: React.FC<PromptlyRenderProps> = ({ input }) => {
  const { caption, motionGraphics, textOverlays, fps, brollWindows } = input;

  return (
    <AbsoluteFill style={{ background: "transparent" }}>
      {/* Captions render UNCONDITIONALLY — they bridge over B-roll so the
          viewer can still read the dialogue during cutaways. */}
      <CaptionsLayer caption={caption} fps={fps} />
      {/* Text overlays + MGs are SUPPRESSED during B-roll windows so cards,
          message bubbles, and notification stacks don't stack on top of
          stock-footage cutaways. */}
      <TextOverlaysLayer
        overlays={textOverlays ?? []}
        captionStyle={caption.style}
        captionExtraProps={caption.extraProps}
        captionKeywords={caption.keywords}
        fps={fps}
        brollWindows={brollWindows}
      />
      <MotionGraphicsLayer items={motionGraphics} fps={fps} brollWindows={brollWindows} />
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

// ─── PromptlyBlendCaptionsOnly composition ─────────────────────────────────
// Second-pass composition for blend-mode caption styles (GlitchHighlight,
// NegativeFlash, Prism). The v62 path produces the full video first WITHOUT
// captions (handler.py zeroes out caption.pages + filters caption_match
// overlays from the v62 PromptlyOverlay input). This composition then takes
// the v62 silent intermediate as its source, lays the blend-mode captions
// (and any caption_match-variant text overlays, which also render through
// the caption component) on top so the existing mixBlendMode CSS has real
// frame content to blend against — visually identical to before.
//
// Surface area: just captions + caption_match overlays + an OffthreadVideo
// background. No clips, transitions, B-roll, MGs, non-caption_match
// overlays, or outro fade — those are all handled by v62 and baked into
// the source video this composition consumes. That makes this a much
// smaller test surface than the previous PromptlyBlendRender.
//
// Output: h264 (no alpha — captions baked in). handler.py muxes audio
// onto this output as the only further step.
export const PromptlyBlendCaptionsOnly: React.FC<PromptlyBlendCaptionsOnlyProps> = ({
  input,
}) => {
  const { videoUrl, caption, captionMatchOverlays, fps } = input;
  const resolvedVideoUrl = resolveSrc(videoUrl);
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <OffthreadVideo
        src={resolvedVideoUrl}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
      <CaptionsLayer caption={caption} fps={fps} />
      <TextOverlaysLayer
        overlays={captionMatchOverlays}
        captionStyle={caption.style}
        captionExtraProps={caption.extraProps}
        captionKeywords={caption.keywords}
        fps={fps}
      />
    </AbsoluteFill>
  );
};
