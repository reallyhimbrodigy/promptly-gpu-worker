import React from "react";
import { Composition } from "remotion";
import { PromptlyOverlay, PromptlyMicroSegments } from "./PromptlyRender";
import type {
  PromptlyRenderInput,
  PromptlyMicroSegmentsInput,
} from "./types";

/**
 * Remotion root — TWO production compositions for the FFmpeg-base architecture:
 *
 *   PromptlyOverlay      — captions + motion graphics + text overlays on a
 *                          TRANSPARENT canvas. ProRes 4444 (alpha) so FFmpeg
 *                          can composite it onto the base.
 *   PromptlyMicroSegments — segmented Remotion-only render covering the
 *                          windows that can't be reproduced faithfully in
 *                          FFmpeg: every transition (11 types) and the
 *                          composite-effect zoom clips (FocusWindow,
 *                          LetterboxPush, DepthPull). h264 (no alpha).
 *
 * The base video — clip cuts, simple zoom (SmoothPush / SnapReframe / StepZoom
 * / StageZoom), B-roll cutaways, outro fade — is built directly by FFmpeg in
 * handler.py with the zoom math ported to per-frame `crop` expressions, then
 * the FFmpeg-built segments + Remotion micro-segments + alpha overlay are
 * composited in a single final ffmpeg pass.
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
    </>
  );
};
