import React from "react";
import { Composition } from "remotion";
import { CaptionOverlay } from "./CaptionOverlay";
import type { CaptionInput } from "./types";

/**
 * Remotion root — registers the CaptionOverlay composition.
 * Input props are passed via the render CLI.
 */
export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="CaptionOverlay"
        component={CaptionOverlay}
        width={1080}
        height={1920}
        fps={30}
        durationInFrames={300}
        defaultProps={{
          input: {
            words: [],
            style: "captions_dynamic",
            width: 1080,
            height: 1920,
            fps: 30,
            durationInFrames: 300,
            keywords: [],
            fontDir: "/assets/fonts",
          } satisfies CaptionInput,
        }}
      />
    </>
  );
};
