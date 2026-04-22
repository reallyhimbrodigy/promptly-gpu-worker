import React from "react";
import { AbsoluteFill, interpolate, Easing, OffthreadVideo } from "remotion";
import type { ShutterFlashProps } from "../types";

export const SHUTTER_FLASH_PEAK_PROGRESS = 0.5;

/**
 * ShutterFlash — CRT TV power-off → power-on transition.
 *
 * The picture of clip A collapses vertically into a thin horizontal beam,
 * the beam contracts horizontally into a single bright dot, the dot
 * briefly blooms and fades. Then clip B powers on in reverse: dot opens
 * into a horizontal beam, beam opens vertically into the full picture.
 *
 * Phases:
 *   0 → 0.28    vertical collapse (scaleY → ~0)
 *   0.28 → 0.42 horizontal collapse (scaleX → ~0)
 *   0.42 → 0.58 bright dot holds + fades (mid-transition)
 *   0.58 → 0.72 clip B horizontal expand (scaleX → 1)
 *   0.72 → 1    clip B vertical expand (scaleY → 1)
 */
export const ShutterFlash: React.FC<ShutterFlashProps> = ({
  clipA,
  clipB,
  progress,
  style,
  flashColor = "#ffffff",
  // `blades`, `bladeColor`, `chromaticAberrationOnReveal` kept on the
  // interface for API compat but unused in this CRT effect.
  startFromA,
  startFromB,
  playbackRateA = 1,
  playbackRateB = 1,
}) => {
  const LINE_THICKNESS = 0.006;
  const DOT_SIZE_X = 0.015;

  const VCOLLAPSE_END = 0.28;
  const HCOLLAPSE_END = 0.42;
  const DOT_MID = 0.5;
  const HEXPAND_START = 0.58;
  const HEXPAND_END = 0.72;

  const aScaleY = interpolate(
    progress,
    [0, VCOLLAPSE_END],
    [1, LINE_THICKNESS],
    {
      easing: Easing.bezier(0.72, 0, 0.9, 1),
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );
  const aScaleX = interpolate(
    progress,
    [VCOLLAPSE_END, HCOLLAPSE_END],
    [1, DOT_SIZE_X],
    {
      easing: Easing.bezier(0.5, 0, 0.9, 1),
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );
  const aOpacity = interpolate(progress, [HCOLLAPSE_END, DOT_MID], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // Phosphor-glow brightness boost as the picture compresses
  const aBrightness = interpolate(
    progress,
    [0, VCOLLAPSE_END, HCOLLAPSE_END],
    [1, 1.35, 2],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const bOpacity = interpolate(progress, [DOT_MID, HEXPAND_START], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const bScaleX = interpolate(
    progress,
    [HEXPAND_START, HEXPAND_END],
    [DOT_SIZE_X, 1],
    {
      easing: Easing.bezier(0.1, 0, 0.3, 1),
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );
  const bScaleY = interpolate(progress, [HEXPAND_END, 1], [LINE_THICKNESS, 1], {
    easing: Easing.bezier(0.1, 0, 0.3, 1),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const bBrightness = interpolate(
    progress,
    [HEXPAND_START, HEXPAND_END, 1],
    [2, 1.35, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const dotOpacity = interpolate(
    progress,
    [HCOLLAPSE_END - 0.06, DOT_MID, HEXPAND_START + 0.06],
    [0, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const beamOpacity = interpolate(
    progress,
    [
      VCOLLAPSE_END - 0.06,
      VCOLLAPSE_END + 0.02,
      HCOLLAPSE_END,
      HCOLLAPSE_END + 0.04,
    ],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const beamOpacityB = interpolate(
    progress,
    [
      HEXPAND_START - 0.04,
      HEXPAND_START + 0.02,
      HEXPAND_END,
      HEXPAND_END + 0.04,
    ],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const totalBeamOpacity = Math.max(beamOpacity, beamOpacityB);

  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#000", ...style }}>
      {aOpacity > 0.01 && (
        <AbsoluteFill
          style={{
            transform: `scaleX(${aScaleX}) scaleY(${aScaleY})`,
            transformOrigin: "center center",
            opacity: aOpacity,
            filter: `brightness(${aBrightness})`,
            willChange: "transform, filter",
          }}
        >
          <OffthreadVideo
            src={clipA}
            startFrom={startFromA}
            playbackRate={playbackRateA}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </AbsoluteFill>
      )}

      {bOpacity > 0.01 && (
        <AbsoluteFill
          style={{
            transform: `scaleX(${bScaleX}) scaleY(${bScaleY})`,
            transformOrigin: "center center",
            opacity: bOpacity,
            filter: `brightness(${bBrightness})`,
            willChange: "transform, filter",
          }}
        >
          <OffthreadVideo
            src={clipB}
            startFrom={startFromB}
            playbackRate={playbackRateB}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </AbsoluteFill>
      )}

      {totalBeamOpacity > 0.001 && (
        <AbsoluteFill
          style={{
            pointerEvents: "none",
            opacity: totalBeamOpacity,
            mixBlendMode: "screen",
          }}
        >
          <div
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              top: "50%",
              height: 4,
              transform: "translateY(-50%)",
              background: `linear-gradient(90deg,
                transparent 0%,
                ${flashColor}33 10%,
                ${flashColor} 50%,
                ${flashColor}33 90%,
                transparent 100%)`,
              boxShadow: `0 0 24px 4px ${flashColor}66`,
              filter: "blur(1px)",
            }}
          />
        </AbsoluteFill>
      )}

      {dotOpacity > 0.001 && (
        <AbsoluteFill
          style={{
            pointerEvents: "none",
            opacity: dotOpacity,
            mixBlendMode: "screen",
          }}
        >
          <div
            style={{
              position: "absolute",
              left: "50%",
              top: "50%",
              width: 28,
              height: 28,
              transform: "translate(-50%, -50%)",
              borderRadius: "50%",
              background: flashColor,
              boxShadow: [
                `0 0 40px 10px ${flashColor}`,
                `0 0 100px 30px ${flashColor}aa`,
                `0 0 220px 60px ${flashColor}55`,
              ].join(", "),
            }}
          />
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
