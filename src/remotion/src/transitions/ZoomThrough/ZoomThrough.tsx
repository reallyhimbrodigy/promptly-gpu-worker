import React from "react";
import { AbsoluteFill, interpolate, Easing, OffthreadVideo } from "remotion";
import type { ZoomThroughProps } from "../types";

export const ZoomThrough: React.FC<ZoomThroughProps> = ({
  clipA, clipB, progress, style,
  startFromA, startFromB, playbackRateA = 1, playbackRateB = 1,
}) => {
  const ease = Easing.bezier(0.32, 0.72, 0, 1);

  const scaleA = interpolate(progress, [0, 0.6], [1, 3], { easing: ease, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const opacityA = interpolate(progress, [0.2, 0.55], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const scaleB = interpolate(progress, [0.3, 1], [0.6, 1], { easing: Easing.out(Easing.cubic), extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const opacityB = interpolate(progress, [0.3, 0.6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#000", ...style }}>
      <AbsoluteFill style={{ transform: `scale(${scaleB})`, opacity: opacityB }}>
        <OffthreadVideo src={clipB} startFrom={startFromB} playbackRate={playbackRateB} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </AbsoluteFill>
      {opacityA > 0.01 && (
        <AbsoluteFill style={{ transform: `scale(${scaleA})`, opacity: opacityA }}>
          <OffthreadVideo src={clipA} startFrom={startFromA} playbackRate={playbackRateA} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
