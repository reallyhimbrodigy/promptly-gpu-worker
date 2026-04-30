import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { TornPaperProps } from "./types";

// Spring tuning. Paper drop is moderately damped for a clean settle; the
// two strips use a softer damping that gives ~15% overshoot — that's the
// "slam and bounce" feel that makes torn-paper cards land instead of fade.
// Damping ratio ζ = damping / (2·√(stiffness·mass)).
const PAPER_SPRING = { damping: 14, stiffness: 110, mass: 1.2 };
const STRIP_SPRING = { damping: 11, stiffness: 140, mass: 1.0 };

export const TornPaper: React.FC<TornPaperProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  anchor,
  offsetX,
  offsetY,
  scale,
  topText,
  bottomText,
  topStripRotation = -10,
  bottomStripRotation = 7,
  stripColor = "#1A1A1A",
  stripTextColor = "#FFFFFF",
  shadowColor = "#4CAF50",
  shadowOffsetX = 10,
  shadowOffsetY = 9,
  stripFontFamily = MG_FONTS.oswald,
  stripFontSize = 72,
  stripFontWeight = 700,
  stripLetterSpacing = "0.06em",
  stripPadding = [14, 32],
  stripGap = 120,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const { visible, localFrame, exitProgress, phase } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 26, defaultExitFrames: 14 },
  );
  if (!visible) return null;

  const isExiting = phase === "exiting" || phase === "after";

  // ── ENTRANCE ──────────────────────────────────────────────────────────
  // Paper sheet drops from above the frame. Spring config gives a clean
  // arrival with a tiny settle — no bounce on the banner itself, since
  // the banner texture sells the impact, not the motion.
  const paperEnter = spring({
    frame: localFrame,
    fps,
    config: PAPER_SPRING,
    durationInFrames: 26,
  });

  // Strips slam in from off-screen sides with a bouncy spring (≈15%
  // overshoot). The second strip is staggered 4 frames behind the first
  // for the layered "thwack thwack" cadence.
  const strip1Enter = spring({
    frame: localFrame - 6,
    fps,
    config: STRIP_SPRING,
    durationInFrames: 22,
  });
  const strip2Enter = spring({
    frame: localFrame - 10,
    fps,
    config: STRIP_SPRING,
    durationInFrames: 22,
  });

  // ── EXIT ──────────────────────────────────────────────────────────────
  // Mirror of entrance but ~55% the duration — research convention is
  // "exits 25–30% faster than entrances" but for a slammed card,
  // committing to a quick exit reads cleaner. Ease-in cubic so the
  // exit accelerates out (the inverse of spring-deceleration in).
  const exitEased = Easing.bezier(0.4, 0, 1, 1)(exitProgress);

  // Paper rises out the top.
  const paperEnterY = interpolate(paperEnter, [0, 1], [-110, 0], {
    extrapolateRight: "clamp",
  });
  const paperExitY = interpolate(exitEased, [0, 1], [0, -110]);
  const paperY = isExiting ? paperEnterY + paperExitY : paperEnterY;
  const paperOpacity =
    paperEnter * (isExiting ? 1 - exitEased : 1);

  // Strip 1 entrance: comes in from the right; on exit, leaves to the right.
  const s1EnterX = interpolate(strip1Enter, [0, 1], [600, 0], {
    extrapolateRight: "clamp",
  });
  const s1EnterY = interpolate(strip1Enter, [0, 1], [-40, 0], {
    extrapolateRight: "clamp",
  });
  const s1ExitX = interpolate(exitEased, [0, 1], [0, 600]);
  const s1X = isExiting ? s1EnterX + s1ExitX : s1EnterX;
  const s1Y = s1EnterY;
  const s1Opacity = strip1Enter * (isExiting ? 1 - exitEased : 1);

  // Strip 2 entrance: from the left; exits left.
  const s2EnterX = interpolate(strip2Enter, [0, 1], [-600, 0], {
    extrapolateRight: "clamp",
  });
  const s2EnterY = interpolate(strip2Enter, [0, 1], [40, 0], {
    extrapolateRight: "clamp",
  });
  const s2ExitX = interpolate(exitEased, [0, 1], [0, -600]);
  const s2X = isExiting ? s2EnterX + s2ExitX : s2EnterX;
  const s2Y = s2EnterY;
  const s2Opacity = strip2Enter * (isExiting ? 1 - exitEased : 1);

  // ── POSITIONING ───────────────────────────────────────────────────────
  // Honor `anchor` from the placement system. Default to "center" because
  // a torn-paper card is typically a chapter beat planted in the middle of
  // the frame — that's its visual identity.
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center" },
  );

  const dotTexture = {
    backgroundImage: `
      radial-gradient(circle, rgba(255,255,255,0.15) 1.5px, transparent 1.5px),
      radial-gradient(circle, rgba(255,255,255,0.05) 1.5px, transparent 1.5px),
      radial-gradient(circle, rgba(255,255,255,0.10) 1.5px, transparent 1.5px)
    `,
    backgroundSize: "10px 10px, 10px 10px, 10px 10px",
    backgroundPosition: "0px 0px, 5px 5px, 3px 8px",
  };

  const textStyle: React.CSSProperties = {
    fontFamily: stripFontFamily,
    fontSize: stripFontSize,
    fontWeight: stripFontWeight,
    color: stripTextColor,
    textTransform: "uppercase",
    letterSpacing: stripLetterSpacing,
    lineHeight: 1.1,
    whiteSpace: "nowrap",
  };

  return (
    <AbsoluteFill style={containerStyle}>
      <div
        style={{
          ...wrapperStyle,
          width: "100%",
          position: "relative",
        }}
      >
        {/* Paper banner — full-width sheet that drops from above */}
        <div
          style={{
            position: "relative",
            width: "100%",
            transform: `translateY(${paperY}%)`,
            opacity: paperOpacity,
          }}
        >
          <Img
            src={staticFile("torn-paper.png")}
            style={{ width: "100%", display: "block" }}
          />
        </div>

        {/* Strips — absolute-positioned over the banner so they overlap visually */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: stripGap,
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              position: "relative",
              display: "inline-block",
              transform: `translate(${s1X}px, ${s1Y}px) rotate(${topStripRotation}deg)`,
              opacity: s1Opacity,
            }}
          >
            <div
              style={{
                position: "absolute",
                top: shadowOffsetY,
                left: shadowOffsetX,
                width: "100%",
                height: "100%",
                backgroundColor: shadowColor,
              }}
            />
            <div
              style={{
                position: "relative",
                backgroundColor: stripColor,
                ...dotTexture,
                padding: `${stripPadding[0]}px ${stripPadding[1]}px`,
              }}
            >
              <span style={textStyle}>{topText}</span>
            </div>
          </div>

          <div
            style={{
              position: "relative",
              display: "inline-block",
              marginLeft: 10,
              transform: `translate(${s2X}px, ${s2Y}px) rotate(${bottomStripRotation}deg)`,
              opacity: s2Opacity,
            }}
          >
            <div
              style={{
                position: "absolute",
                top: shadowOffsetY,
                left: shadowOffsetX,
                width: "100%",
                height: "100%",
                backgroundColor: shadowColor,
              }}
            />
            <div
              style={{
                position: "relative",
                backgroundColor: stripColor,
                ...dotTexture,
                padding: `${stripPadding[0]}px ${stripPadding[1]}px`,
              }}
            >
              <span style={textStyle}>{bottomText}</span>
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
