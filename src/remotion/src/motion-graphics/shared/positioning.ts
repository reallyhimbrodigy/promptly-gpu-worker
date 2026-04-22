import type React from "react";

// ---------------------------------------------------------------------------
// Shared positioning / scale API for motion-graphic components.
// ---------------------------------------------------------------------------
//
// Any MG component that includes MGPositionProps in its type lets the client:
//   - `anchor`   : pick one of 9 preset anchor points on the 1080×1920 frame
//   - `offsetX`  : fine-tune horizontally in pixels (positive = right)
//   - `offsetY`  : fine-tune vertically in pixels (positive = down)
//   - `scale`    : scale the whole component uniformly (1 = 100%)
//
// The component places its content inside a flex AbsoluteFill using
// `containerStyle`, and wraps its own render in a div with `wrapperStyle`
// — that div handles the offset + scale + correct transform-origin so
// scaling always grows outward from the anchor, not off-screen.

export type MGAnchor =
  | "center"
  | "top"
  | "bottom"
  | "left"
  | "right"
  | "top-left"
  | "top-right"
  | "bottom-left"
  | "bottom-right";

export interface MGPositionProps {
  // Anchor preset on the 1080×1920 frame. Default depends on the component.
  anchor?: MGAnchor;
  // Pixel offset from the anchor. Positive x = right, positive y = down.
  offsetX?: number;
  offsetY?: number;
  // Uniform scale multiplier. 1 = 100% (default), 0.5 = half, 2 = double.
  scale?: number;
}

interface FlexAlign {
  alignItems: React.CSSProperties["alignItems"];
  justifyContent: React.CSSProperties["justifyContent"];
}

const ANCHOR_FLEX: Record<MGAnchor, FlexAlign> = {
  center: { alignItems: "center", justifyContent: "center" },
  top: { alignItems: "flex-start", justifyContent: "center" },
  bottom: { alignItems: "flex-end", justifyContent: "center" },
  left: { alignItems: "center", justifyContent: "flex-start" },
  right: { alignItems: "center", justifyContent: "flex-end" },
  "top-left": { alignItems: "flex-start", justifyContent: "flex-start" },
  "top-right": { alignItems: "flex-start", justifyContent: "flex-end" },
  "bottom-left": { alignItems: "flex-end", justifyContent: "flex-start" },
  "bottom-right": { alignItems: "flex-end", justifyContent: "flex-end" },
};

const ANCHOR_ORIGIN: Record<MGAnchor, string> = {
  center: "center",
  top: "top center",
  bottom: "bottom center",
  left: "center left",
  right: "center right",
  "top-left": "top left",
  "top-right": "top right",
  "bottom-left": "bottom left",
  "bottom-right": "bottom right",
};

export interface ResolvedPositioning {
  containerStyle: React.CSSProperties;
  wrapperStyle: React.CSSProperties;
}

// Resolve the user-provided position props into container + wrapper styles.
// `defaults` lets each component pick its own sensible default anchor/offset.
export function resolveMGPosition(
  props: MGPositionProps | undefined,
  defaults: { anchor?: MGAnchor; offsetX?: number; offsetY?: number } = {},
): ResolvedPositioning {
  const anchor = props?.anchor ?? defaults.anchor ?? "center";
  const offsetX = props?.offsetX ?? defaults.offsetX ?? 0;
  const offsetY = props?.offsetY ?? defaults.offsetY ?? 0;
  const scale = props?.scale ?? 1;

  const flex = ANCHOR_FLEX[anchor];
  const transformOrigin = ANCHOR_ORIGIN[anchor];

  return {
    containerStyle: {
      display: "flex",
      // Force row layout — AbsoluteFill defaults to column, which would
      // swap the meaning of alignItems/justifyContent. Row keeps the mental
      // model simple: justifyContent = horizontal, alignItems = vertical.
      flexDirection: "row",
      alignItems: flex.alignItems,
      justifyContent: flex.justifyContent,
    },
    wrapperStyle: {
      transform: `translate(${offsetX}px, ${offsetY}px) scale(${scale})`,
      transformOrigin,
    },
  };
}
