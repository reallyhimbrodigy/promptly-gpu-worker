import React from "react";
import { AbsoluteFill } from "remotion";

interface CaptionContainerProps {
  position?: "top" | "center" | "bottom";
  children: React.ReactNode;
}

const POSITION_STYLES: Record<
  "top" | "center" | "bottom",
  React.CSSProperties
> = {
  top: {
    justifyContent: "flex-start",
    paddingTop: 160,
  },
  center: {
    justifyContent: "center",
  },
  bottom: {
    justifyContent: "flex-end",
    paddingBottom: 200,
  },
};

export const CaptionContainer: React.FC<CaptionContainerProps> = ({
  position = "bottom",
  children,
}) => {
  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        ...POSITION_STYLES[position],
        padding: "0 60px",
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
