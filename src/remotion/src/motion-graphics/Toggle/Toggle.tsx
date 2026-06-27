import React from "react";
import {
  interpolate,
  interpolateColors,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { SPRING_SNAPPY } from "../shared/springs";
import { MG_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import type { ToggleProps } from "./types";


export const Toggle: React.FC<ToggleProps> = ({
  startMs,
  durationMs,
  text,
  activateAtMs = 400,
  fontSize = 72,
  toggleScale = 1.5,
  offColor = "#D1D5DB",
  onColor = "#3B82F6",
  labelColor = "#FFFFFF",
  knobColor = "#FFFFFF",
  top = "12%",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const appearFrame = msToFrames(startMs, fps);
  const activateFrame = msToFrames(startMs + activateAtMs, fps);
  const disappearFrame = msToFrames(startMs + durationMs, fps);

  if (frame < appearFrame) return null;
  if (frame > disappearFrame + 8) return null;

  const fadeIn = interpolate(
    frame,
    [appearFrame, appearFrame + 6],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const fadeOut = interpolate(
    frame,
    [disappearFrame, disappearFrame + 8],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const isActivated = frame >= activateFrame;
  const toggleSpring = isActivated
    ? spring({
        fps,
        frame: frame - activateFrame,
        config: SPRING_SNAPPY,
      })
    : 0;

  const trackW = 120 * toggleScale;
  const trackH = 64 * toggleScale;
  const knobSize = 56 * toggleScale;
  const knobGap = 4 * toggleScale;
  const knobTravel = trackW - knobSize - knobGap * 2;

  const knobLeft = interpolate(
    toggleSpring,
    [0, 1],
    [knobGap, knobGap + knobTravel],
  );
  const trackColor = interpolateColors(
    toggleSpring,
    [0, 1],
    [offColor, onColor],
  );

  return (
    <div
      style={{
        position: "absolute",
        top,
        // [horizontal-center] structural — hardcoded 50% + translateX(-50%) so
        // Toggle can NEVER render off-center, regardless of any passed prop.
        left: "50%",
        transform: "translateX(-50%)",
        display: "flex",
        alignItems: "center",
        opacity: Math.min(fadeIn, fadeOut),
      }}
    >
      <div
        style={{
          fontFamily: MG_FONTS.inter,
          fontSize,
          fontWeight: 700,
          color: labelColor,
          marginRight: 100,
          textShadow: "0 2px 10px rgba(0,0,0,0.4)",
          whiteSpace: "nowrap",
        }}
      >
        {text}
      </div>

      <div
        style={{
          width: trackW,
          height: trackH,
          borderRadius: trackH / 2,
          backgroundColor: trackColor,
          position: "relative",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: knobSize,
            height: knobSize,
            borderRadius: knobSize / 2,
            backgroundColor: knobColor,
            position: "absolute",
            top: knobGap,
            left: knobLeft,
            boxShadow: "0 2px 6px rgba(0,0,0,0.2)",
          }}
        />
      </div>
    </div>
  );
};
