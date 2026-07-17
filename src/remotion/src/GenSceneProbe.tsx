import React from "react";
import { AbsoluteFill } from "remotion";
import { GeneratedSceneLayer } from "./PromptlyRender";
import type { GeneratedSceneSpec } from "./types";

/**
 * GenSceneProbe — Lumen Increment-1 proof composition (Zac 2026-07-16).
 * Renders the REAL GeneratedSceneLayer (the exact production component:
 * background world → subject <Img> → kinetic text → spring entrance inside
 * <CameraMotionBlur samples=6>) with a locally-staged generated subject still,
 * so Zac's eye judges the finished composited MOTION — not a bare image.
 * Not used in production; driven by --props.
 */
export interface GenSceneProbeProps {
  scenes: GeneratedSceneSpec[];
  label?: string;
}

export const GenSceneProbe: React.FC<GenSceneProbeProps> = ({ scenes, label }) => (
  <AbsoluteFill style={{ backgroundColor: "#0c0c10" }}>
    <GeneratedSceneLayer items={scenes} fps={60} />
    {label ? (
      <div
        style={{
          position: "absolute",
          top: 40,
          left: 40,
          fontFamily: "monospace",
          fontSize: 38,
          fontWeight: 700,
          color: "#00FF88",
          background: "rgba(0,0,0,0.65)",
          padding: "6px 16px",
        }}
      >
        {label}
      </div>
    ) : null}
  </AbsoluteFill>
);
