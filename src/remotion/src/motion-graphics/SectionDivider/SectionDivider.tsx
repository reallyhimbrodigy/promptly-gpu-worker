import React from "react";
import { AbsoluteFill, interpolate, useVideoConfig } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import { mgSchedule } from "../shared/schedule";
import type { SectionDividerFontKey, SectionDividerProps } from "./types";
import { asText } from "../../shared/asText";


const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);
const easeInOutCubic = (t: number): number =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const easeOutBack = (t: number): number => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};

// 680 = the position resolver's symmetric safe box (1080 − 2×200); the old 840
// exceeded it, so wide lines ran under the TikTok action rail (pass #9).
const CONTENT_MAX_WIDTH = 680;
const NUMBER_SIZE = 110;
const EYEBROW_SIZE = 36;
const RULE_THICKNESS = 3;
const BAND_HEIGHT = 560;

const DEFAULT_TEXT_SHADOW =
  "0 2px 12px rgba(0,0,0,0.55), 0 14px 48px rgba(0,0,0,0.45)";
const RULE_SHADOW = "0 2px 8px rgba(0,0,0,0.5)";

const FONT_FAMILY: Record<SectionDividerFontKey, string> = {
  anton: MG_FONTS.anton,
  dmSerifDisplay: MG_FONTS.dmSerifDisplay,
  playfairDisplay: MG_FONTS.playfairDisplay,
  oswald: MG_FONTS.oswald,
};

