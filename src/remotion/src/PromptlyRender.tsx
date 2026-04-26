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
  PromptlyRenderInput,
  PromptlyRenderProps,
  ClipSpec,
  TransitionSpec,
  BrollSpec,
  CaptionSpec,
  MotionGraphicSpec,
  TextOverlaySpec,
  TikTokPageLike,
} from "./types";

// Caption styles — all 21
import {
  HormoziPopIn, GlitchHighlight, EmojiPop, NegativeFlash, PaperII,
  Prime, Prism, TypewriterReveal, CinematicLetterpress, Cove,
  Dimidium, EditorialPop, Gadzhi, Illuminate, Lumen,
  MagazineCutout, Passage, Pulse, Quintessence, Serif, StaggerWave,
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

// Motion graphics — all 15 + 4 SpeechBubble variants
import {
  LowerThird, AnnotationArrow, BRollFrame, QuoteCard, StatCard,
  Notification, ComparisonSplit, ChartReveal, ProgressBar, ChatThread,
  TornPaper, StickyNotes, Toggle, RecordingFrame,
  TweetBubble, InstagramComment, IMessageBubble, TikTokComment,
} from "./motion-graphics";

// ─── Component maps ────────────────────────────────────────────────────────
const CAPTION_MAP: Record<string, React.FC<any>> = {
  HormoziPopIn, GlitchHighlight, EmojiPop, NegativeFlash, PaperII,
  Prime, Prism, TypewriterReveal, CinematicLetterpress, Cove,
  Dimidium, EditorialPop, Gadzhi, Illuminate, Lumen,
  MagazineCutout, Passage, Pulse, Quintessence, Serif, StaggerWave,
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
  LowerThird, AnnotationArrow, BRollFrame, QuoteCard, StatCard,
  Notification, ComparisonSplit, ChartReveal, ProgressBar, ChatThread,
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

// ─── Clip series ───────────────────────────────────────────────────────────
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

// ─── B-roll cutaways ───────────────────────────────────────────────────────
const BrollOverlays: React.FC<{ broll: BrollSpec[] }> = ({ broll }) => (
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
            startFrom={b.seekFromFrames}
            playbackRate={b.playbackRate}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </AbsoluteFill>
      </Sequence>
    ))}
  </>
);

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
  for (const page of pages) {
    const pStart = page.startMs;
    const pEnd = page.startMs + page.durationMs;
    if (pEnd <= segStartMs) continue;
    if (pStart >= segEndMs) continue;
    const localStart = pStart - segStartMs;
    clippedPages.push({
      ...page,
      startMs: Math.max(0, localStart),
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
  if (overlay.variant === "lower_third") {
    return (
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <LowerThird
          startMs={0}
          durationMs={Math.round((overlay.durationInFrames / fps) * 1000)}
          name={overlay.name}
          title={overlay.title}
          accentColor={overlay.accentColor}
          theme={overlay.theme}
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

// ─── Outro fade ────────────────────────────────────────────────────────────
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

const resolveSrc = (s: string): string => {
  if (!s) return s;
  if (/^[a-z][a-z0-9+.-]*:/i.test(s) || s.startsWith("//")) return s;
  return staticFile(s);
};

// ─── PromptlyBase composition ──────────────────────────────────────────────
// Renders ONLY the underlying video timeline: clips, transitions, zoom, B-roll.
// Black background, no overlays. This is what FFmpeg used to do in the
// pre-66-pack era — it's intentionally minimal so per-frame paint cost stays
// at "video frame copy" levels.
//
// The Outro fade is included here because it's a full-canvas color overlay
// that operates on the underlying video, not on text/MG overlays.
export const PromptlyBase: React.FC<PromptlyRenderProps> = ({ input }) => {
  const { sourceUrl, clips, transitions, broll, outro } = input;
  const resolvedSourceUrl = resolveSrc(sourceUrl);
  const resolvedBroll = React.useMemo(
    () => broll.map((b) => ({ ...b, src: resolveSrc(b.src) })),
    [broll],
  );

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <ClipSeries clips={clips} transitions={transitions} sourceUrl={resolvedSourceUrl} />
      <BrollOverlays broll={resolvedBroll} />
      {outro && outro !== "none" ? <OutroFade kind={outro} /> : null}
    </AbsoluteFill>
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

// ─── Backward-compat alias ─────────────────────────────────────────────────
// Kept so older code paths or external callers that import `PromptlyRender`
// don't break — it now renders the union of base + overlay (the pre-split
// behavior, minus color effects which are deleted from the schema). New
// production renders use the split path via Root.tsx's two compositions.
export const PromptlyRender: React.FC<PromptlyRenderProps> = ({ input }) => {
  return (
    <>
      <PromptlyBase input={input} />
      <PromptlyOverlay input={input} />
    </>
  );
};
