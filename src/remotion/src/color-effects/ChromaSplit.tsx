import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { useColorPhase } from "./shared";
import type { ColorTimingMode } from "./shared";

export interface ChromaSplitProps {
  children: React.ReactNode;
  // Peak pixel offset at full intensity. Default 14.
  offset?: number;
  // Angle in degrees the split moves along. Default 0 (horizontal).
  angle?: number;
  // Animate the split direction with a slow drift. Default true.
  drift?: boolean;
  intensity?: number;
  timing?: ColorTimingMode;
}

// RGB channel split (anamorphic / analog monitor vibe). Three stacked copies
// of the footage with isolated red, green, blue channels shifted apart.
// Restrained by default — single-digit pixel offset + slow drift.
export const ChromaSplit: React.FC<ChromaSplitProps> = ({
  children,
  offset = 14,
  angle = 0,
  drift = true,
  intensity = 1,
  timing = { mode: "persistent" },
}) => {
  const frame = useCurrentFrame();
  const { intensity: k } = useColorPhase(timing, {
    baseIntensity: intensity,
    defaultAttackFrames: 3,
    defaultHoldFrames: 6,
    defaultReleaseFrames: 8,
    defaultFadeInFrames: 12,
  });

  const driftAngle = drift ? angle + Math.sin(frame / 28) * 6 : angle;
  const rad = (driftAngle * Math.PI) / 180;
  const dx = Math.cos(rad) * offset * k;
  const dy = Math.sin(rad) * offset * k;

  return (
    <AbsoluteFill>
      {/* Green baseline sits center */}
      <AbsoluteFill style={{ filter: `url(#chroma-split-g)` }}>
        {children}
      </AbsoluteFill>

      {/* Red channel, shifted +dx, screen blend */}
      <AbsoluteFill
        style={{
          transform: `translate(${dx}px, ${dy}px)`,
          filter: `url(#chroma-split-r)`,
          mixBlendMode: "screen",
          pointerEvents: "none",
        }}
      >
        {children}
      </AbsoluteFill>

      {/* Blue channel, shifted -dx, screen blend */}
      <AbsoluteFill
        style={{
          transform: `translate(${-dx}px, ${-dy}px)`,
          filter: `url(#chroma-split-b)`,
          mixBlendMode: "screen",
          pointerEvents: "none",
        }}
      >
        {children}
      </AbsoluteFill>

      {/* SVG channel isolator filters */}
      <svg
        width="0"
        height="0"
        style={{ position: "absolute" }}
        aria-hidden
      >
        <filter id="chroma-split-r">
          <feColorMatrix
            type="matrix"
            values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0"
          />
        </filter>
        <filter id="chroma-split-g">
          <feColorMatrix
            type="matrix"
            values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0"
          />
        </filter>
        <filter id="chroma-split-b">
          <feColorMatrix
            type="matrix"
            values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0"
          />
        </filter>
      </svg>
    </AbsoluteFill>
  );
};
