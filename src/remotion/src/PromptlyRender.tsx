import React from "react";
import {
  AbsoluteFill,
  Sequence,
  Series,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";
import type {
  PromptlyRenderProps,
  PromptlyMicroSegmentsProps,
  ClipSpec,
  TransitionSpec,
  BrollSpec,
  CaptionSpec,
  MotionGraphicSpec,
  TextOverlaySpec,
  TikTokPageLike,
} from "./types";

// Caption styles. NegativeFlash, Prism, GlitchHighlight use CSS mixBlendMode
// against video pixels — they only render correctly inside PromptlyBlendRender
// (the full Remotion composition that includes the source video as a
// background layer). The other styles render in the transparent PromptlyOverlay
// composition that the v62 FFmpeg-base architecture composites on top of the
// FFmpeg-built base video.
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
    // Shift page AND tokens by the same delta so they remain in the same
    // coordinate system. The components subtract pageStartMs from
    // token.fromMs to derive page-local time — that math only works when
    // both are shifted together. Without this, mutating page.startMs alone
    // breaks the per-token activation animations (words appear all at
    // once instead of progressively as spoken).
    const tokenDelta = page.startMs - Math.max(0, localStart);
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

// ─── Helpers for PromptlyBlendRender (full Remotion-primary composition) ────
// These mirror the pre-v62 architecture so blend-mode caption styles
// (GlitchHighlight, NegativeFlash, Prism) have actual video pixels underneath
// to blend against. The v62 FFmpeg-base architecture is bypassed entirely for
// blend-mode renders; PromptlyBlendRender produces the final h264 video and
// audio is muxed in a single FFmpeg pass.

const ClipSeries: React.FC<{
  clips: ClipSpec[]; transitions: TransitionSpec[]; sourceUrl: string;
}> = ({ clips, transitions, sourceUrl }) => {
  const byIdx = new Map<number, TransitionSpec>();
  for (const t of transitions) byIdx.set(t.afterClipIndex, t);

  return (
    <Series>
      {clips.map((clip, i) => {
        const trans = byIdx.get(i);
        return (
          <React.Fragment key={`clip-${clip.id}`}>
            <Series.Sequence durationInFrames={clip.durationInFrames}>
              <ClipRenderer clip={clip} sourceUrl={sourceUrl} />
            </Series.Sequence>
            {trans && i < clips.length - 1 ? (
              <Series.Sequence durationInFrames={trans.durationInFrames}>
                <TransitionRenderer transition={trans} sourceUrl={sourceUrl} />
              </Series.Sequence>
            ) : null}
          </React.Fragment>
        );
      })}
    </Series>
  );
};

const BrollOverlays: React.FC<{ broll: BrollSpec[]; fps: number }> = ({ broll, fps }) => (
  <>
    {broll.map((b, i) => (
      <Sequence
        key={`broll-${i}`}
        from={b.fromFrame}
        durationInFrames={b.durationInFrames}
      >
        <AbsoluteFill style={{ background: "#000" }}>
          <OffthreadVideo
            src={b.src}
            startFrom={Math.round((b.seekFromSeconds ?? 0) * fps)}
            playbackRate={b.playbackRate}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </AbsoluteFill>
      </Sequence>
    ))}
  </>
);

const OutroFade: React.FC<{ kind: "fade_black" | "fade_white" }> = ({ kind }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();
  const fadeFrames = Math.round(fps * 1.0);
  const start = Math.max(0, durationInFrames - fadeFrames);
  const alpha = interpolate(
    frame, [start, durationInFrames], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const bg = kind === "fade_white" ? "#ffffff" : "#000000";
  return (
    <AbsoluteFill style={{ backgroundColor: bg, opacity: alpha, pointerEvents: "none" }} />
  );
};

// ─── PromptlyBlendRender composition ───────────────────────────────────────
// Used ONLY when caption_style is one of {GlitchHighlight, NegativeFlash, Prism}.
// These caption components use CSS mixBlendMode (screen/difference/multiply/
// color-burn) against video pixels to produce their chromatic-aberration,
// inversion, and color-flash effects. They cannot render correctly on a
// transparent canvas.
//
// PromptlyBlendRender is the pre-v62 single-render architecture: source video
// + clips + transitions + zoom + B-roll + outro fade as the BASE, with
// captions + text overlays + motion graphics composited on top in the same
// Remotion process. Captions blend against the actual video pixels.
//
// Output: h264 (no alpha needed — captions are baked in). handler.py muxes
// audio onto this output as the only post-Remotion step.
//
// Trade-off: render time goes up vs. v62 (FFmpeg-base + alpha overlay run in
// parallel in v62; PromptlyBlendRender is single-threaded Remotion). Accepted
// trade-off for correct blend-mode caption rendering.
export const PromptlyBlendRender: React.FC<PromptlyRenderProps> = ({ input }) => {
  const { sourceUrl, clips, transitions, broll, caption, motionGraphics, textOverlays, outro, fps } = input;
  const resolvedSourceUrl = resolveSrc(sourceUrl);
  const resolvedBroll = React.useMemo(
    () => broll.map((b) => ({ ...b, src: resolveSrc(b.src) })),
    [broll],
  );

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <ClipSeries clips={clips} transitions={transitions} sourceUrl={resolvedSourceUrl} />
      <BrollOverlays broll={resolvedBroll} fps={fps} />
      <CaptionsLayer caption={caption} fps={fps} />
      <TextOverlaysLayer
        overlays={textOverlays ?? []}
        captionStyle={caption.style}
        captionExtraProps={caption.extraProps}
        captionKeywords={caption.keywords}
        fps={fps}
      />
      <MotionGraphicsLayer items={motionGraphics} fps={fps} />
      {outro && outro !== "none" ? <OutroFade kind={outro} /> : null}
    </AbsoluteFill>
  );
};
