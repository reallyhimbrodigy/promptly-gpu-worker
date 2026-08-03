import React from "react";
import {
  AbsoluteFill,
  Sequence,
  Img,
  staticFile,
  useCurrentFrame,
  interpolate,
  spring,
} from "remotion";
import { Video } from "@remotion/media";
import { CameraMotionBlur } from "@remotion/motion-blur";
import { LumenScene } from "./LumenScenes";
import type {
  PromptlyRenderProps,
  PromptlyMicroSegmentsProps,
  BrollSpec,
  GeneratedSceneSpec,
  GenSceneTextLayerSpec,
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
};

// Caption styles. All render through PromptlyOverlay's transparent canvas
// and composite onto the source via FFmpeg in a single final encode.
import {
  Prime, TypewriterReveal, Cove,
  Lumen,
  Pulse, Quintessence,
  // Batch 2 (4 net-new caption styles)
  TwoTone, CleanCut,
  // Directive #12 promotions (ABE archive)
  Gadzhi,
} from "./captions";
import { pagesDirection } from "./captions/shared/direction";

// Transitions — all 12
import {
  CardSwipe, ZoomThrough, SlideOver, Stack, CrossfadeZoom,
  ShutterFlash, LightLeak, StepPush, FilmStrip,
  DipToBlack,
} from "./transitions";

// Zoom effects
import {
  SmoothPush, SnapReframe, FocusWindow, StepZoom, LetterboxPush,
  DepthPull, StagedPush,
} from "./zoom";

// Motion graphics — 29 components total (13 batch 1 + 16 batch 2). All share the
// MGTimingProps/MGPositionProps + useMGPhase interface; the renderer feeds each
// startMs=0 + window-derived durationMs + spread props (see MotionGraphicRenderer).
import {
  AnnotationArrow, StatCard,
  Notification, ProgressBar, ChatThread,
  StickyNotes, RecordingFrame,
  TweetBubble, InstagramComment, IMessageBubble, TikTokComment,
  // Batch 2 (16 net-new)
  Timeline, Reticle, RankedList, PullQuote,
  PillCluster, Stamp, BarRace, SectionDivider, EditorialQuote, StepDivider,
  DropBanner, DropCard, PillMarquee, TimelineRoadmap, MouseDrag,
} from "./motion-graphics";

// Flare motion-token system (Workstream D). The provider gates the whole
// system on one flag; migrated components read useMotionTokens(). GLIDE/
// EASE_GLIDE/dur drive the token-ON b-roll path below.
import { MotionTokensProvider, useMotionTokens } from "./motion-graphics/shared/motion-flag";
import { ResprungZoomsProvider } from "./zoom/shared/resprung-flag";
// SMOOTH-GRAPHICS (Zac 2026-08-01): eased + ms-floored entrances/exits/fades/
// transitions. Wraps both compositions; migrated components read useSmoothGraphics().
import { SmoothGraphicsProvider, useSmoothGraphics } from "./motion-graphics/shared/smooth-graphics-flag";
import { GLIDE, EASE_GLIDE, dur } from "./motion-graphics/shared/motion";

// Flare motion blur (Workstream D2). Parallel dark flag to motionTokens.
// `MotionBlurWrap` wraps a moving element in CameraMotionBlur when ON, and
// returns the child untouched when OFF (byte-identical). `MotionBlurProvider`
// carries the flag + tunables (samples / shutterAngle) from the render input.
import {
  MotionBlurProvider,
  MotionBlurWrap,
} from "./motion-graphics/shared/motion-blur";
import { SafeImg } from "./SafeImg";

// ─── Component maps ────────────────────────────────────────────────────────
const CAPTION_MAP: Record<string, React.FC<any>> = {
  Prime, TypewriterReveal, Cove, Lumen, Pulse, Quintessence,
  // Batch 2 (4 net-new)
  TwoTone, CleanCut,
  // Directive #12 promotions (ABE archive)
  Gadzhi,
};

