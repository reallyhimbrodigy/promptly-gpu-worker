import React from "react";
import { AbsoluteFill, interpolate } from "remotion";

export interface ShutterFlashOverlayProps {
  progress: number;
  flashColor?: string;
}

/**
 * ShutterFlashOverlay — DECORATION-ONLY variant of ShutterFlash.
 *
 * Decoupled from clipA / clipB. Renders the CRT/shutter flash decoration
 * (white wash, horizontal beam, central dot) on a TRANSPARENT background.
 * Whatever the underlying composition shows during the overlay's frame
 * range plays through unaltered — except briefly washed by the flash at
 * peak progress, which is the desired "snap" effect on top of a hard cut.
 *
 * Visual shape:
 *   0 → 0.42   white flash ramps in, beam appears
 *   0.42 → 0.58 peak: white wash + bright dot at center
 *   0.58 → 1   white fades out, beam fades out
 *
 * The original ShutterFlash's screen-collapse effect needed both clipA and
 * clipB scaled to zero at peak; that mechanic is dropped here. The flash
 * does the work of masking the cut underneath without warping either clip.
 */
export const ShutterFlashOverlay: React.FC<ShutterFlashOverlayProps> = ({
  progress,
  flashColor = "#ffffff",
}) => {
  // White wash peak dropped 0.95 → 0.82 (2026-06-15) — at 0.95 the speaker
  // was a near-invisible silhouette through the wash on real talking-head
  // footage, which risks reading as a glitch/blowout rather than an
  // intentional camera-flash punch. 0.82 keeps the speaker perceptible
  // THROUGH the flash. Plateau width (0.42-0.58) preserved — the entire
  // plateau is flattened to 0.82 so 0.82 is the true maximum (a partial
  // change to just the center 0.5 value would have inverted the curve
  // since shoulders sat at 0.85). Plateau widening is a separate pass if
  // 0.82 still feels too brief.
  const washOpacity = interpolate(
    progress,
    [0.0, 0.42, 0.5, 0.58, 1.0],
    [0.0, 0.82, 0.82, 0.82, 0.0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Horizontal beam — visible during the wash ramp/fall.
  const beamOpacity = interpolate(
    progress,
    [0.15, 0.42, 0.58, 0.85],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Central glow dot — peaks at the moment the wash is brightest.
  const dotOpacity = interpolate(
    progress,
    [0.36, 0.5, 0.64],
    [0, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {washOpacity > 0.001 && (
        <AbsoluteFill
          style={{
            background: flashColor,
            opacity: washOpacity,
            pointerEvents: "none",
          }}
        />
      )}

      {beamOpacity > 0.001 && (
        <AbsoluteFill
          style={{
            pointerEvents: "none",
            opacity: beamOpacity,
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
