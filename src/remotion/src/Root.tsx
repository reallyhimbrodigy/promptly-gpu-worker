import React from "react";
import { Composition } from "remotion";
import { PromptlyOverlay, PromptlyMicroSegments, PromptlyBlendRender } from "./PromptlyRender";
import type {
  PromptlyRenderInput,
  PromptlyMicroSegmentsInput,
} from "./types";

/**
 * Remotion root — THREE production compositions:
 *
 *   PromptlyOverlay      — captions + motion graphics + text overlays on a
 *                          TRANSPARENT canvas. ProRes 4444 (alpha) so FFmpeg
 *                          can composite it onto the base. Used for the v62
 *                          FFmpeg-base architecture (default path).
 *   PromptlyMicroSegments — segmented Remotion-only render covering the
 *                          windows that can't be reproduced faithfully in
 *                          FFmpeg: every transition (11 types) and the
 *                          composite-effect zoom clips (FocusWindow,
 *                          LetterboxPush, DepthPull). h264 (no alpha).
 *   PromptlyBlendRender  — full Remotion composition (clips + transitions +
 *                          zoom + B-roll + captions + MG + text overlays +
 *                          outro). h264. Used ONLY when the chosen
 *                          caption_style is one of the blend-mode styles
 *                          (GlitchHighlight, NegativeFlash, Prism) which
 *                          require video pixels underneath the captions to
 *                          blend against. Bypasses the FFmpeg-base + alpha-
 *                          overlay split for those renders.
 *
 * Default path: FFmpeg builds the base video (clip cuts, simple zoom, B-roll,
 * outro fade), Remotion renders PromptlyOverlay (alpha) + PromptlyMicroSegments
 * (transitions, complex zooms) in parallel, then a single ffmpeg pass
 * composites everything.
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
    style: "PaperII",
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
      <Composition
        id="PromptlyBlendRender"
        component={PromptlyBlendRender as unknown as React.FC<Record<string, unknown>>}
        width={DEFAULT_RENDER_INPUT.width}
        height={DEFAULT_RENDER_INPUT.height}
        fps={DEFAULT_RENDER_INPUT.fps}
        durationInFrames={DEFAULT_RENDER_INPUT.totalDurationInFrames}
        defaultProps={{ input: DEFAULT_RENDER_INPUT } as unknown as Record<string, unknown>}
        calculateMetadata={calculateOverlayMetadata}
      />
    </>
  );
};
