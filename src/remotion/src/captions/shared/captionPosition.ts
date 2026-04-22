export const CAPTION_PADDING = {
  top: 160,
  sides: 60,
  bottomSafe: 300,
  sidesSafe: 200,
} as const;

export function getCaptionPositionStyle(
  position: "top" | "center" | "bottom",
): React.CSSProperties {
  switch (position) {
    case "top":
      return {
        justifyContent: "flex-start",
        paddingTop: CAPTION_PADDING.top,
        paddingLeft: CAPTION_PADDING.sides,
        paddingRight: CAPTION_PADDING.sides,
      };
    case "bottom":
      return {
        justifyContent: "flex-end",
        paddingBottom: CAPTION_PADDING.bottomSafe,
        paddingLeft: CAPTION_PADDING.sidesSafe,
        paddingRight: CAPTION_PADDING.sidesSafe,
      };
    case "center":
    default:
      return {
        justifyContent: "center",
        paddingLeft: CAPTION_PADDING.sides,
        paddingRight: CAPTION_PADDING.sides,
      };
  }
}
