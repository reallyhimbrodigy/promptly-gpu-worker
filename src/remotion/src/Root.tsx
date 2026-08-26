import React from "react";
import { Composition } from "remotion";
import {
  PromptlyOverlay,
  PromptlyMicroSegments,
} from "./PromptlyRender";
import type {
  PromptlyRenderInput,
  PromptlyMicroSegmentsInput,
} from "./types";
import { OverlayCutTest, type OverlayCutTestProps } from "./transitions/overlays/_OverlayCutTest";
import { FitSpecimen } from "./FitSpecimen";
import { MGAttackProbe } from "./MGAttackProbe";
import { CaptionFadeProbe } from "./CaptionFadeProbe";
import { StagedPushProbe } from "./StagedPushProbe";
import { SmoothPushProbe } from "./SmoothPushProbe";
import { CrossfadeProbe } from "./CrossfadeProbe";
import { ZoomTagProbe } from "./ZoomTagProbe";
import { ZoomEaseProbe } from "./ZoomEaseProbe";
import { GenSceneProbe } from "./GenSceneProbe";
import { FrameCompProbe } from "./FrameCompProbe";
import { MGCraftProbe } from "./MGCraftProbe";

/**
 * Remotion root — two production compositions:
 *
 *   PromptlyOverlay        — captions + motion graphics + text overlays on a
 *                            TRANSPARENT canvas. ProRes 4444 (alpha) so FFmpeg
 *                            can composite it onto the base. Captions render
 *                            here for every supported style; the FFmpeg
 *                            composite step lays this layer over the source
 *                            in a single encode.
 *   PromptlyMicroSegments  — segmented Remotion render covering windows that
 *                            can't be reproduced faithfully in FFmpeg
 *                            (transitions, composite-effect zoom clips).
 *                            ProRes 4444 lossless intermediate — composite
 *                            re-reads it without quality loss.
 *
 * Single composite pass merges source + overlay alpha + micro-segments + audio
 * into the final encoded output. No second video pass for any caption style.
 */

const DEFAULT_RENDER_INPUT: PromptlyRenderInput = {
  sourceUrl: "",
  fps: 60,
  width: 1080,
  height: 1920,
  totalDurationInFrames: 600,
  clips: [],
  transitions: [],
  broll: [],
  caption: {
    style: "CleanCut",
    pages: [],
    keywords: [],
    positionSegments: [{ fromFrame: 0, toFrame: 600, position: "bottom" }],
  },
  textOverlays: [],
  motionGraphics: [],
  outro: "none",
};

const DEFAULT_MICRO_INPUT: PromptlyMicroSegmentsInput = {
  sourceUrl: "",
  fps: 60,
  width: 1080,
  height: 1920,
  totalDurationInFrames: 1,
  segments: [],
};

const calculateOverlayMetadata = ({ props }: { props: unknown }) => {
  const i = (props as { input: PromptlyRenderInput }).input;
  return {
    width: i.width,
    height: i.height,
    fps: i.fps,
    durationInFrames: Math.max(1, i.totalDurationInFrames),
  };
};

