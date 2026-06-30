import React from "react";

// Classic arrow pointer; tip (hotspot) at the SVG origin (0,0).
const ARROW_PATH = "M0 0 L0 24 L7 17.5 L11.5 27 L15 25.5 L10.5 16 L19 16 Z";

export const CursorArrow: React.FC<{ size: number }> = ({ size }) => {
  const W = 22;
  const H = 30;
  return (
    <svg
      width={size}
      height={(size * H) / W}
      viewBox={`0 0 ${W} ${H}`}
      style={{
        display: "block",
        overflow: "visible",
        filter: "drop-shadow(0 2px 6px rgba(0,0,0,0.55))",
      }}
    >
      <path
        d={ARROW_PATH}
        fill="#FFFFFF"
        stroke="#0A0A0A"
        strokeWidth={2.4}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
};