const TRANSITION_MAP: Record<string, React.FC<any>> = {
  CardSwipe, ZoomThrough, SlideOver, Stack, CrossfadeZoom,
  ShutterFlash, LightLeak, StepPush, FilmStrip,
  DipToBlack,
};

const ZOOM_MAP: Record<string, React.FC<any>> = {
  SmoothPush, SnapReframe, FocusWindow, StepZoom, LetterboxPush,
  DepthPull, StagedPush,
};

export const MG_MAP: Record<string, React.FC<any>> = {
  AnnotationArrow, StatCard,
  Notification, ProgressBar, ChatThread,
  StickyNotes, RecordingFrame,
  TweetBubble, InstagramComment, IMessageBubble, TikTokComment,
  // Batch 2 (16 net-new) — canonical type names = export names.
  Timeline, Reticle, RankedList, PullQuote,
  PillCluster, Stamp, BarRace, SectionDivider, EditorialQuote, StepDivider,
  DropBanner, DropCard, PillMarquee, TimelineRoadmap, MouseDrag,
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
      <Video
        src={sourceUrl}
        trimBefore={clip.startFromFrames}
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
        <Video
          src={sourceUrl}
          trimBefore={transition.clipBStartFromFrames}
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
  anchor?: { topPx: number };
  segmentStartFrame: number;
  segmentDurationInFrames: number;
  fps: number;
}> = ({
  style, pages, keywords, extraProps, position, anchor,
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
    //
    // Front-edge straddle (localStart < 0): clamp startMs to 0 AND
    // shrink durationMs by |localStart|. Without the shrink, the
    // clipped page renders for its full original durationMs from
    // segment-local 0 — overstaying its true end by |localStart| ms
    // and stacking with the next page in the same segment.
    //
    // Back-edge straddle (page extends past segEndMs) needs no mirror
    // clamp: Remotion's parent Sequence bounds children's render
    // lifetime, so the position-segment outer Sequence cuts the inner
    // page at segEndMs. See remotion/Sequence.js:145-150.
    const tokenDelta = segStartMs;
    clippedPages.push({
      ...page,
      startMs: Math.max(0, localStart),
      durationMs: page.durationMs + Math.min(0, localStart),
      tokens: page.tokens.map((t) => ({
        ...t,
        fromMs: t.fromMs - tokenDelta,
        toMs: t.toMs - tokenDelta,
      })),
    });
  }
  if (!clippedPages.length) return null;
  // SINGLE-PAINT INVARIANT tripwire (caption-stack fix, 2026-07-04): the
  // Python page builder now guarantees non-overlapping page windows by
  // construction — an overlap reaching this point means a construction
  // regression (or a replayed pre-fix plan), so clamp it here too and log
  // the grep-stable line. This guard should be unreachable.
  for (let pi = 0; pi < clippedPages.length - 1; pi++) {
    const limit = clippedPages[pi + 1].startMs - clippedPages[pi].startMs;
    if (clippedPages[pi].durationMs > limit) {
      // eslint-disable-next-line no-console
      console.log(
        `[caption-paint] deduped page="${clippedPages[pi].text}" ` +
          `clamped=${clippedPages[pi].durationMs - Math.max(1, limit)}ms`,
      );
      clippedPages[pi] = {
        ...clippedPages[pi],
        durationMs: Math.max(1, limit),
      };
    }
  }
  // MULTILINGUAL A2.2 — RTL word order. Every caption lays its words out as
  // separate inline-block spans in a flex row; each span is an atomic bidi box,
  // so the row flows in this wrapper's inherited `direction`. Setting it from the
  // caption's own script reverses word order for Arabic/Hebrew across all 9
  // components at once — no per-component change. ltr is a no-op (Latin stays
  // byte-identical); physical `left`/`translateX` centering is unaffected.
  const direction = pagesDirection(clippedPages);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", direction }}>
      <Comp
        pages={clippedPages}
        keywords={keywords}
        position={position}
        anchor={anchor}
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
              anchor={seg.anchor}
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
        {/* D2: the MG's entrance/exit is the motion. Blur wraps the whole MG
            window (per-frame entrance/exit windowing isn't available at this
            layer); static hold frames re-render identically under the blur but
            still pay the samples× cost — see the cost note in the D2 report. */}
        <MotionBlurWrap>
          <MotionGraphicRenderer spec={mg} fps={fps} />
        </MotionBlurWrap>
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
  const motionTokens = useMotionTokens();

  const totalFrames = spec.durationInFrames;
  const fadeFrames = Math.max(1, Math.round(fps * 0.067));

  // LEGACY (flag OFF) — today's exact pixels: bare-linear opacity crossfade,
  // ~67ms each side, no transform. Preserved verbatim so the OFF render is a
  // true off-state for the A/B (the audit's "amateur linear fade").
  const legacyFadeIn = interpolate(
    frame,
    [0, fadeFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const legacyFadeOut = interpolate(
    frame,
    [totalFrames - fadeFrames, totalFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const legacyOpacity = Math.min(legacyFadeIn, legacyFadeOut);

  // TOKEN (flag ON) — same ~67ms fade windows (still reads as a cut), but the
  // opacity is eased (EASE_GLIDE) rather than dead-linear, and the cutaway
  // "lands" via a subtle GLIDE scale-settle 1.04→1.0 over BASE. GLIDE is
  // clamped → monotonic, so a cutaway never wobbles (a bounce here would look
  // wrong). No slide/position move — full-frame cover is preserved.
  const tokenFadeIn = interpolate(
    frame,
    [0, fadeFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE_GLIDE }
  );
  const tokenFadeOut = interpolate(
    frame,
    [totalFrames - fadeFrames, totalFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE_GLIDE }
  );
  const settle = spring({
    frame,
    fps,
    config: GLIDE,
    durationInFrames: dur("BASE", fps),
  });
  const tokenScale = 1.04 - 0.04 * settle; // 1.04 → 1.0, no overshoot (clamped)

  // SMOOTH-GRAPHICS (Zac 2026-08-01): the b-roll cutaway is the WORST case — a
  // 67ms/2-frame bare-linear opacity fade with no transform, on every cut. Widen
  // the fade to ~300ms (≥9 samples @30fps) + EASE_GLIDE so it glides instead of
  // stepping, and keep the scale-settle so the cutaway "lands." Full-frame cover
  // preserved (no slide). Cut-vs-fade feel is Zac's-eye via the pair.
  const smoothGraphics = useSmoothGraphics();
  const smoothFadeFrames = Math.max(1, Math.round(fps * 0.30));
  const smoothFadeIn = interpolate(
    frame, [0, smoothFadeFrames], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE_GLIDE }
  );
  const smoothFadeOut = interpolate(
    frame, [totalFrames - smoothFadeFrames, totalFrames], [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE_GLIDE }
  );

  const opacity = smoothGraphics
    ? Math.min(smoothFadeIn, smoothFadeOut)
    : motionTokens ? Math.min(tokenFadeIn, tokenFadeOut) : legacyOpacity;
  const scale = smoothGraphics || motionTokens ? tokenScale : 1;

  // Source resolution: handler.py stages B-roll files into /remotion/bundle/
  // public with a stage-key-prefixed basename; spec.src is just that basename.
  // resolveSrc → staticFile() resolves it to a public URL.
  const resolvedSrc = resolveSrc(spec.src);

  // OffthreadVideo `startFrom` is in COMPOSITION frames. Match Python's
  // int(round(seekFromSeconds * fps)) exactly — same rounding policy =
  // no drift between Python's framing and Remotion's seek.
  const startFromFrames = Math.round(spec.seekFromSeconds * fps);

  return (
    // D2: the cutaway "push" (the scale-settle on the token path) is the motion
    // that carries the smear. NOTE (report §cost): this wraps a full-frame
    // OffthreadVideo, so it is the MOST expensive site (video decode/composite
    // ×samples) and the LEAST valuable on the legacy path (which is an
    // opacity-only fade — motion blur smears position/scale, not opacity).
    <MotionBlurWrap>
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          opacity,
          backgroundColor: "#000",
          transform: `scale(${scale})`,
        }}
      >
        <Video
          src={resolvedSrc}
          trimBefore={startFromFrames}
          playbackRate={spec.playbackRate || 1.0}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>
    </MotionBlurWrap>
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

// ─── Generated scene layer (Phase E · composed premium graphics) ───────────
// A GeneratedScene composites SEPARATE layers: a background world (CSS
// gradient/solid, or the subject's own generated frame), the generated subject
// still (anchored + scaled), and kinetic text — wrapped in a motion entrance
// (spring) optionally run through CameraMotionBlur for the "buttery" feel at
// 60fps. INERT until Sub-step 3 fills subject.imageUrl and Sub-step 5 makes the
// model emit scenes; `generatedScenes` is [] today so this renders nothing.
const genSceneAnchorTop = (anchor: string): string =>
  anchor === "upper_third_safe"
    ? "24%"
    : anchor === "lower_third_safe"
      ? "74%"
      : "50%";

const GenSceneText: React.FC<{
  layer: GenSceneTextLayerSpec;
  progress: number;
}> = ({ layer, progress }) => (
  <div
    style={{
      position: "absolute",
      top: genSceneAnchorTop(layer.anchor),
      left: 0,
      right: 0,
      transform: "translateY(-50%)",
      padding: "0 72px",
      textAlign: "center",
      color: "#ffffff",
      fontSize: 68,
      fontWeight: 800,
      lineHeight: 1.04,
      letterSpacing: "-0.02em",
      textShadow: "0 6px 28px rgba(0,0,0,0.4)",
      opacity: progress,
    }}
  >
    {layer.content}
  </div>
);

const GeneratedScene: React.FC<{ spec: GeneratedSceneSpec; fps: number }> = ({
  spec,
  fps,
}) => {
  const frame = useCurrentFrame();
  const { background, subject, textLayers, motion } = spec;
  // Lumen DESIGNED scenes (Increment 3): typed scenes route to the code-authored
  // compositions (LumenScenes.tsx); only legacy full-frame continues below.
  if (spec.sceneType) {
    return <LumenScene spec={spec} />;
  }

  // Entrance progress 0→1. Spring for the buttery default; linear fallback.
  const entranceDur = Math.max(1, Math.round(fps * 0.5));
  const progress =
    motion.easing === "spring"
      ? spring({ frame, fps, config: { damping: 18, stiffness: 120, mass: 0.9 } })
      : interpolate(frame, [0, entranceDur], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

  // Boundary fade-out at the tail (matches B-roll's ~67ms out).
  const fadeFrames = Math.max(1, Math.round(fps * 0.067));
  const fadeOut = interpolate(
    frame,
    [spec.durationInFrames - fadeFrames, spec.durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Entrance transform by type.
  let tx = 0;
  let ty = 0;
  let sc = 1;
  let entranceOpacity = 1;
  if (motion.entrance === "slide") tx = (1 - progress) * 140;
  else if (motion.entrance === "rise") ty = (1 - progress) * 140;
  else if (motion.entrance === "float") ty = (1 - progress) * 70;
  else if (motion.entrance === "scale") sc = 0.86 + 0.14 * progress;
  else if (motion.entrance === "fade") entranceOpacity = progress;

  // Background: "generated" = the subject image IS its own full-frame world
  // (no separate bg). gradient/solid paint a CSS background under a cutout.
  const fullFrame = background.kind === "generated";
  const colors =
    background.colors && background.colors.length >= 2
      ? background.colors
      : ["#2a2a33", "#141419"];
  const bgStyle =
    background.kind === "solid"
      ? colors[0] || "#141419"
      : `linear-gradient(155deg, ${colors[0]} 0%, ${colors[colors.length - 1]} 100%)`;

  const subjectScale = (subject.scale || 1) * sc;

  const subjectInner = subject.imageUrl ? (
    <SafeImg role="decoration" label="GeneratedScene.subject"
      src={resolveSrc(subject.imageUrl)}
      style={
        fullFrame
          ? { width: "100%", height: "100%", objectFit: "cover" }
          : {
              maxWidth: "82%",
              maxHeight: "64%",
              objectFit: "contain",
              filter: "drop-shadow(0 28px 64px rgba(0,0,0,0.5))",
            }
      }
    />
  ) : (
    // Placeholder until Sub-step 3 fills the generated still.
    <div
      style={{
        width: "58%",
        height: "38%",
        border: "3px dashed rgba(255,255,255,0.45)",
        borderRadius: 28,
      }}
    />
  );

  const subjectWrapped = (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transform: `translate(${tx}px, ${ty}px) scale(${subjectScale})`,
        opacity: entranceOpacity,
      }}
    >
      {subjectInner}
    </div>
  );

  const subjectMaybeBlurred = motion.motionBlur ? (
    <CameraMotionBlur samples={6} shutterAngle={180}>
      {subjectWrapped}
    </CameraMotionBlur>
  ) : (
    subjectWrapped
  );

  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity: fadeOut }}>
      {!fullFrame ? <AbsoluteFill style={{ background: bgStyle }} /> : null}
      {subjectMaybeBlurred}
      {textLayers.map((t, i) => (
        <GenSceneText key={`gst-${i}`} layer={t} progress={progress} />
      ))}
    </AbsoluteFill>
  );
};

export const GeneratedSceneLayer: React.FC<{
  items: GeneratedSceneSpec[];
  fps: number;
}> = ({ items, fps }) => (
  <>
    {items.map((scn, i) => (
      <Sequence
        key={`genscene-${i}`}
        from={scn.fromFrame}
        durationInFrames={scn.durationInFrames}
      >
        <GeneratedScene spec={scn} fps={fps} />
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
  const { caption, motionGraphics, textOverlays, fps, broll, tightCutOverlays, generatedScenes } = input;

  return (
    <SmoothGraphicsProvider enabled={input.smoothGraphics ?? false}>
    <MotionTokensProvider enabled={input.motionTokens ?? false}>
    <MotionBlurProvider
      enabled={input.motionBlur ?? false}
      samples={input.motionBlurSamples}
      shutterAngle={input.motionBlurShutterAngle}
    >
    <AbsoluteFill style={{ background: "transparent" }}>
      {/* B-roll cutaways render at the BOTTOM of the overlay z-stack —
          under captions, text overlays, and MGs. Each B-roll fills the
          ENTIRE canvas during its window (full-frame cutaway, standard
          short-form B-roll convention). The speaker frame rendered by
          FFmpeg below this alpha overlay is fully covered for the duration
          of every B-roll window. Captions auto-flip to "top" during B-roll
          windows so they remain readable over the cutaway content. */}
      <BrollLayer items={broll ?? []} fps={fps} />
      {/* Generated scenes — full-frame composed takeovers (gradient world +
          generated subject + kinetic text + motion). Same z-tier as B-roll
          (bottom of the overlay stack); captions/MGs render on top. Empty by
          default → zero DOM, identical to the pre-GeneratedScene pipeline. */}
      <GeneratedSceneLayer items={generatedScenes ?? []} fps={fps} />
      <TextOverlaysLayer
        overlays={textOverlays ?? []}
        // W1: caption-less renders are first-class — caption may be absent.
        // caption_match overlays mimic the caption style; with no caption
        // track they fall back to CleanCut styling (never a crash).
        captionStyle={caption?.style ?? "CleanCut"}
        captionExtraProps={caption?.extraProps}
        captionKeywords={caption?.keywords ?? []}
        fps={fps}
      />
      <MotionGraphicsLayer items={motionGraphics} fps={fps} />
      {/* Captions paint ABOVE the content-accent tier (text overlays + motion
          graphics) and BELOW only the tight-cut flash — readable over speaker,
          B-roll, accents, and any residual overlap. Captions are the dialogue
          itself and carry the legibility floor (solid box/scrim, ≥2px dark
          contour, or the tight anchor shadow from captions/shared/legibility.ts),
          so an editorial accent must never occlude speech. Zones are kept
          disjoint upstream (handler.py _force_caption_position_around_overlays
          clears captions out of any text_overlay zone), so with clearance live
          this reorder is pixel-identical — it is the safety net that keeps the
          dialogue legible on any residual clearing miss (wrapped/grown caption,
          edge overlap). Previously this layer sat UNDER text-overlays + MGs,
          contradicting this very comment. */}
      {caption ? <CaptionsLayer caption={caption} fps={fps} /> : null}
      {/* Tight-cut overlays render on TOP of every other layer. The flash /
          warm leak briefly washes through captions + MGs at the cut frame,
          masking the hard-cut discontinuity. Outside each 11-frame window
          the components return null (no z-stack cost). */}
      <TightCutOverlayLayer overlays={tightCutOverlays ?? []} />
    </AbsoluteFill>
    </MotionBlurProvider>
    </MotionTokensProvider>
    </SmoothGraphicsProvider>
  );
};

// ─── PromptlyMicroSegments composition ─────────────────────────────────────
// Renders ONLY the windows that FFmpeg can't replicate without visual drift:
//   - Every transition (CardSwipe, FilmStrip,
//     LightLeak, etc. — all 11 use bespoke React/CSS that has no faithful
//     FFmpeg analog).
//   - Composite-effect zoom clips (FocusWindow, LetterboxPush, DepthPull —
//     multi-layer overlays, blur masks, bokeh orbs, etc.).
// Pure scale-only zooms (SmoothPush, SnapReframe, StepZoom) and no-zoom clips
// are produced directly by FFmpeg in handler.py.
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
    // D2: this composition renders ONLY transitions + composite zoom moves —
    // every segment here IS motion — so the blur provider gates it too. OFF
    // (default) → MotionBlurWrap is a passthrough → byte-identical.
    // ResprungZooms gates the SnapReframe/FocusWindow settle (default OFF →
    // today's clamped pixels); the zoom clips mount below via ClipRenderer.
    <SmoothGraphicsProvider enabled={input.smoothGraphics ?? false}>
    <ResprungZoomsProvider enabled={input.resprungZooms ?? false}>
    <MotionBlurProvider
      enabled={input.motionBlur ?? false}
      samples={input.motionBlurSamples}
      shutterAngle={input.motionBlurShutterAngle}
    >
    <AbsoluteFill style={{ background: "#000" }}>
      {segments.map((seg, i) => (
        <Sequence
          key={`micro-${i}`}
          from={seg.outputStartFrame}
          durationInFrames={seg.durationInFrames}
        >
          {seg.type === "transition" && seg.transition ? (
            <MotionBlurWrap>
              <TransitionRenderer
                transition={seg.transition}
                sourceUrl={resolvedSourceUrl}
              />
            </MotionBlurWrap>
          ) : null}
          {seg.type === "zoom_clip" && seg.clip ? (
            <MotionBlurWrap>
              <ClipRenderer clip={seg.clip} sourceUrl={resolvedSourceUrl} />
            </MotionBlurWrap>
          ) : null}
        </Sequence>
      ))}
    </AbsoluteFill>
    </MotionBlurProvider>
    </ResprungZoomsProvider>
    </SmoothGraphicsProvider>
  );
};