export const SectionDivider: React.FC<SectionDividerProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  title,
  label,
  number,
  fontKey = "anton",
  align = "center",
  variant = "full",
  titleColor = "#FFFFFF",
  accentColor = "#C8551F",
  eyebrowColor,
  numberColor,
  titleFontSize = 150,
  showRule = true,
  showScrim = true,
  scrimColor = "rgba(0,0,0,0.55)",
  showVignette = true,
  vignetteStrength = 0.6,
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center" },
  );
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress, exitStartFrame } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 50, defaultExitFrames: 24 },
  );

  if (!visible) return null;

  // Pass #9 — corpus law 2: eyebrow + number + rule all defaulted to the
  // accent (three simultaneous chroma elements). The NUMBER is the beat's one
  // hit; the eyebrow defaults to neutral ink; the hairline rule stays accent
  // chrome.
  const ebColor = eyebrowColor ?? "rgba(255,255,255,0.78)";
  const numColor = numberColor ?? accentColor;
  const isSerif = fontKey === "dmSerifDisplay" || fontKey === "playfairDisplay";
  const isLeft = align === "left";
  const lines = asText(title).split("\n");

  // Script routing (pass #9, render-caught): the display faces are latin-only —
  // the live Devanagari title fell back to an unstyled system face, with matras
  // clipped at lineHeight 1.0 under the reveal mask. Detect by Unicode range
  // (the standing rule: detect by script, never by language tag).
  const isDevanagari = /[ऀ-ॿ]/.test(asText(title));
  const titleFontFamily = isDevanagari
    ? MG_FONTS.notoSansDevanagari
    : FONT_FAMILY[fontKey];
  const titleLineHeight = isDevanagari ? 1.3 : isSerif ? 1.08 : 1.0;

  // Width-driven autofit (the EditorialQuote recipe): the title GROWS to the
  // safe box and can never overflow it. Per-script advance estimates are
  // deliberate over-estimates — text may never crop.
  let maxChars = 1;
  for (const l of lines) maxChars = Math.max(maxChars, [...l].length);
  const advance = isDevanagari ? 0.4 : isSerif ? 0.58 : 0.52;
  const fitTitleSize = Math.round(
    Math.max(56, Math.min(CONTENT_MAX_WIDTH / (maxChars * advance), 170)),
  );

  // Duration-aware fps-relative schedule (the DropCard recipe via mgSchedule):
  // the authored 60fps choreography compresses so the last title reveal
  // completes by 85% of the pre-exit window — the live 1.52s placement showed
  // the title only mid-translate, half-clipped, AFTER exit had begun.
  const K = mgSchedule({
    fps,
    window: exitStartFrame,
    authoredEnd: 42 + 8 * (lines.length - 1),
  });

  // --- Scrim ---
  const scrimEnter = interpolate(localFrame, [K(0), K(18)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });
  const scrimExit = interpolate(exitProgress, [0.2, 1], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const scrimOpacity = scrimEnter * scrimExit;

  // --- Rule ---
  const ruleEnter = interpolate(localFrame, [K(4), K(22)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });
  const ruleRetract = interpolate(exitProgress, [0, 0.55], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeInOutCubic,
  });
  const ruleScaleX = ruleEnter * (1 - ruleRetract);
  const ruleOpacity = interpolate(localFrame, [K(4), K(12)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // --- Number ---
  const numScale = interpolate(localFrame, [K(10), K(28)], [0.7, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutBack,
  });
  const numEnterO = interpolate(localFrame, [K(10), K(22)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const numExitO = interpolate(exitProgress, [0, 0.5], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const numTY = interpolate(localFrame, [K(10), K(24)], [10, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });

  // --- Eyebrow ---
  const ebEnterO = interpolate(localFrame, [K(16), K(30)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const ebTYenter = interpolate(localFrame, [K(16), K(30)], [14, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });
  const ebExitO = interpolate(exitProgress, [0, 0.5], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const ebExitTY = interpolate(exitProgress, [0, 0.6], [0, -18], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeInOutCubic,
  });

  // --- Content block global exit drift ---
  const blockY = interpolate(exitProgress, [0, 1], [0, -10], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // --- Band ---
  const bandScaleY = interpolate(localFrame, [K(0), K(16)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });
  const bandOpacity =
    interpolate(localFrame, [K(0), K(10)], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }) * scrimExit;

  const crossAlign = isLeft ? "flex-start" : "center";

  const vig = Math.max(0, Math.min(1, vignetteStrength));

  return (
    <AbsoluteFill style={containerStyle}>
      {/* Cinematic 4-corner vignette (darkens each corner) */}
      {showVignette ? (
        <AbsoluteFill
          style={{
            background: [
              `radial-gradient(circle at top left, rgba(0,0,0,${vig}) 0%, transparent 42%)`,
              `radial-gradient(circle at top right, rgba(0,0,0,${vig}) 0%, transparent 42%)`,
              `radial-gradient(circle at bottom left, rgba(0,0,0,${vig}) 0%, transparent 42%)`,
              `radial-gradient(circle at bottom right, rgba(0,0,0,${vig}) 0%, transparent 42%)`,
            ].join(", "),
            opacity: scrimOpacity,
          }}
        />
      ) : null}

      {/* Full-frame vignette scrim (behind, not anchored/scaled) */}
      {showScrim && variant === "full" ? (
        <AbsoluteFill
          style={{
            background: `radial-gradient(135% 62% at 50% 50%, ${scrimColor} 0%, ${scrimColor} 38%, transparent 76%)`,
            opacity: scrimOpacity,
          }}
        />
      ) : null}

      {/* Centered letterbox band */}
      {variant === "band" ? (
        <AbsoluteFill
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              width: "100%",
              height: BAND_HEIGHT,
              backgroundColor: scrimColor,
              opacity: bandOpacity,
              transform: `scaleY(${bandScaleY})`,
              transformOrigin: "center",
            }}
          />
        </AbsoluteFill>
      ) : null}

      <div style={wrapperStyle}>
        <div
          style={{
            width: CONTENT_MAX_WIDTH,
            display: "flex",
            flexDirection: "column",
            alignItems: crossAlign,
            transform: `translateY(${blockY}px)`,
          }}
        >
          {/* Number */}
          {number ? (
            <div
              style={{
                fontFamily: FONT_FAMILY[fontKey],
                fontSize: NUMBER_SIZE,
                fontWeight: 400,
                color: numColor,
                lineHeight: 1,
                fontVariantNumeric: "tabular-nums",
                marginBottom: 12,
                opacity: numEnterO * numExitO,
                transform: `translateY(${numTY}px) scale(${numScale})`,
                transformOrigin: isLeft ? "left center" : "center",
                textShadow,
              }}
            >
              {number}
            </div>
          ) : null}

          {/* Eyebrow */}
          {label ? (
            <div
              style={{
                fontFamily: MG_FONTS.inter,
                fontSize: EYEBROW_SIZE,
                fontWeight: 600,
                color: ebColor,
                letterSpacing: "0.3em",
                textTransform: "uppercase",
                lineHeight: 1.2,
                marginBottom: 28,
                opacity: ebEnterO * ebExitO,
                transform: `translateY(${ebTYenter + ebExitTY}px)`,
                textShadow,
              }}
            >
              {label}
            </div>
          ) : null}

          {/* Accent rule */}
          {showRule ? (
            <div
              style={{
                width: isLeft ? 200 : 160,
                height: RULE_THICKNESS,
                backgroundColor: accentColor,
                marginBottom: 28,
                opacity: ruleOpacity,
                transform: `scaleX(${ruleScaleX})`,
                transformOrigin: isLeft ? "left center" : "center",
                boxShadow: RULE_SHADOW,
              }}
            />
          ) : null}

          {/* Title lines (percent-translate masks) */}
          {lines.map((line, li) => {
            const revealP = interpolate(
              localFrame,
              [K(24 + 8 * li), K(42 + 8 * li)],
              [0, 1],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: easeOutCubic,
              },
            );
            const enterTY = (1 - revealP) * 100;
            const exitTYp = interpolate(exitProgress, [0, 0.7], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeInOutCubic,
            });
            const lineTY = enterTY - 100 * exitTYp;
            const lineEnterO = interpolate(
              localFrame,
              [K(24 + 8 * li), K(32 + 8 * li)],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );
            const lineExitO = interpolate(exitProgress, [0.45, 0.8], [1, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });

            return (
              <div
                key={li}
                style={{
                  // The mask keys off REVEAL COMPLETION, not the phase label
                  // (pass #9): 'holding' was unreachable whenever the computed
                  // enter window outlived the pre-exit window, so the mask
                  // never lifted — fallback-face matras stayed clipped for the
                  // component's whole life, and the old holding→exiting flip
                  // re-clipped settled text with a visible pop.
                  overflow: revealP >= 1 ? "visible" : "hidden",
                  maxWidth: CONTENT_MAX_WIDTH,
                }}
              >
                <div
                  style={{
                    fontFamily: titleFontFamily,
                    fontSize: fitTitleSize,
                    fontWeight: 400,
                    color: titleColor,
                    letterSpacing: isSerif || isDevanagari ? "0" : "-0.01em",
                    lineHeight: titleLineHeight,
                    textTransform: isDevanagari ? "none" : "uppercase",
                    textAlign: isLeft ? "left" : "center",
                    whiteSpace: "nowrap",
                    opacity: lineEnterO * lineExitO,
                    transform: `translateY(${lineTY}%)`,
                    textShadow,
                  }}
                >
                  {line}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
