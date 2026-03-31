import React from "react";
import { Composition } from "remotion";
import { VideoOverlay } from "./VideoOverlay";
import { CaptionOverlay } from "./CaptionOverlay";
import type { OverlayInput, CaptionInput } from "./types";

/**
 * Remotion root — registers compositions.
 * VideoOverlay: captions + all visual effects in one pass (primary)
 * CaptionOverlay: captions only (legacy fallback)
 */
export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* Primary composition: captions + visual effects */}
      <Composition
        id="VideoOverlay"
        component={VideoOverlay}
        width={1080}
        height={1920}
        fps={30}
        durationInFrames={300}
        defaultProps={{
          input: {
            words: [],
            captionStyle: "captions_dynamic",
            keywords: [],
            effects: [],
            cuts: [],
            emphasisMoments: [],
            width: 1080,
            height: 1920,
            fps: 30,
            duration: 10,
            durationInFrames: 300,
            fontDir: "/assets/fonts",
            vibe: "",
          } satisfies OverlayInput,
        }}
      />
      {/* Legacy: captions only */}
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
