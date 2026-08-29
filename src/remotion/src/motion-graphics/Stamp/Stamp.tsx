import React from "react";
import { AbsoluteFill, interpolate, spring, useVideoConfig } from "remotion";
import { mgTextFont, mgTextMetrics } from "../shared/text-font";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { StampFontKey, StampMark, StampProps, StampStyle } from "./types";
import { useSmoothGraphics } from "../shared/smooth-graphics-flag";
import { cappedEntranceProgress } from "../shared/entrance-cap";
import { MotionBlurWrap } from "../shared/motion-blur";


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
  // §4 presence (2026-08-24): REF-2's mark commands the frame — the previous
  // sizes read as a lone sticker floating mid-frame (render-proven). Sized so
  // the default stamp spans ~70% of a 1080 frame the way the reference's
  // number does.
  // Corpus law 1 (pass #7b): a card that lands alone OWNS the frame — REF-2's
  // number runs ~95% width and clips the edge; the 2026-08-25 panel measured
  // ours at ~58% floating in symmetric margins. Tilted corners now approach
  // the 1080 frame edges.
  seal: { fontKey: "oswald", fontSize: 64, mark: "star", distress: false, size: 900 },
  stamp: { fontKey: "anton", fontSize: 84, mark: "none", distress: true, size: 1000 },
  ribbon: { fontKey: "anton", fontSize: 72, mark: "none", distress: false, size: 1040 },
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
// These are VIEWBOX-space sizes (the seal renders in a fixed 560-wide
// viewBox): presence scaling comes from the `size` prop scaling the whole
// SVG, NEVER from these — at 140 the word overflowed the frame and the
// border rects struck through the glyphs ("SOLD" read as "$OLD",
// render-proven 2026-08-24).
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
  // ENTRANCE VELOCITY CAP: this spring is UNDER-damped (damping 10 vs mass 0.8 /
  // stiffness 150), so it bounces — and a bounce is a velocity spike (measured
  // peak_step 0.62 => ~1.6 effective positions). OFF => today's exact bounce.
  const smoothEntrance = useSmoothGraphics();
  const pressSpring = spring({
    fps,
    frame: localFrame,
    config: { damping: 10, mass: 0.8, stiffness: 150 },
  });
  const press = smoothEntrance
    ? cappedEntranceProgress({ localFrame, fps, authoredFrames: 12 })
    : pressSpring;
  const appear = interpolate(press, [0, 1], [entryScale, 1.0]);
  const rotSettle = interpolate(press, [0, 1], [restRot - 4, restRot]);
  // The 5-frame OPACITY ramp — not the spring — is what the presence metric
  // (and the eye) actually tracks: capping only the transform left peak_step
  // unchanged at 0.62. Cap the channel that carries the appearance.
  const opacityIn = smoothEntrance
    ? cappedEntranceProgress({ localFrame, fps, authoredFrames: 5 })
    : interpolate(localFrame, [0, 5], [0, 1], {
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
    fontSizeProp ?? (text.length > 14 ? 78 : text.length > 11 ? 94 : d.fontSize);

  // User/model text routes by script + emoji tail (font census 2026-08-26);
  // caps-transform is gated and tight line boxes open up for non-Latin.
  const textFont = mgTextFont(text, fontKey);
  const textMetrics = mgTextMetrics(text);
  const subTopFont = mgTextFont(subtextTop ?? "", "oswald");
  const subTopMetrics = mgTextMetrics(subtextTop ?? "");
  const subBottomFont = mgTextFont(subtextBottom ?? "", "oswald");
  const subBottomMetrics = mgTextMetrics(subtextBottom ?? "");

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
              fontFamily={subTopFont}
              fontWeight={700}
              fontSize={27}
              letterSpacing={9}
              fill={ink}
            >
              {subTopMetrics.uppercaseSafe ? subtextTop.toUpperCase() : subtextTop}
            </text>
          ) : null}

          <text
            x={W / 2}
            y={hasSub ? 186 : 176}
            textAnchor="middle"
            fontFamily={textFont}
            fontWeight={FONT_WEIGHT[fontKey]}
            fontSize={mainFont}
            letterSpacing={2}
            fill={ink}
          >
            {textMetrics.uppercaseSafe ? text.toUpperCase() : text}
          </text>

          {subtextBottom ? (
            <text
              x={W / 2}
              y={242}
              textAnchor="middle"
              fontFamily={subBottomFont}
              fontWeight={700}
              fontSize={27}
              letterSpacing={9}
              fill={ink}
            >
              {subBottomMetrics.uppercaseSafe
                ? subtextBottom.toUpperCase()
                : subtextBottom}
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
            fontFamily: textFont,
            fontWeight: FONT_WEIGHT[fontKey],
            fontSize: stampFont,
            color: textColor ?? "#FFFFFF",
            letterSpacing: "0.04em",
            textTransform: textMetrics.uppercaseSafe ? "uppercase" : "none",
            lineHeight: Math.max(1, textMetrics.lineHeight),
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
          // Corpus law 2: shock fragments hit at FULL ink — 0.95 read as a
          // watermark on the panel's frames. Distress erodes; alpha doesn't.
          opacity: 1,
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
            fontFamily: textFont,
            fontWeight: FONT_WEIGHT[fontKey],
            fontSize: stampFont,
            color: ink,
            letterSpacing: "0.04em",
            textTransform: textMetrics.uppercaseSafe ? "uppercase" : "none",
            lineHeight:
              textMetrics.script === "latin" ? 0.95 : textMetrics.lineHeight,
            textShadow,
            whiteSpace: "nowrap",
          }}
        >
          {text}
        </div>
        {subtextBottom ? (
          <div style={subStyle(ink, textShadow, subBottomFont, subBottomMetrics)}>
            {subtextBottom}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        {/* The bounce-in press (scale overshoot + rotation settle) renders through
            the film-shutter blur. Wraps the WHOLE self-contained stamp group (the
            only child of wrapperStyle) — never a single flex child, per the
            MotionBlurWrap subtree constraint. */}
        <MotionBlurWrap>
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
            {/* Rotation group. §4 second plane (2026-08-24): a stamp struck
                once is a graphic; struck twice it's a physical act. The ghost
                impression sits BEHIND at an offset + its own small rotation,
                soft and inkier; the crisp strike occludes it. Both live inside
                the press group so they land as one object. Shadow moved onto
                the crisp strike only — the ghost is ink, not an object. */}
            <div
              style={{
                position: "relative",
                transform: `rotate(${finalRot}deg)`,
                transformOrigin: "center",
              }}
            >
              <div
                aria-hidden
                style={{
                  position: "absolute",
                  inset: 0,
                  // Scaled-up rather than laterally offset: a lateral offset
                  // puts the ghost's frame BORDER through the crisp glyphs
                  // (render-proven: "SOLD" read as "$OLD"). Scaling keeps the
                  // ghost frame outside the crisp frame on every side.
                  transform: "translate(7px, 12px) scale(1.05) rotate(2.2deg)",
                  transformOrigin: "center",
                  opacity: 0.14,
                  filter: "blur(1.4px)",
                }}
              >
                {badge}
              </div>
              <div style={{ position: "relative", filter: BADGE_SHADOW }}>
                {badge}
              </div>
            </div>
          </div>
        </MotionBlurWrap>
      </div>
    </AbsoluteFill>
  );
};

function subStyle(
  color: string,
  textShadow: string,
  fontFamily: string,
  metrics: ReturnType<typeof mgTextMetrics>,
): React.CSSProperties {
  return {
    fontFamily,
    fontWeight: 600,
    fontSize: 26,
    color,
    letterSpacing: "0.2em",
    textTransform: metrics.uppercaseSafe ? "uppercase" : "none",
    lineHeight: Math.max(1, metrics.lineHeight),
    opacity: 0.92,
    textShadow,
  };
}
