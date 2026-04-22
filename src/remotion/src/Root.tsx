import React from "react";
import { Composition } from "remotion";
import { PromptlyRender } from "./PromptlyRender";
import type { PromptlyRenderInput } from "./types";

/**
 * Remotion root — ONE production composition.
 *
 * Runtime dimensions (width/height/fps/durationInFrames) are driven entirely
 * by the `input` prop via `calculateMetadata`, so Python can render any
 * length/resolution without re-registering compositions.
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

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="PromptlyRender"
      component={PromptlyRender as unknown as React.FC<Record<string, unknown>>}
      width={DEFAULT_INPUT.width}
      height={DEFAULT_INPUT.height}
      fps={DEFAULT_INPUT.fps}
      durationInFrames={DEFAULT_INPUT.totalDurationInFrames}
      defaultProps={{ input: DEFAULT_INPUT } as unknown as Record<string, unknown>}
      calculateMetadata={({ props }) => {
        const i = (props as unknown as { input: PromptlyRenderInput }).input;
        return {
          width: i.width,
          height: i.height,
          fps: i.fps,
          durationInFrames: Math.max(1, i.totalDurationInFrames),
        };
      }}
    />
  );
};