const calculateMicroMetadata = ({ props }: { props: unknown }) => {
  const i = (props as { input: PromptlyMicroSegmentsInput }).input;
  return {
    width: i.width,
    height: i.height,
    fps: i.fps,
    durationInFrames: Math.max(1, i.totalDurationInFrames),
  };
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="PromptlyOverlay"
        component={PromptlyOverlay as unknown as React.FC<Record<string, unknown>>}
        width={DEFAULT_RENDER_INPUT.width}
        height={DEFAULT_RENDER_INPUT.height}
        fps={DEFAULT_RENDER_INPUT.fps}
        durationInFrames={DEFAULT_RENDER_INPUT.totalDurationInFrames}
        defaultProps={{ input: DEFAULT_RENDER_INPUT } as unknown as Record<string, unknown>}
        calculateMetadata={calculateOverlayMetadata}
      />
      <Composition
        id="PromptlyMicroSegments"
        component={PromptlyMicroSegments as unknown as React.FC<Record<string, unknown>>}
        width={DEFAULT_MICRO_INPUT.width}
        height={DEFAULT_MICRO_INPUT.height}
        fps={DEFAULT_MICRO_INPUT.fps}
        durationInFrames={DEFAULT_MICRO_INPUT.totalDurationInFrames}
        defaultProps={{ input: DEFAULT_MICRO_INPUT } as unknown as Record<string, unknown>}
        calculateMetadata={calculateMicroMetadata}
      />
      {/* OverlayCutTest — STANDALONE isolation test composition for the
          overlay-on-top-of-hard-cut transition path. Not used in production
          renders. Reachable via `npx remotion render OverlayCutTest --props='{...}'`
          to verify: (1) underlying frames advance with no freeze, (2) overlay
          renders ON TOP within its window, (3) total duration == 240 frames
          (no growth), (4) audio waveform identical across overlay variants
          (the overlay components have no audio outputs). */}
      <Composition
        id="OverlayCutTest"
        component={OverlayCutTest as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={60}
        durationInFrames={240}
        defaultProps={{
          overlayType: "none",
          overlayDurationInFrames: 18,
          withAudio: true,
        } as unknown as Record<string, unknown> & OverlayCutTestProps}
      />
      {/* FrameCompProbe — STANDALONE entrance/depth proof for the three
          generation-free frame comps. 1080x1920@30fps (production target).
          Driven by render-frame-comp-proof.mjs; renderStill across the entrance
          window. Not used in production renders. */}
      <Composition
        id="FrameCompProbe"
        component={FrameCompProbe as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={30}
        durationInFrames={60}
        defaultProps={{
          kind: "EmojiCard",
          spec: {},
          sourceUrl: "",
          motionBlur: true,
        } as unknown as Record<string, unknown>}
      />
      {/* MGCraftProbe — catalogue-pass render-proof (blur + smooth-graphics on a
          gray plate). 1080x1920@60fps to match MGAttackProbe's timing grid so
          before/after frames are directly comparable. Not used in production. */}
      <Composition
        id="MGCraftProbe"
        component={MGCraftProbe as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={60}
        durationInFrames={96}
        defaultProps={{
          type: "StatCard",
          props: {},
          motionBlur: true,
        } as unknown as Record<string, unknown>}
      />
      {/* MGCraftProbe30 — the SAME probe at production's 30fps. The 60fps grid
          masks the absolute-frame-schedule class (raw frame constants run 2x
          faster in real time and short live windows collide with exit) — pair
          this with durationMs = the live placement's window to prove those
          defects and their fixes. Not used in production. */}
      <Composition
        id="MGCraftProbe30"
        component={MGCraftProbe as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={30}
        durationInFrames={240}
        defaultProps={{
          type: "StatCard",
          props: {},
          motionBlur: true,
        } as unknown as Record<string, unknown>}
      />
      {/* FitSpecimen — STANDALONE F4 caption width-fit battery composition.
          Renders one style with a worst-case-string page over black, strict
          fit invariant armed. Driven by fit-battery.mjs; pixel-scanned by
          test_caption_fit.py. Not used in production renders. */}
      <Composition
        id="FitSpecimen"
        component={FitSpecimen as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={60}
        durationInFrames={120}
        defaultProps={{
          style: "Gadzhi",
          words: ["DOWNLOAD", "PROMPTLY"],
          keywords: [],
          position: "bottom",
        } as unknown as Record<string, unknown>}
      />
      {/* MGAttackProbe — WS1 entrance-arrival measurement. One MG type on a
          flat plate at startMs=0; driven by mg-attack-battery.mjs. Not used in
          production renders. 96 frames @60fps = 1.6s (entrance + hold). */}
      <Composition
        id="MGAttackProbe"
        component={MGAttackProbe as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={60}
        durationInFrames={96}
        defaultProps={{
          type: "StatCard",
          props: { value: 100000, label: "SUBSCRIBERS", anchor: "center" },
        } as unknown as Record<string, unknown>}
      />
      {/* CaptionFadeProbe — STANDALONE WS2 fade-bound sample (not used in
          production). One style on a fast-speech word track + a beat-pulse
          metronome; render before/after the fade-bound to compare on Zac's eye.
          Driven by caption-fade-battery.mjs. */}
      <Composition
        id="CaptionFadeProbe"
        component={CaptionFadeProbe as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={60}
        durationInFrames={220}
        defaultProps={{
          style: "CleanCut",
          words: ["this", "is", "the", "fastest", "way", "to", "grow", "your", "account", "right", "now", "today"],
          keywords: ["fastest", "grow"],
          wordMs: 170,
        } as unknown as Record<string, unknown>}
      />
      {/* StagedPushProbe — isolated LOOK test for the multi-stage emphasis zoom
          (StagedPush). Renders the staged push-in on the sample talking-head clip;
          driven by staged-push-battery.mjs. Not used in production. 300f@60 = 5s. */}
      <Composition
        id="StagedPushProbe"
        component={StagedPushProbe as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={60}
        durationInFrames={300}
        defaultProps={{
          events: [
            {
              stages: [
                { atMs: 1000, scale: 1.08 },
                { atMs: 1800, scale: 1.16 },
                { atMs: 2600, scale: 1.24 },
              ],
              cutTerminated: false,
            },
          ],
        } as unknown as Record<string, unknown>}
      />
      {/* StagedPushProbe30 — the SAME probe at the real DELIVERY format: 30fps.
          The 60fps probe above is a look-at-it harness, but every smoothness
          number must be read at 30fps, because per-frame displacement (the whole
          defect) HALVES at 60 — measuring the cap on the 60fps probe understates
          it by 2x. 150f@30 = 5s, the same 5 seconds as the probe above.
          Driven by velocity-cap-ab.mjs. Not used in production. */}
      <Composition
        id="StagedPushProbe30"
        component={StagedPushProbe as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={30}
        durationInFrames={150}
        defaultProps={{
          events: [
            {
              stages: [
                { atMs: 1000, scale: 1.08 },
                { atMs: 1800, scale: 1.16 },
                { atMs: 2600, scale: 1.24 },
              ],
              cutTerminated: false,
            },
          ],
        } as unknown as Record<string, unknown>}
      />
      {/* ZoomTagProbe — before/after for the OffthreadVideo -> @remotion/media
          <Video> migration. 90f@30 = 3s. Not used in production. */}
      <Composition
        id="ZoomTagProbe"
        component={ZoomTagProbe as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={30}
        durationInFrames={90}
        defaultProps={{
          component: "LetterboxPush",
          events: [{ startMs: 400, durationMs: 1400, scale: 1.25, originX: 0.5, originY: 0.45 }],
        } as unknown as Record<string, unknown>}
      />
      {/* CrossfadeProbe — proves a crossfade with ONE unloadable image layer
          still paints real frames (the survivor holds the window as a cut)
          instead of going black. 60f@30 = 2s. Not used in production. */}
      <Composition
        id="CrossfadeProbe"
        component={CrossfadeProbe as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={30}
        durationInFrames={60}
        defaultProps={{ clipA: "vcap_A.png", clipB: "vcap_B.png" } as unknown as Record<string, unknown>}
      />
      {/* SmoothPushProbe30 — the velocity-cap pair on the zoom that ACTUALLY
          SHIPS. SmoothPush is 48.6% of production zooms; StagedPush is 3 of
          1,542, so this is the arm the flip decision rests on. 30fps because
          per-frame displacement — the whole defect — halves at 60.
          180f@30 = 6s. Driven by velocity-cap-ab.mjs. Not used in production. */}
      <Composition
        id="SmoothPushProbe30"
        component={SmoothPushProbe as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={30}
        durationInFrames={180}
        defaultProps={{
          events: [
            { startMs: 1600, durationMs: 1200, scale: 1.22, originX: 0.5, originY: 0.42 },
          ],
        } as unknown as Record<string, unknown>}
      />
      {/* ZoomEaseProbe — glide-vs-punch A/B (Zac 2026-07-15). SmoothPush ramp
          completing on a word at 2.0s (frame 120); green flash = the word onset.
          Render easeDir "out" (glide) vs "in" (punch) to compare. 240f@60 = 4s. */}
      <Composition
        id="ZoomEaseProbe"
        component={ZoomEaseProbe as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={60}
        durationInFrames={240}
        defaultProps={{
          punch: false,
          startMs: 1580,     // 2000 - 420 (SmoothPush peak_reach) → scale completes at the word
          durationMs: 1200,
          targetScale: 1.22,
          wordMs: 2000,      // the anchor word onset (frame 120)
          label: "GLIDE (corporate)",
        } as unknown as Record<string, unknown>}
      />
      {/* GenSceneProbe — Lumen Increment-1: the REAL GeneratedSceneLayer
          (bg → subject → kinetic text → motion blur) on a staged subject still.
          Driven by --props; 240f@60 = 4s. Not used in production. */}
      <Composition
        id="GenSceneProbe"
        component={GenSceneProbe as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={60}
        durationInFrames={600}
        defaultProps={{
          scenes: [],
          label: "",
        } as unknown as Record<string, unknown>}
      />
      {/* LumenReel — Wave-3 scene reel (ephemeral modal app drives it): the
          REAL GeneratedSceneLayer over a constructed source, at the canonical
          30fps. Vertical 1080x1920 only. Not used in production. */}
      <Composition
        id="LumenReel"
        component={GenSceneProbe as unknown as React.FC<Record<string, unknown>>}
        width={1080}
        height={1920}
        fps={30}
        durationInFrames={360}
        defaultProps={{
          scenes: [],
          label: "",
          sourceSrc: "",
        } as unknown as Record<string, unknown>}
      />
    </>
  );
};
