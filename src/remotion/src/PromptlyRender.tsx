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
  ColorEffectSpec,
  MotionGraphicSpec,
  TextOverlaySpec,
  TikTokPageLike,
  CaptionPositionSegment,
} from "./types";

// Caption styles — all 21
import {
  HormoziPopIn, GlitchHighlight, EmojiPop, NegativeFlash, PaperII,
  Prime, Prism, TypewriterReveal, CinematicLetterpress, Cove,
  Dimidium, EditorialPop, Gadzhi, Illuminate, Lumen,
  MagazineCutout, Passage, Pulse, Quintessence, Serif, StaggerWave,
} from "./captions";

// Color effects — all 12
import {
  CinematicGrade, BleachBypass, VintageFilm, DreamHaze, ChromaSplit,
  VignettePulse, InvertStrike, CineMono, GoldenHour, FilmGrain,
  Portra, NeoNoir,
} from "./color-effects";

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

const COLOR_MAP: Record<string, React.FC<any>> = {
  CinematicGrade, BleachBypass, VintageFilm, DreamHaze, ChromaSplit,
  VignettePulse, InvertStrike, CineMono, GoldenHour, FilmGrain,
  Portra, NeoNoir,
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

// ─── Canvas + safe zone constants (1080×1920) ──────────────────────────────
const CANVAS_W = 1080;
const CANVAS_H = 1920;
const SAFE_X_MIN = 60;
const SAFE_X_MAX = 1020;
const SAFE_Y_MIN = 108;
const SAFE_Y_MAX = 1812;

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
  // Select only the pages whose [startMs, startMs+durationMs) intersects
  // the segment window, and rebase their startMs to segment-local time so
  // the inner caption component's useCurrentFrame aligns correctly.
  const segStartMs = Math.round((segmentStartFrame / fps) * 1000);
  const segEndMs = Math.round(((segmentStartFrame + segmentDurationInFrames) / fps) * 1000);
  const clippedPages: TikTokPageLike[] = [];
  for (const page of pages) {
    const pStart = page.startMs;
    const pEnd = page.startMs + page.durationMs;
    if (pEnd <= segStartMs) continue;
    if (pStart >= segEndMs) continue;
    // Rebase so startMs is relative to segment start.
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
// Build a caption-style page for caption_match variant.
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
// Each MG component was built to render against the full 1080×1920 canvas
// using its own `resolveMGPosition(props.anchor, offsetX, offsetY, scale)`
// against an AbsoluteFill. Python has already translated the safe-zone anchor
// into an MGAnchor and merged it into `props.anchor`. We render the component
// directly — no wrapper, no size assumptions, no face lookup.
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

// Resolve a basename or absolute URL into a Remotion-servable URL.
// Bare basenames (e.g. "source_30fps.mp4") are local files in publicDir
// and MUST be wrapped in staticFile() — without it, Remotion's bundle
// HTTP server tries to resolve against the bundle dir and 404s. Absolute
// URLs (http(s)://, file://) and protocol-relative URLs pass through.
const resolveSrc = (s: string): string => {
  if (!s) return s;
  if (/^[a-z][a-z0-9+.-]*:/i.test(s) || s.startsWith("//")) return s;
  return staticFile(s);
};

// ─── Top-level composition ─────────────────────────────────────────────────
export const PromptlyRender: React.FC<PromptlyRenderProps> = ({ input }) => {
  const {
    sourceUrl, clips, transitions, broll, caption,
    colorEffect, motionGraphics, outro, textOverlays, fps,
  } = input;

  // Resolve once at the boundary; every child component receives a URL
  // already resolved against publicDir.
  const resolvedSourceUrl = resolveSrc(sourceUrl);
  const resolvedBroll = React.useMemo(
    () => broll.map((b) => ({ ...b, src: resolveSrc(b.src) })),
    [broll],
  );

  const content = (
    <>
      <ClipSeries clips={clips} transitions={transitions} sourceUrl={resolvedSourceUrl} />
      <BrollOverlays broll={resolvedBroll} />
    </>
  );

  let graded: React.ReactNode;
  if (colorEffect) {
    const ColorComp = COLOR_MAP[colorEffect.type];
    if (ColorComp) {
      const { type: _t, intensity, timing, extraProps } = colorEffect;
      graded = (
        <ColorComp intensity={intensity} timing={timing} {...(extraProps ?? {})}>
          {content}
        </ColorComp>
      );
    } else {
      graded = content;
    }
  } else {
    graded = content;
  }

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {graded}
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
