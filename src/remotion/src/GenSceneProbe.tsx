import React from "react";
import { AbsoluteFill, OffthreadVideo, staticFile, useVideoConfig } from "remotion";
import { GeneratedSceneLayer } from "./PromptlyRender";
import type { GeneratedSceneSpec } from "./types";

/**
 * GenSceneProbe — Lumen Increment-1 proof composition (Zac 2026-07-16).
 * Renders the REAL GeneratedSceneLayer (the exact production component:
 * background world → subject <Img> → kinetic text → spring entrance inside
 * <CameraMotionBlur samples=6>) with a locally-staged generated subject still,
 * so Zac's eye judges the finished composited MOTION — not a bare image.
 * Not used in production; driven by --props.
 *
 * Wave-3: optional `sourceSrc` renders a constructed source clip UNDER the
 * scene layer (the reel shape: source plays, a designed scene takes over,
 * source returns). fps comes from the composition (the LumenReel registration
 * runs this at the canonical 30fps; the legacy probe registration stays 60).
 */
export interface GenSceneProbeProps {
  scenes: GeneratedSceneSpec[];
  label?: string;
  sourceSrc?: string;
}

export const GenSceneProbe: React.FC<GenSceneProbeProps> = ({ scenes, label, sourceSrc }) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: "#0c0c10" }}>
      {sourceSrc ? (
        <OffthreadVideo
          src={/^[a-z][a-z0-9+.-]*:/i.test(sourceSrc) ? sourceSrc : staticFile(sourceSrc)}
          muted
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      ) : null}
      <GeneratedSceneLayer items={scenes} fps={fps} />
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
};
