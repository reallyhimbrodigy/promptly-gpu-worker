import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { EchoOutroProps } from "./types";
import { useMGPhase } from "../shared/useMGPhase";

/**
 * The copy-free close. The footage keeps playing to its own last frame; this
 * lays the job's palette over the final seconds so the edit RESOLVES.
 *
 * NO TEXT, DELIBERATELY. A component with no copy cannot fabricate copy, and
 * that is the whole reason this one is universal where the copy-bearing card is
 * stuck at a measured 2.2%.
 *
 * ART_DIRECTION §6: "an end card running past the final cut is a black frame
 * with text on it." Placement is the handler's job (fromFrame /
 * durationInFrames), identical to NamePlate and EndCard — a component that also
 * placed itself would be doing the same math twice on two different clocks.
 */
export const EchoOutro: React.FC<EchoOutroProps> = ({
  startMs = 0,
  durationMs,
  tint,
  tintOpacity = 0.22,
  vignette = true,
  rule,
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  // Same phase helper every other MG uses, with the required defaults object.
  const { progress } = useMGPhase({ startMs, durationMs, fps, frame }, {
    enterMs: 420,
    exitMs: 0,
    holdMs: 0,
  });
  // Ramps IN and stays. The close does not un-resolve.
  const o = interpolate(progress, [0, 1], [0, tintOpacity], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const ruleW = interpolate(progress, [0, 1], [0, width * 0.38], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill style={{ backgroundColor: tint, opacity: o }} />
      {vignette ? (
        <AbsoluteFill
          style={{
            opacity: o,
            background:
              "radial-gradient(ellipse at center, rgba(0,0,0,0) 45%, rgba(0,0,0,0.55) 100%)",
          }}
        />
      ) : null}
      {rule ? (
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-end" }}>
          <div
            style={{
              width: ruleW,
              height: Math.max(2, Math.round(width * 0.004)),
              backgroundColor: rule,
              marginBottom: "12%",
              opacity: progress,
            }}
          />
        </AbsoluteFill>
      ) : null}
    </AbsoluteFill>
  );
};
