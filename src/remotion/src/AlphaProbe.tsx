import React from "react";
import { AbsoluteFill, OffthreadVideo } from "remotion";

export const AlphaProbe: React.FC<{ alphaUrl: string }> = ({ alphaUrl }) => (
  <AbsoluteFill style={{ backgroundColor: "#FF0000" }}>
    <OffthreadVideo src={alphaUrl} transparent muted />
  </AbsoluteFill>
);
