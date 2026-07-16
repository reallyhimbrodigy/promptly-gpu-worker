import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  staticFile,
} from "remotion";
import { SmoothPush } from "./zoom";

/**
 * ZoomEaseProbe — glide-vs-punch A/B (Zac 2026-07-15). Drives the REAL SmoothPush
 * component with the vibe-gated `punch` prop, over the sample clip, so the A/B is
 * the SHIPPED behavior (not a copy):
 *   punch=false (glide, ease-out) — motion front-loaded, gentle settle ON the word
 *   punch=true  (punch, ease-in)  — motion accelerates INTO the word, impact ON it
 * Both complete the SCALE on the word (SmoothPush peak_reach 420ms → the event start
 * is back-timed so rampIn == the word frame). A green border flashes for one frame at
 * the word onset so the eye sees the beat. Not used in production.
 */
export interface ZoomEaseProbeProps {
  punch: boolean;
  startMs: number;      // back-timed event start (word - peak_reach)
  durationMs: number;
  targetScale: number;
  wordMs: number;       // the anchor word onset (where the scale completes)
  label: string;
}

export const ZoomEaseProbe: React.FC<ZoomEaseProbeProps> = ({
  punch,
  startMs,
  durationMs,
  targetScale = 1.22,
  wordMs,
  label,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const wordFrame = Math.round((wordMs / 1000) * fps);
  const onWord = frame === wordFrame;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <SmoothPush
        src={staticFile("test_talking_head.mp4")}
        punch={punch}
        events={[
          { startMs, durationMs, scale: targetScale, originX: 0.5, originY: 0.42 },
        ]}
      />
      {onWord ? (
        <AbsoluteFill style={{ border: "16px solid #00FF88", boxSizing: "border-box" }} />
      ) : null}
      <div
        style={{
          position: "absolute",
          top: 44,
          left: 44,
          fontFamily: "monospace",
          fontSize: 42,
          fontWeight: 700,
          color: "#00FF88",
          background: "rgba(0,0,0,0.65)",
          padding: "8px 18px",
        }}
      >
        {label}
      </div>
    </AbsoluteFill>
  );
};
