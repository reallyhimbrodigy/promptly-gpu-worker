import React from "react";
import { AbsoluteFill, interpolate, spring, useVideoConfig } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { StampFontKey, StampMark, StampProps, StampStyle } from "./types";


const easeInCubic = (t: number): number => t * t * t;

const DEFAULT_TEXT_SHADOW = "0 1px 2px rgba(0,0,0,0.35)";
const BADGE_SHADOW =
  "drop-shadow(0 6px 18px rgba(0,0,0,0.45)) drop-shadow(0 2px 4px rgba(0,0,0,0.35))";
const GRAIN =
  "repeating-linear-gradient(28deg, rgba(0,0,0,0.05) 0 1px, transparent 1px 3px)";

const STYLE_DEFAULTS: Record<
  StampStyle,
  { fontKey: StampFontKey; fontSize: number; mark: StampMark; distress: boolean; size: number }
> = {
  seal: { fontKey: "oswald", fontSize: 64, mark: "star", distress: false, size: 380 },
  stamp: { fontKey: "anton", fontSize: 84, mark: "none", distress: true, size: 440 },
  ribbon: { fontKey: "anton", fontSize: 72, mark: "none", distress: false, size: 520 },
};

const FONT_FAMILY: Record<StampFontKey, string> = {
  oswald: MG_FONTS.oswald,
  anton: MG_FONTS.anton,
  inter: MG_FONTS.inter,
};
const FONT_WEIGHT: Record<StampFontKey, number> = {
  oswald: 700,
  anton: 400,
  inter: 800,
};

const Star: React.FC<{ size: number; color: string }> = ({ size, color }) => (
  <svg width={size} height={size} viewBox="0 0 24 24">
    <path
      d="M12 3.2l2.6 5.27 5.81.84-4.2 4.1.99 5.79L12 16.9l-5.2 2.73.99-5.79-4.2-4.1 5.81-.84z"
      fill={color}
    />
  </svg>
);

const renderMark = (
  mark: StampMark,
  color: string,
  size: number,
): React.ReactNode => {
  if (mark === "none") return null;
  if (mark === "check") {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke={color}
        strokeWidth={3}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4.5 12.5l5 5 10-11" />
      </svg>
    );
  }
  if (mark === "stars") {
    return (
      <div style={{ display: "flex", gap: 8 }}>
        {[0, 1, 2].map((i) => (
          <Star key={i} size={size * 0.42} color={color} />
        ))}
      </div>
    );
  }
  return <Star size={size} color={color} />;
};

// Main word size in the rectangular-stamp viewBox (560 wide).
const rectFontFit = (len: number): number =>
  len <= 6 ? 122 : len <= 8 ? 104 : len <= 10 ? 88 : len <= 12 ? 74 : 64;

