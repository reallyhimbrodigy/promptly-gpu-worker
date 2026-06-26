import type React from "react";
import {
  SAFE_RECT,
  CANVAS_WIDTH,
  TIKTOK_SAFE_TOP,
  TIKTOK_SAFE_RIGHT,
  TIKTOK_SAFE_BOTTOM,
  TIKTOK_SAFE_SIDE,
} from "../../shared/safeZone";

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

// TikTok-safe positioning. The flex container's padding IS the platform-safe
// rect (single source of truth in src/shared/safeZone.ts): every anchor —
// edges AND center — resolves INSIDE x∈[80,880], y∈[270,1500] on the
// 1080×1920 canvas, clear of the top header, the right action rail, and the
// bottom caption/nav drawer. This replaces the old cosmetic ~60/80px edge
// insets, which assumed the whole frame was usable and let content bleed
// under the platform UI.
//
// Gemini controls only the anchor + offsets + scale. We make it impossible
// for any of those to place content into an unsafe zone:
//   (1) padding box → the anchor itself is always inside the safe rect;
//   (2) offset clamp → a supplied offset cannot drag content back across a
//       safe boundary (component-author default offsets land inside the rect
//       already, so they pass through untouched);
//   (3) max-width/height + scale≤1 → a large or enlarged component cannot
//       overflow the rect even when correctly anchored.

const clampNum = (v: number, lo: number, hi: number): number =>
  Math.max(lo, Math.min(hi, v));

// Clamp an effective offset into the safe-travel range for its anchor. The
// anchored reference point is kept within the central band of the safe rect
// (half the safe extent in any direction), which both blocks a Gemini offset
// from crossing a boundary AND leaves the component's body room to extend
// toward the opposite edge without bleeding out. Author default offsets
// (e.g. the SpeechBubble family's offsetY 720–820) sit inside this range and
// are unaffected.
function clampOffsetForAnchor(
  anchor: MGAnchor,
  dx: number,
  dy: number,
): { dx: number; dy: number } {
  const halfW = SAFE_RECT.width / 2;
  const halfH = SAFE_RECT.height / 2;
  const isTop =
    anchor === "top" || anchor === "top-left" || anchor === "top-right";
  const isBottom =
    anchor === "bottom" ||
    anchor === "bottom-left" ||
    anchor === "bottom-right";
  const isLeft =
    anchor === "left" || anchor === "top-left" || anchor === "bottom-left";
  const isRight =
    anchor === "right" || anchor === "top-right" || anchor === "bottom-right";

  if (isTop) dy = clampNum(dy, 0, halfH);
  else if (isBottom) dy = clampNum(dy, -halfH, 0);
  else dy = clampNum(dy, -halfH, halfH);

  if (isLeft) dx = clampNum(dx, 0, halfW);
  else if (isRight) dx = clampNum(dx, -halfW, 0);
  else dx = clampNum(dx, -halfW, halfW);

  return { dx, dy };
}

// ---------------------------------------------------------------------------
// Per-type positioning policy — SINGLE SOURCE OF TRUTH.
// ---------------------------------------------------------------------------
//   centerColumn: ignore the anchor's horizontal component — force the MG into
//     the center column. Text/number/UI cards must never side-anchor.
//   topExempt:    render at the TRUE top like a real OS notification — opt out
//     of the safe-zone top + bottom padding AND the centering rule; full-width
//     minus the action rail. (Notification intentionally overlaps TikTok's own
//     clock — that's the notification-mimic look, not a bug.)
//
// Types ABSENT here keep default behavior (anchor honored, inside the safe
// rect). StickyNotes + Toggle self-center (left:50% + translateX(-50%)) and
// never route through resolveMGPosition; AnnotationArrow (points at a target)
// and RecordingFrame (full-frame border) are intentionally free-positioned.
export interface MGPositionConfig {
  centerColumn?: boolean;
  topExempt?: boolean;
}

export const MG_POSITION_CONFIG: Record<string, MGPositionConfig> = {
  StatCard: { centerColumn: true },
  ChatThread: { centerColumn: true },
  ProgressBar: { centerColumn: true },
  TweetBubble: { centerColumn: true },
  InstagramComment: { centerColumn: true },
  IMessageBubble: { centerColumn: true },
  TikTokComment: { centerColumn: true },
  Notification: { topExempt: true },
};

