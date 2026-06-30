import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { NumberTickerProps } from "./types";


const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);
const clamp01 = (x: number): number => Math.max(0, Math.min(1, x));

const DIGIT_SIZE = 84;
const AFFIX_SIZE = 66;
const AFFIX_GAP = 8;
const ROLL_START = 8;
const COIN_SIZE = 58;

const DEFAULT_TEXT_SHADOW =
  "0 2px 10px rgba(0,0,0,0.7), 0 1px 2px rgba(0,0,0,0.55)";

// Insert thousands separators deterministically (no locale dependence).
const group3 = (s: string): string => s.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

// A dimensional silver coin — metallic radial sheen, rim depth, specular
// highlight and an embossed "$". Drawn (not an emoji) so it reads premium.
const Coin: React.FC<{ size: number }> = ({ size }) => {
  const uid = React.useId().replace(/:/g, "");
  const faceId = `ntCoinFace-${uid}`;
  const rimId = `ntCoinRim-${uid}`;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      style={{ display: "block", filter: "drop-shadow(0 3px 5px rgba(0,0,0,0.45))" }}
    >
      <defs>
        <radialGradient id={faceId} cx="36%" cy="30%" r="82%">
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="50%" stopColor="#E4E8EE" />
          <stop offset="100%" stopColor="#B7BDC6" />
        </radialGradient>
        <linearGradient id={rimId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#EFF1F4" />
          <stop offset="100%" stopColor="#8B919B" />
        </linearGradient>
      </defs>
      <circle cx="24" cy="24" r="22.5" fill={`url(#${rimId})`} />
      <circle cx="24" cy="24" r="18" fill={`url(#${faceId})`} />
      <circle cx="24" cy="24" r="18" fill="none" stroke="#FFFFFF" strokeWidth="1.1" opacity="0.6" />
      <circle cx="24" cy="24" r="13.4" fill="none" stroke="#8B919B" strokeWidth="1.2" opacity="0.5" />
      <path
        d="M24 14 V34 M29.5 18 c-1.3-1.5-3.4-2.2-5.5-2.2 h-0.6 a3.4 3.4 0 0 0 0 6.8 h2.6 a3.4 3.4 0 0 1 0 6.8 h-0.6 c-2.1 0-4.2-0.7-5.5-2.2"
        fill="none"
        stroke="#6B7178"
        strokeWidth="2.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <ellipse
        cx="18"
        cy="16.5"
        rx="7"
        ry="3.6"
        fill="#FFFFFF"
        opacity="0.4"
        transform="rotate(-28 18 16.5)"
      />
    </svg>
  );
};

