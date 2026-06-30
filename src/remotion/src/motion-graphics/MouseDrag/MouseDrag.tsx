import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import { CursorArrow } from "./cursor";
import type { MouseDragProps } from "./types";

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);
const easeInOutCubic = (t: number): number =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const clamp01 = (x: number): number => Math.max(0, Math.min(1, x));

const CURSOR_SIZE = 46;

export const MouseDrag: React.FC<MouseDragProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  label,
  cardColor = "#F2C211",
  cardTextColor = "#1C1C1C",
  regionWidth = 720,
  regionHeight = 360,
  showCursor = true,
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center" },
  );
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 30, defaultExitFrames: 16 },
  );

  if (!visible) return null;

  const lf = localFrame;
  const cx = regionWidth / 2;
  const cy = regionHeight / 2;
  const START_X = cx + 880; // off the right edge, card already "held"
  const START_Y = cy + 380; // and lower, so the drag rises diagonally from bottom-right

  // --- Card drags in from the bottom-right, then drops into place ---
  const dragP = easeInOutCubic(clamp01((lf - 10) / 54));
  let cardCenterX: number;
  if (lf <= 64) {
    cardCenterX = START_X + (cx - START_X) * dragP;
  } else {
    const overshoot = interpolate(
      clamp01((lf - 64) / 18),
      [0, 0.45, 1],
      [0, -9, 0],
      { easing: easeOutCubic },
    );
    cardCenterX = cx + overshoot;
  }
  const cardCenterY = lf <= 64 ? START_Y + (cy - START_Y) * dragP : cy;

  const cardScale = interpolate(
    lf,
    [0, 10, 16, 64, 74, 82],
    [0.96, 0.96, 1.04, 1.04, 0.98, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  // Held card tilts toward travel (leftward), settles flat on drop.
  const cardRot = interpolate(lf, [0, 16, 60, 74, 82], [0, -4, -4, -1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const cardOpacity = interpolate(lf, [6, 16], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // Lifted (big shadow) while dragging, shrinks to resting on drop.
  const lift = interpolate(lf, [6, 14, 66, 80], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const sy = 10 + 6 * lift;
  const sb = 30 + 14 * lift;
  const sa = 0.35 + 0.1 * lift;
  const cardShadow = `0 ${sy.toFixed(1)}px ${sb.toFixed(1)}px rgba(0,0,0,${sa.toFixed(3)})`;

  // --- Cursor: on the card during the drag, then arcs back off right ---
  // The return bows upward so the move never reads as a robotic reverse.
  const RETURN_X = cx + 940;
  const retRaw = clamp01((lf - 82) / 50);
  const retP = easeInOutCubic(retRaw);
  const returnArc = -120 * Math.sin(retRaw * Math.PI);
  const cursorTipX = cardCenterX + (RETURN_X - cx) * retP;
  const cursorTipY = cardCenterY + 6 + returnArc;
  const cursorClick = interpolate(lf, [60, 66, 72], [1, 0.9, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // --- Card exit: the instant the cursor has arced back off-frame, the card
  // dematerializes in its wake. Driven off the return timeline (not the clip
  // end) so it fades right when the mouse leaves rather than holding first.
  // It lifts up-and-right after the cursor, swells a touch, softens with blur,
  // and dissolves under a feathered diagonal sweep angled along the exit. ---
  const dissolveStart = 82 + 50 * 0.7; // cursor is essentially off-frame here
  const dRaw = clamp01((lf - dissolveStart) / 34);
  const dissolveP = easeOutCubic(dRaw); // quick release, gentle dissipating tail
  const exitOpacity = 1 - exitProgress; // group-level safety fade at clip end

  // Feathered diagonal wipe (~104deg, following the cursor's up-right exit).
  // The mid stop gives a graded edge so it dissolves instead of hard-wiping.
  const wipeBand = 48; // % softness of the dissolving edge
  const wipeP1 = dissolveP * (100 + wipeBand);
  const wipeP0 = wipeP1 - wipeBand;
  const wipeMid = wipeP0 + wipeBand * 0.55;
  const cardMask =
    dRaw > 0
      ? `linear-gradient(104deg, transparent ${wipeP0.toFixed(1)}%, rgba(0,0,0,0.4) ${wipeMid.toFixed(1)}%, #000 ${wipeP1.toFixed(1)}%)`
      : undefined;

  // The card dissolves in place: it swells a touch and softens, no drift.
  const dissolveScale = 1 + 0.05 * dissolveP;
  const dissolveBlur = 6 * dissolveP;

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            position: "relative",
            width: regionWidth,
            height: regionHeight,
          }}
        >
          {/* 1. Dragged card */}
          <div
            style={{
              position: "absolute",
              left: cardCenterX,
              top: cardCenterY,
              transform: `translate(-50%, -50%) scale(${(cardScale * dissolveScale).toFixed(3)}) rotate(${cardRot.toFixed(2)}deg)`,
              transformOrigin: "center",
              opacity: cardOpacity,
              padding: "22px 40px",
              borderRadius: 14,
              background: cardColor,
              boxShadow: cardShadow,
              whiteSpace: "nowrap",
              filter: dissolveBlur > 0.01 ? `blur(${dissolveBlur.toFixed(2)}px)` : undefined,
              maskImage: cardMask,
              WebkitMaskImage: cardMask,
            }}
          >
            <span
              style={{
                fontFamily: MG_FONTS.inter,
                fontSize: 46,
                fontWeight: 800,
                color: cardTextColor,
                letterSpacing: "0.01em",
                lineHeight: 1,
              }}
            >
              {label}
            </span>
          </div>

          {/* 2. Arrow cursor (tip = hotspot at the SVG origin) */}
          {showCursor ? (
            <div
              style={{
                position: "absolute",
                left: cursorTipX,
                top: cursorTipY,
                transform: `scale(${cursorClick.toFixed(3)})`,
                transformOrigin: "0 0",
                opacity: exitOpacity,
              }}
            >
              <CursorArrow size={CURSOR_SIZE} />
            </div>
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};
