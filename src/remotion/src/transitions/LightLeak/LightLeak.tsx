import React from "react";
import { AbsoluteFill, interpolate, OffthreadVideo } from "remotion";
import type { LightLeakProps } from "../types";

export const LIGHT_LEAK_PEAK_PROGRESS = 0.5;

type PaletteKey = "warm" | "gold" | "cool" | "magenta";
type DirectionKey = "tl-br" | "tr-bl" | "left-right" | "top-down";

interface Palette {
  primary: string;
  secondary: string;
  highlight: string;
}

const PALETTES: Record<PaletteKey, Palette> = {
  warm: { primary: "#FF8A30", secondary: "#FFB870", highlight: "#FFE2B0" },
  gold: { primary: "#FFC93C", secondary: "#FFE070", highlight: "#FFF7C8" },
  cool: { primary: "#5BC8FF", secondary: "#A8DCFF", highlight: "#E0F2FF" },
  magenta: { primary: "#E64FA1", secondary: "#F593C5", highlight: "#FFD6EB" },
};

interface TranslationPath {
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
}

const getPaths = (
  direction: DirectionKey,
): { layer1: TranslationPath; layer2: TranslationPath } => {
  switch (direction) {
    case "tr-bl":
      return {
        layer1: { fromX: 50, fromY: -50, toX: -50, toY: 50 },
        layer2: { fromX: 30, fromY: -60, toX: -60, toY: 30 },
      };
    case "left-right":
      return {
        layer1: { fromX: -60, fromY: 0, toX: 60, toY: 0 },
        layer2: { fromX: -40, fromY: -15, toX: 70, toY: 15 },
      };
    case "top-down":
      return {
        layer1: { fromX: 0, fromY: -60, toX: 0, toY: 60 },
        layer2: { fromX: -15, fromY: -40, toX: 15, toY: 70 },
      };
    case "tl-br":
    default:
      return {
        layer1: { fromX: -50, fromY: -50, toX: 50, toY: 50 },
        layer2: { fromX: -30, fromY: -60, toX: 60, toY: 30 },
      };
  }
};

/**
 * LightLeak — a warm glow sweeps across the frame like sunlight hitting a
 * camera lens, bridging two clips. Three layered radial gradients with
 * screen / soft-light blend modes sell the filmic feel; the hard cut is
 * hidden at the peak of the brightest layer.
 */
export const LightLeak: React.FC<LightLeakProps> = ({
  clipA,
  clipB,
  progress,
  style,
  palette = "warm",
  direction = "tl-br",
  intensity = 1.0,
  startFromA,
  startFromB,
  playbackRateA = 1,
  playbackRateB = 1,
}) => {
  const pal = PALETTES[palette];
  const paths = getPaths(direction);

  const showClipB = progress >= LIGHT_LEAK_PEAK_PROGRESS;

  const l1X = interpolate(progress, [0, 1], [paths.layer1.fromX, paths.layer1.toX], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const l1Y = interpolate(progress, [0, 1], [paths.layer1.fromY, paths.layer1.toY], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const l1Opacity = interpolate(
    progress,
    [0, 0.5, 1],
    [0, 0.85 * intensity, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const l2X = interpolate(progress, [0, 1], [paths.layer2.fromX, paths.layer2.toX], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const l2Y = interpolate(progress, [0, 1], [paths.layer2.fromY, paths.layer2.toY], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const l2Opacity = interpolate(
    progress,
    [0.1, 0.55, 0.9],
    [0, 1.0 * intensity, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const washOpacity = interpolate(
    progress,
    [0.2, 0.5, 0.8],
    [0, 0.3 * intensity, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const grainOpacity = interpolate(
    progress,
    [0.1, 0.5, 0.9],
    [0, 0.08, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#000", ...style }}>
      {/* Active clip — swap at the peak of the glow so the cut is invisible. */}
      <AbsoluteFill>
        <OffthreadVideo
          src={showClipB ? clipB : clipA}
          startFrom={showClipB ? startFromB : startFromA}
          playbackRate={showClipB ? playbackRateB : playbackRateA}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>

      {washOpacity > 0.001 && (
        <AbsoluteFill
          style={{
            background: pal.secondary,
            mixBlendMode: "soft-light",
            opacity: washOpacity,
            pointerEvents: "none",
          }}
        />
      )}

      {l1Opacity > 0.001 && (
        <AbsoluteFill
          style={{
            mixBlendMode: "screen",
            opacity: l1Opacity,
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              position: "absolute",
              left: "-20%",
              top: "-20%",
              width: "140%",
              height: "140%",
              transform: `translate(${l1X}%, ${l1Y}%)`,
              background: `radial-gradient(circle at center, ${pal.primary} 0%, ${pal.primary}AA 30%, ${pal.primary}55 60%, transparent 100%)`,
              filter: "blur(40px)",
            }}
          />
        </AbsoluteFill>
      )}

      {l2Opacity > 0.001 && (
        <AbsoluteFill
          style={{
            mixBlendMode: "screen",
            opacity: l2Opacity,
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              position: "absolute",
              left: "20%",
              top: "20%",
              width: "60%",
              height: "60%",
              transform: `translate(${l2X}%, ${l2Y}%)`,
              background: `radial-gradient(circle at center, ${pal.highlight} 0%, ${pal.secondary}88 50%, transparent 100%)`,
              filter: "blur(28px)",
            }}
          />
        </AbsoluteFill>
      )}

      {grainOpacity > 0.001 && (
        <AbsoluteFill
          style={{
            mixBlendMode: "overlay",
            opacity: grainOpacity,
            pointerEvents: "none",
          }}
        >
          <svg
            width="100%"
            height="100%"
            xmlns="http://www.w3.org/2000/svg"
            style={{ display: "block" }}
          >
            <filter id="light-leak-grain">
              <feTurbulence
                type="fractalNoise"
                baseFrequency="0.9"
                numOctaves="2"
                stitchTiles="stitch"
              />
              <feColorMatrix type="saturate" values="0" />
            </filter>
            <rect width="100%" height="100%" filter="url(#light-leak-grain)" />
          </svg>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
