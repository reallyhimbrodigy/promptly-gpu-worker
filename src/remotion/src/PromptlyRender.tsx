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
  PromptlyBlendCaptionsOnlyProps,
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

// ─── PromptlyOverlay composition ───────────────────────────────────────────
// Renders ONLY the text/graphic overlay layer on a TRANSPARENT canvas:
// captions, motion graphics, text overlays. No video, no transitions, no
// zoom, no B-roll. Per-frame paint cost is tiny (small painted regions on
// transparent background).
//
// Output is encoded with alpha (ProRes 4444) so FFmpeg can composite it
// over the base in the final mux step.
export const PromptlyOverlay: React.FC<PromptlyRenderProps> = ({ input }) => {
  const { caption, motionGraphics, textOverlays, fps } = input;

  return (
    <AbsoluteFill style={{ background: "transparent" }}>
      <CaptionsLayer caption={caption} fps={fps} />
      <TextOverlaysLayer
        overlays={textOverlays ?? []}
        captionStyle={caption.style}
        captionExtraProps={caption.extraProps}
        captionKeywords={caption.keywords}
        fps={fps}
      />
      <MotionGraphicsLayer items={motionGraphics} fps={fps} />
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