// Notification's container top inset is 0 — the component supplies its own
// small top offset (platform topOffset ≈ 24) so the banner lands at ~y=24.
const NOTIFICATION_TOP_INSET = 0;

// Resolve the user-provided position props into container + wrapper styles.
// `defaults` lets each component pick its own sensible default anchor/offset.
// `mgType` (optional) selects the per-type policy above.
export function resolveMGPosition(
  props: MGPositionProps | undefined,
  defaults: { anchor?: MGAnchor; offsetX?: number; offsetY?: number } = {},
  mgType?: string,
): ResolvedPositioning {
  const cfg = (mgType && MG_POSITION_CONFIG[mgType]) || {};
  const anchor = props?.anchor ?? defaults.anchor ?? "center";
  const rawOffsetX = props?.offsetX ?? defaults.offsetX ?? 0;
  const rawOffsetY = props?.offsetY ?? defaults.offsetY ?? 0;
  // Scale may shrink (toward fitting the rect) but never enlarge past the
  // bounded box — an enlarging scale is the one way a correctly-anchored
  // component could still grow into a platform-UI zone.
  const scale = clampNum(props?.scale ?? 1, 0.1, 1);

  // (2) Clamp the offset so it cannot push content across a safe boundary.
  const { dx: clampedX, dy: clampedY } = clampOffsetForAnchor(
    anchor,
    rawOffsetX,
    rawOffsetY,
  );
  // Item 1: center-column types ignore any horizontal offset (forced center).
  const offsetX = cfg.centerColumn ? 0 : clampedX;
  const offsetY = clampedY;

  const flex = ANCHOR_FLEX[anchor];
  const transformOrigin = ANCHOR_ORIGIN[anchor];

  // Item 1: force horizontal center regardless of the anchor's horizontal part.
  const justifyContent = cfg.centerColumn ? "center" : flex.justifyContent;
  // Item 3 (topExempt): pin to the true top, full-width minus the rail, and
  // drop the top + bottom safe padding. Right-rail padding stays so a wide
  // banner can't run under the action buttons.
  const alignItems = cfg.topExempt ? "flex-start" : flex.alignItems;
  const paddingTop = cfg.topExempt ? NOTIFICATION_TOP_INSET : TIKTOK_SAFE_TOP;
  const paddingBottom = cfg.topExempt ? 0 : TIKTOK_SAFE_BOTTOM;
  // Item 1: centerColumn types use SYMMETRIC horizontal padding so the flex
  // center lands on the TRUE frame center (540), not the asymmetric safe-box
  // center (480 = midpoint of [80,880]). paddingLeft = paddingRight =
  // TIKTOK_SAFE_RIGHT (200) → box [200,880], midpoint 540, still clears the
  // right rail; maxWidth shrinks to the symmetric box width (680) so a wide
  // card can't overflow. Scoped to centerColumn only — other types keep the
  // 80/200 asymmetric padding + 800 maxWidth.
  const paddingLeft = cfg.topExempt
    ? 0
    : cfg.centerColumn
      ? TIKTOK_SAFE_RIGHT
      : TIKTOK_SAFE_SIDE;
  const maxWidth = cfg.topExempt
    ? CANVAS_WIDTH - TIKTOK_SAFE_RIGHT
    : cfg.centerColumn
      ? CANVAS_WIDTH - 2 * TIKTOK_SAFE_RIGHT
      : SAFE_RECT.width;

  return {
    containerStyle: {
      display: "flex",
      // Force row layout — AbsoluteFill defaults to column, which would
      // swap the meaning of alignItems/justifyContent. Row keeps the mental
      // model simple: justifyContent = horizontal, alignItems = vertical.
      flexDirection: "row",
      alignItems,
      justifyContent,
      // (1) The padded content box IS the TikTok-safe rect (topExempt types
      // override top/bottom/left to sit at the true top, full-width). box-
      // sizing keeps the padding inside the 1080×1920 AbsoluteFill. No
      // overflow:hidden — it would clip slide-in/out animations.
      boxSizing: "border-box",
      paddingTop,
      paddingRight: TIKTOK_SAFE_RIGHT,
      paddingBottom,
      paddingLeft,
    },
    wrapperStyle: {
      // (3) Bound the component so a wide or tall card cannot overflow even
      // when correctly anchored.
      maxWidth,
      maxHeight: SAFE_RECT.height,
      transform: `translate(${offsetX}px, ${offsetY}px) scale(${scale})`,
      transformOrigin,
    },
  };
}
