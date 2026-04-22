import React from "react";
import { AbsoluteFill } from "remotion";

// Non-clickable absolute layer used by color effects to stack blend-mode
// overlays above their children. Pointer events disabled so the wrapper never
// steals interaction in the Remotion preview.
export const ColorEffectLayer: React.FC<{
  children?: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ children, style }) => {
  return (
    <AbsoluteFill style={{ pointerEvents: "none", ...style }}>
      {children}
    </AbsoluteFill>
  );
};
