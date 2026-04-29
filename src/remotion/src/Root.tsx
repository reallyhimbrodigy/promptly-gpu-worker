import React from "react";
import { Composition } from "remotion";
import {
  PromptlyOverlay,
  PromptlyMicroSegments,
  PromptlyBlendCaptionsOnly,
} from "./PromptlyRender";
import type {
  PromptlyRenderInput,
  PromptlyMicroSegmentsInput,
  PromptlyBlendCaptionsOnlyInput,
} from "./types";

/**
 * Remotion root — three production compositions:
 *
 *   PromptlyOverlay           — captions + motion graphics + text overlays on
 *                               a TRANSPARENT canvas. ProRes 4444 (alpha) so
 *                               FFmpeg can composite it onto the base.
 *                               In blend-mode renders, handler.py zeroes out
 *                               caption.pages and filters caption_match text
 *                               overlays from this input — those are drawn
 *                               by PromptlyBlendCaptionsOnly in the second
 *                               pass instead.
 *   PromptlyMicroSegments     — segmented Remotion render covering windows
 *                               that can't be reproduced faithfully in
 *                               FFmpeg: every transition (11 types) and
 *                               composite-effect zoom clips. h264.
 *   PromptlyBlendCaptionsOnly — second pass for blend-mode caption styles
 *                               (GlitchHighlight, NegativeFlash, Prism).
 *                               Reads the v62 silent intermediate as
 *                               OffthreadVideo source and lays the blend-
 *                               mode captions + caption_match overlays on
 *                               top so the existing mixBlendMode CSS has
 *                               real frame content underneath. h264.
 *
 * v62 path always runs end-to-end first. Blend renders pay for one extra
 * Remotion pass on top; non-blend renders go straight from v62 to audio mux.
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

const DEFAULT_BLEND_CAPTIONS_INPUT: PromptlyBlendCaptionsOnlyInput = {
  videoUrl: "",
  fps: 60,
  width: 1080,
  height: 1920,
  totalDurationInFrames: 1,
  caption: {
    style: "GlitchHighlight",
    pages: [],
    keywords: [],
    positionSegments: [{ fromFrame: 0, toFrame: 1, position: "bottom" }],
  },
  captionMatchOverlays: [],
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

const calculateBlendCaptionsMetadata = ({ props }: { props: unknown }) => {
  const i = (props as { input: PromptlyBlendCaptionsOnlyInput }).input;
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
        id="PromptlyBlendCaptionsOnly"
        component={PromptlyBlendCaptionsOnly as unknown as React.FC<Record<string, unknown>>}
        width={DEFAULT_BLEND_CAPTIONS_INPUT.width}
        height={DEFAULT_BLEND_CAPTIONS_INPUT.height}
        fps={DEFAULT_BLEND_CAPTIONS_INPUT.fps}
        durationInFrames={DEFAULT_BLEND_CAPTIONS_INPUT.totalDurationInFrames}
        defaultProps={{ input: DEFAULT_BLEND_CAPTIONS_INPUT } as unknown as Record<string, unknown>}
        calculateMetadata={calculateBlendCaptionsMetadata}
      />
    </>
  );
};