export const NumberTicker: React.FC<NumberTickerProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  value,
  fromValue = 0,
  prefix,
  suffix,
  icon = "none",
  decimals = 0,
  grouping = true,
  live = true,
  accentColor = "#FFFFFF",
  digitColor = "#FFFFFF",
  chip = true,
  chipColor = "rgba(17,19,25,0.30)",
  rollFrames = 46,
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "top-right", offsetX: -56, offsetY: 132 },
  );
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 22, defaultExitFrames: 16 },
  );

  if (!visible) return null;

  const decimalsSafe = Math.max(0, Math.floor(decimals));
  const targetAbs = Math.abs(value);
  const fromAbs = Math.abs(fromValue);
  const ROLL_END = ROLL_START + rollFrames;
  const tCount = clamp01((localFrame - ROLL_START) / rollFrames);

  // Count value. For a count up from ~zero we ramp the MAGNITUDE linearly
  // (log-space) so each new figure spawns at an even pace and the number lands
  // crisply on the exact target. Otherwise we ease the value directly.
  const countUpFromZero =
    fromAbs < 1 && targetAbs >= 10 && value >= fromValue;
  let currentAbs: number;
  if (localFrame <= ROLL_START) {
    currentAbs = fromAbs;
  } else if (tCount >= 1) {
    currentAbs = targetAbs;
  } else if (countUpFromZero) {
    currentAbs = Math.pow(10, Math.log10(targetAbs) * tCount);
  } else {
    currentAbs = fromAbs + (targetAbs - fromAbs) * easeOutCubic(tCount);
  }

  const fixed = currentAbs.toFixed(decimalsSafe);
  const dotIndex = fixed.indexOf(".");
  const intRaw = dotIndex >= 0 ? fixed.slice(0, dotIndex) : fixed;
  const fracRaw = dotIndex >= 0 ? fixed.slice(dotIndex + 1) : "";
  const intStr = grouping ? group3(intRaw) : intRaw;
  const numStr = decimalsSafe > 0 ? `${intStr}.${fracRaw}` : intStr;
  const sign = value < 0 ? "−" : "";

  // Entrance — fade in + a slight slide up, in step with the count starting.
  const enterOpacity = interpolate(localFrame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const enterY = interpolate(localFrame, [0, 18], [22, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });

  // When the count lands, the pill "drops" — a quick scale pop (bigger then
  // back to rest), position unchanged — so it reads as set down and planted.
  const dropPop = interpolate(
    localFrame,
    [ROLL_END, ROLL_END + 4, ROLL_END + 12],
    [1, 1.09, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Cool, simple fade-out — fade + a hair of scale-down, position holds.
  const exitOpacity = 1 - exitProgress;
  const exitScale = interpolate(exitProgress, [0, 1], [1, 0.96]);

  const glyphStyle: React.CSSProperties = {
    fontFamily: MG_FONTS.oswald,
    fontSize: DIGIT_SIZE,
    fontWeight: 600,
    color: digitColor,
    lineHeight: 1,
    letterSpacing: "0.01em",
    fontVariantNumeric: "tabular-nums",
    textShadow,
    whiteSpace: "nowrap",
  };
  const affixStyle: React.CSSProperties = {
    fontFamily: MG_FONTS.oswald,
    fontSize: AFFIX_SIZE,
    fontWeight: 500,
    color: digitColor,
    opacity: 0.92,
    lineHeight: 1,
    fontVariantNumeric: "tabular-nums",
    textShadow,
  };

  const pillStyle: React.CSSProperties = chip
    ? {
        padding: "26px 50px",
        borderRadius: 999,
        background: `linear-gradient(180deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0) 46%), ${chipColor}`,
        backdropFilter: "blur(22px) saturate(150%)",
        WebkitBackdropFilter: "blur(22px) saturate(150%)",
        border: "2px solid rgba(255,255,255,0.30)",
        boxShadow: `0 10px 28px rgba(0,0,0,0.42), 0 28px 66px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.25)${
          live ? `, 0 0 22px ${accentColor}18` : ""
        }`,
      }
    : {};

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            transform: `translateY(${enterY.toFixed(2)}px) scale(${(dropPop * exitScale).toFixed(4)})`,
            transformOrigin: "center",
            opacity: enterOpacity * exitOpacity,
            display: "flex",
            flexDirection: "row",
            alignItems: "center",
            ...pillStyle,
          }}
        >
          {/* Optional leading icon (built-in premium SVG) */}
          {icon === "coin" ? (
            <div style={{ display: "flex", marginRight: 16, flexShrink: 0 }}>
              <Coin size={COIN_SIZE} />
            </div>
          ) : null}

          {/* Sign + prefix + number + suffix — one tight group so the prefix
              always hugs the leftmost digit and is pushed out as it grows. */}
          {sign ? <span style={{ ...glyphStyle, marginRight: 2 }}>{sign}</span> : null}
          {prefix ? (
            <span style={{ ...affixStyle, marginRight: AFFIX_GAP }}>{prefix}</span>
          ) : null}
          <span style={glyphStyle}>{numStr}</span>
          {suffix ? (
            <span style={{ ...affixStyle, marginLeft: AFFIX_GAP }}>{suffix}</span>
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};
