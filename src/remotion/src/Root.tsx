import React from "react";
import { Composition } from "remotion";
import { PromptlyBase, PromptlyOverlay } from "./PromptlyRender";
import type { PromptlyRenderInput } from "./types";

/**
 * Remotion root — TWO production compositions for the two-renderer split:
 *
 *   PromptlyBase      — source video + transitions + zoom + B-roll. Black
 *                       background. Encoded as h264 (no alpha).
 *   PromptlyOverlay   — captions + motion graphics + text overlays on a
 *                       TRANSPARENT canvas. Encoded as ProRes 4444 (alpha)
 *                       so FFmpeg can overlay it on the base.
 *
 * Both compositions share the same input shape (PromptlyRenderInput); each
 * one just ignores the fields it doesn't render. handler.py launches both
 * in parallel via render-full.mjs --composition <id> and FFmpeg composites
 * the alpha overlay onto the base in the final mux step.
 *
 * Per-frame paint cost in each composition is dramatically lower than the
 * old monolithic PromptlyRender — base has no caption/MG/text-overlay paint,
 * overlay has no video paint. Combined render time drops from ~150s to
 * ~12-18s on H100 (encoder-bound on libx264 ultrafast).
 */

const DEFAULT_INPUT: PromptlyRenderInput = {
  sourceUrl: "",
  fps: 30,
  width: 1080,
  height: 1920,
  totalDurationInFrames: 300,
  clips: [],
  transitions: [],
  broll: [],
  caption: {
    style: "HormoziPopIn",
    pages: [],
    keywords: [],
    positionSegments: [{ fromFrame: 0, toFrame: 300, position: "bottom" }],
  },
  textOverlays: [],
  motionGraphics: [],
  outro: "none",
};

const calculateMetadata = ({ props }: { props: unknown }) => {
  const i = (props as { input: PromptlyRenderInput }).input;
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
        id="PromptlyBase"
        component={PromptlyBase as unknown as React.FC<Record<string, unknown>>}
        width={DEFAULT_INPUT.width}
        height={DEFAULT_INPUT.height}
        fps={DEFAULT_INPUT.fps}
        durationInFrames={DEFAULT_INPUT.totalDurationInFrames}
        defaultProps={{ input: DEFAULT_INPUT } as unknown as Record<string, unknown>}
        calculateMetadata={calculateMetadata}
      />
      <Composition
        id="PromptlyOverlay"
        component={PromptlyOverlay as unknown as React.FC<Record<string, unknown>>}
        width={DEFAULT_INPUT.width}
        height={DEFAULT_INPUT.height}
        fps={DEFAULT_INPUT.fps}
        durationInFrames={DEFAULT_INPUT.totalDurationInFrames}
        defaultProps={{ input: DEFAULT_INPUT } as unknown as Record<string, unknown>}
        calculateMetadata={calculateMetadata}
      />
    </>
  );
};