export const Stamp: React.FC<StampProps> = (props) => {
  const style = props.style ?? "seal";
  const d = STYLE_DEFAULTS[style];
  const {
    startMs,
    durationMs,
    enterFrames,
    exitFrames,
    text,
    subtextTop,
    subtextBottom,
    mark = d.mark,
    color = "#C8321F",
    textColor,
    markColor,
    rotation = -9,
    entryScale = 1.28,
    fontKey = d.fontKey,
    fontSize: fontSizeProp,
    size = d.size,
    doubleRing = true,
    distress = d.distress,
    textShadow = DEFAULT_TEXT_SHADOW,
    anchor,
    offsetX,
    offsetY,
    scale,
  } = props;

  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center" },
  );
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 30, defaultExitFrames: 16 },
  );
  const uid = React.useId().replace(/:/g, "");
  const { fps } = useVideoConfig();

  if (!visible) return null;

  const ink = textColor ?? color;
  const markInk = markColor ?? color;
  const restRot = rotation;

  // --- Bounce-in press: a springy scale settle (overshoots, then lands) ---
  const press = spring({
    fps,
    frame: localFrame,
    config: { damping: 10, mass: 0.8, stiffness: 150 },
  });
  const appear = interpolate(press, [0, 1], [entryScale, 1.0]);
  const rotSettle = interpolate(press, [0, 1], [restRot - 4, restRot]);
  const opacityIn = interpolate(localFrame, [0, 5], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const ex = easeInCubic(exitProgress);
  const exitScaleV = 1 + 0.06 * ex;
  const exitY = -12 * ex;
  const exitRot = -2 * ex;
  const exitOpacity = interpolate(exitProgress, [0, 0.85], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const finalScale = appear * exitScaleV;
  const finalRot = rotSettle + exitRot;
  const groupOpacity = opacityIn * exitOpacity;

  // --- Badge content ---
  const stampFont =
    fontSizeProp ?? (text.length > 14 ? 58 : text.length > 11 ? 70 : d.fontSize);

  let badge: React.ReactNode;

  if (style === "seal") {
    const W = 560;
    const H = 280;
    const mainFont = fontSizeProp ?? rectFontFit(text.length);
    const grungeId = `grunge-${uid}`;
    const hasSub = Boolean(subtextTop || subtextBottom);
    badge = (
      <svg
        width={size}
        height={(size * H) / W}
        viewBox={`0 0 ${W} ${H}`}
        style={{ overflow: "visible", display: "block" }}
      >
        <defs>
          <filter
            id={grungeId}
            x="-15%"
            y="-15%"
            width="130%"
            height="130%"
            filterUnits="objectBoundingBox"
          >
            {/* roughen the edges */}
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.022"
              numOctaves={2}
              seed={5}
              result="warp"
            />
            <feDisplacementMap
              in="SourceGraphic"
              in2="warp"
              scale={2.5}
              xChannelSelector="R"
              yChannelSelector="G"
              result="rough"
            />
            {/* lightly erode the ink into a few worn patches */}
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.3"
              numOctaves={2}
              seed={9}
              result="speck"
            />
            <feColorMatrix
              in="speck"
              type="matrix"
              values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 4 -0.78"
              result="mask"
            />
            <feComposite in="rough" in2="mask" operator="in" />
          </filter>
        </defs>

        <g filter={`url(#${grungeId})`}>
          <rect
            x={12}
            y={12}
            width={W - 24}
            height={H - 24}
            rx={14}
            fill="none"
            stroke={ink}
            strokeWidth={12}
          />
          {doubleRing ? (
            <rect
              x={30}
              y={30}
              width={W - 60}
              height={H - 60}
              rx={8}
              fill="none"
              stroke={ink}
              strokeWidth={3.5}
            />
          ) : null}

          {subtextTop ? (
            <text
              x={W / 2}
              y={72}
              textAnchor="middle"
              fontFamily={FONT_FAMILY.oswald}
              fontWeight={700}
              fontSize={27}
              letterSpacing={9}
              fill={ink}
            >
              {subtextTop.toUpperCase()}
            </text>
          ) : null}

          <text
            x={W / 2}
            y={hasSub ? 186 : 176}
            textAnchor="middle"
            fontFamily={FONT_FAMILY[fontKey]}
            fontWeight={FONT_WEIGHT[fontKey]}
            fontSize={mainFont}
            letterSpacing={2}
            fill={ink}
          >
            {text.toUpperCase()}
          </text>

          {subtextBottom ? (
            <text
              x={W / 2}
              y={242}
              textAnchor="middle"
              fontFamily={FONT_FAMILY.oswald}
              fontWeight={700}
              fontSize={27}
              letterSpacing={9}
              fill={ink}
            >
              {subtextBottom.toUpperCase()}
            </text>
          ) : null}
        </g>
      </svg>
    );
  } else if (style === "ribbon") {
    badge = (
      <div
        style={{
          minWidth: size,
          height: 96,
          background: color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 64px",
          clipPath:
            "polygon(0 0, 100% 0, calc(100% - 28px) 50%, 100% 100%, 0 100%, 28px 50%)",
        }}
      >
        <div
          style={{
            fontFamily: FONT_FAMILY[fontKey],
            fontWeight: FONT_WEIGHT[fontKey],
            fontSize: stampFont,
            color: textColor ?? "#FFFFFF",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
            lineHeight: 1,
            textShadow,
          }}
        >
          {text}
        </div>
      </div>
    );
  } else {
    badge = (
      <div
        style={{
          minWidth: size,
          border: `7px solid ${color}`,
          borderRadius: 4,
          padding: "18px 30px",
          position: "relative",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 6,
          opacity: 0.95,
          overflow: "hidden",
        }}
      >
        {distress ? (
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: GRAIN,
              pointerEvents: "none",
            }}
          />
        ) : null}
        {doubleRing ? (
          <div
            style={{
              position: "absolute",
              inset: 6,
              border: `2px solid ${color}`,
              borderRadius: 2,
              pointerEvents: "none",
            }}
          />
        ) : null}
        {mark !== "none" ? (
          <div style={{ lineHeight: 0 }}>
            {renderMark(mark, markInk, Math.round(stampFont * 0.6))}
          </div>
        ) : null}
        <div
          style={{
            fontFamily: FONT_FAMILY[fontKey],
            fontWeight: FONT_WEIGHT[fontKey],
            fontSize: stampFont,
            color: ink,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
            lineHeight: 0.95,
            textShadow,
            whiteSpace: "nowrap",
          }}
        >
          {text}
        </div>
        {subtextBottom ? (
          <div style={subStyle(ink, textShadow)}>{subtextBottom}</div>
        ) : null}
      </div>
    );
  }

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            position: "relative",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transform: `translate(0px, ${exitY.toFixed(2)}px) scale(${finalScale.toFixed(4)})`,
            transformOrigin: "center",
            opacity: groupOpacity,
          }}
        >
          {/* Rotation group */}
          <div
            style={{
              position: "relative",
              transform: `rotate(${finalRot}deg)`,
              transformOrigin: "center",
              filter: BADGE_SHADOW,
            }}
          >
            {badge}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

function subStyle(color: string, textShadow: string): React.CSSProperties {
  return {
    fontFamily: MG_FONTS.oswald,
    fontWeight: 600,
    fontSize: 26,
    color,
    letterSpacing: "0.2em",
    textTransform: "uppercase",
    lineHeight: 1,
    opacity: 0.92,
    textShadow,
  };
}
