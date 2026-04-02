import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";
import type { VisualEffect } from "./types";

/**
 * BlurCard — Full-frame heavy Gaussian blur with sharp text overlaid.
 *
 * Observed in V4: entire video goes extremely blurry, sharp white text
 * sits on top at center for dramatic emphasis. Creates a "text card
 * over blurred video" effect.
 *
 * Since we're rendering as a transparent overlay and can't actually blur
 * the underlying video from Remotion, we render a semi-transparent dark
 * frosted-glass overlay + large sharp text. The actual video blur is
 * handled by FFmpeg's boxblur filter at the corresponding timestamps.
 *
 * params.text: the text to display (use \n for line break)
 * params.color: text color (default: white)
 * params.bgOpacity: background overlay opacity (default: 0.7)
 */
export const BlurCard: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const t = frame / fps;

  const start = effect.start;
  const end = effect.end;
  if (t < start || t > end) return null;

  const duration = end - start;
  const progress = (t - start) / duration;

  const text = (effect.params?.text as string) || "";
  const color = (effect.params?.color as string) || "#FFFFFF";
  const bgOpacity = (effect.params?.bgOpacity as number) || 0.7;

  // Fade envelope
  const fadeIn = interpolate(progress, [0, 0.15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(progress, [0.85, 1], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = fadeIn * fadeOut;
  if (opacity <= 0) return null;

  // Spring entrance for text
  const age = Math.max(0, frame - Math.round(start * fps));
  const entranceSpring = spring({
    frame: age,
    fps,
    config: { damping: 14, stiffness: 180, mass: 0.6 },
  });
  const textScale = interpolate(entranceSpring, [0, 1], [0.85, 1]);

  const lines = text.split("\n").filter((l) => l.trim());
  const fontSize = Math.round(width * 0.1);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        opacity,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        willChange: "opacity",
      }}
    >
      {/* Dark frosted overlay */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundColor: `rgba(0,0,0,${bgOpacity})`,
          backdropFilter: "blur(30px)",
          WebkitBackdropFilter: "blur(30px)",
        }}
      />

      {/* Sharp text on top */}
      <div
        style={{
          position: "relative",
          zIndex: 1,
          transform: `scale(${textScale.toFixed(3)})`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "12px",
          padding: "0 5%",
          willChange: "transform",
        }}
      >
        {lines.map((line, i) => (
          <div
            key={i}
            style={{
              fontSize,
              fontFamily: "Montserrat",
              fontWeight: 800,
              color,
              textAlign: "center",
              textTransform: "uppercase",
              lineHeight: 1.15,
              textShadow: `0 0 ${Math.round(fontSize * 0.12)}px ${color}60, 0 4px 16px rgba(0,0,0,0.5)`,
              WebkitTextStroke: "1.5px rgba(0,0,0,0.6)",
              letterSpacing: "0.02em",
            }}
          >
            {line}
          </div>
        ))}
      </div>
    </div>
  );
};
