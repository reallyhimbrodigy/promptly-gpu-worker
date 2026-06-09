import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { useMGPhase } from "../shared/useMGPhase";
import type {
  RecordingFrameAnnotation,
  RecordingFrameProps,
} from "./types";

const DEFAULT_ANNOTATIONS: RecordingFrameAnnotation[] = [
  { label: "ELAPSED", value: "timestamp", corner: "top-left" },
  { label: "WORDS", value: "wordcount", corner: "top-right" },
  { label: "RATE", value: "wpm", corner: "bottom-left" },
  { label: "SIG", value: "ACTIVE", corner: "bottom-right" },
];

const cornerToStyle = (
  corner: RecordingFrameAnnotation["corner"],
): React.CSSProperties => {
  const base: React.CSSProperties = { position: "absolute" };
  switch (corner) {
    case "top-left":
      base.top = 40;
      base.left = 40;
      break;
    case "top-right":
      base.top = 40;
      base.right = 40;
      break;
    case "bottom-left":
      base.bottom = 40;
      base.left = 40;
      break;
    case "bottom-right":
      base.bottom = 40;
      base.right = 40;
      break;
  }
  return base;
};

export const RecordingFrame: React.FC<RecordingFrameProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  accentColor = "#F0EEE9",
  textColor = "#F0EEE9",
  annotationFontSize = 24,
  showFrame = true,
  frameBorderColor = "rgba(240,238,233,0.08)",
  showScanLine = false,
  scanLineColor = "rgba(240,238,233,0.4)",
  scanLineCycle = 90,
  annotations = DEFAULT_ANNOTATIONS,
}) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 8, defaultExitFrames: 8 },
  );

  if (!visible) return null;

  const enterOpacity = interpolate(localFrame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exitOpacity = 1 - exitProgress;
  const overlayOpacity = enterOpacity * exitOpacity;

  const scanY = interpolate(
    frame % scanLineCycle,
    [0, scanLineCycle],
    [0, height],
  );

  const elapsedSeconds = Math.max(0, localFrame) / fps;

  const resolveValue = (raw: string): string => {
    if (raw === "timestamp") {
      return `T+${elapsedSeconds.toFixed(1)}s`;
    }
    if (raw === "wordcount") {
      return String(Math.floor(elapsedSeconds * 2));
    }
    if (raw === "wpm") {
      const wpm =
        elapsedSeconds > 0.3 ? Math.round(120 + elapsedSeconds * 8) : 0;
      return String(Math.min(220, wpm));
    }
    return raw;
  };

  return (
    <AbsoluteFill style={{ opacity: overlayOpacity }}>
      {showFrame ? (
        <div
          style={{
            position: "absolute",
            top: 30,
            left: 30,
            right: 30,
            bottom: 30,
            border: `1px solid ${frameBorderColor}`,
            pointerEvents: "none",
          }}
        />
      ) : null}

      {showScanLine ? (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: 2,
            background: `linear-gradient(to right, transparent, ${scanLineColor}, transparent)`,
            boxShadow: `0 0 12px 4px ${scanLineColor}`,
            transform: `translateY(${scanY}px)`,
            pointerEvents: "none",
          }}
        />
      ) : null}

      {annotations.map((a, i) => (
        <div key={i} style={cornerToStyle(a.corner)}>
          <div
            style={{
              fontFamily: MG_FONTS.jetBrainsMono,
              fontSize: annotationFontSize * 0.75,
              fontWeight: 400,
              color: `${textColor}80`,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              lineHeight: 1.4,
            }}
          >
            {a.label}
          </div>
          <div
            style={{
              fontFamily: MG_FONTS.jetBrainsMono,
              fontSize: annotationFontSize,
              fontWeight: 500,
              color: accentColor,
              letterSpacing: "0.02em",
              lineHeight: 1.2,
            }}
          >
            {resolveValue(a.value)}
          </div>
        </div>
      ))}
    </AbsoluteFill>
  );
};
