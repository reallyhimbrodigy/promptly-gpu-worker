import React from "react";
import { AbsoluteFill, interpolate, useVideoConfig } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { StatCardProps } from "./types";
import { useSmoothGraphics } from "../shared/smooth-graphics-flag";
import { cappedEntranceProgress } from "../shared/entrance-cap";
import { MotionBlurWrap } from "../shared/motion-blur";

// ART DIRECTION (2026-08-20) — reference: REF-2's number treatment, §4:
// "the number: full-bleed, cropping off both frame edges, accent-outlined."
// StatCard is the hero-number OVERLAY (no card background — it floats over the
// footage, by design). The craft pass gives that number real presence:
//   • FULL-BLEED — the figure is sized to span the frame width (kissing the
//     edges), adapting to the string so "0" is enormous and "$20,000,000" fills
//     the width. Was a modest fixed 240px centred in open space.
//   • STRUCTURAL ACCENT — a thick accent bar the width of the number, not a 48px
//     hairline. It is the spine the label hangs from, drawn in on the landing.
//   • ANCHORED LABEL — the caps line sits tight under the accent spine, so the
//     three read as ONE object, not a floating centred stack (§4: a stack of
//     centred boxes reads as a slide).
//   • MOTION BLUR — the count-up + scale entrance render through the film-shutter
//     blur (task 2: 30fps smoothness comes from the smear, not linear motion).
// INVARIANTS HELD: tabular-nums, the contrast-floor drop shadow, palette-only
// colours (numberColor/accentColor/labelColor arrive from the job palette), and
// the entrance velocity cap (cappedEntranceProgress). The count-up, eased
// scale-in, landing pulse and rule-draw timings are preserved verbatim.

const LABEL_RATIO = 0.14;   // label cap-height as a fraction of the number size
const AFFIX_RATIO = 0.55;   // prefix/suffix size relative to the number
const ACCENT_HEIGHT_RATIO = 0.045;
const NUMBER_MIN = 210;
const NUMBER_MAX = 470;
const FULL_BLEED_FRAC = 1.0; // span the frame width; outermost strokes kiss the edge

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);

const DEFAULT_TEXT_SHADOW =
  "0 2px 8px rgba(0,0,0,0.85), 0 12px 40px rgba(0,0,0,0.6)";

// Anton is a tall condensed bold; advances estimated in em so the number can be
// sized to a target width without a DOM measure. Separators are narrow.
const antonCharEm = (c: string): number =>
  c === "," || c === "." ? 0.24 : c === " " ? 0.30 : 0.50;
const estWidthEm = (s: string): number =>
  s.split("").reduce((a, c) => a + antonCharEm(c), 0);

export const StatCard: React.FC<StatCardProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  value,
  fromValue = 0,
  prefix,
  suffix,
  decimals,
  label,
  numberColor = "#FFFFFF",
  labelColor = "#FFFFFF",
  accentColor = "#C8551F",
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    undefined,
    "StatCard",
  );
  const { fps, width } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 32, defaultExitFrames: 12 },
  );

  if (!visible) return null;
  // v197 fail-closed: a non-numeric value would paint NaN via the count-up.
  if (typeof value !== "number" || !Number.isFinite(value)) return null;

  // ENTRANCE VELOCITY CAP (unchanged): cappedEntranceProgress is ms-based and
  // profiled so no single delivered frame exceeds the peak-travel cap.
  const smoothEntrance = useSmoothGraphics();
  const enterP = cappedEntranceProgress({ localFrame, fps, authoredFrames: 8 });
  const numberEnterScale = smoothEntrance
    ? 0.92 + 0.08 * enterP
    : interpolate(localFrame, [0, 8], [0.92, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: easeOutCubic,
      });
  const numberFadeIn = smoothEntrance
    ? enterP
    : interpolate(localFrame, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const countProgress = interpolate(localFrame, [4, 24], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const easedCount = easeOutCubic(countProgress);
  const currentValue = fromValue + (value - fromValue) * easedCount;
  const display =
    decimals !== undefined
      ? currentValue.toFixed(decimals)
      : Math.round(currentValue).toLocaleString();

  // FULL-BLEED SIZING (§4). Size the number to the FINAL string's width so the
  // envelope is stable while the count grows into it — the figure never jumps.
  const finalDisplay =
    decimals !== undefined ? value.toFixed(decimals) : Math.round(value).toLocaleString();
  const affixChars = (prefix ? prefix.length : 0) + (suffix ? suffix.length : 0);
  const totalEm =
    estWidthEm(finalDisplay) +
    affixChars * 0.5 * AFFIX_RATIO +
    (prefix ? 0.08 : 0) +
    (suffix ? 0.08 : 0);
  const numberSize = Math.max(
    NUMBER_MIN,
    Math.min(NUMBER_MAX, (width * FULL_BLEED_FRAC) / Math.max(totalEm, 0.5)),
  );
  const affixSize = numberSize * AFFIX_RATIO;
  const affixGap = numberSize * 0.04;
  const labelSize = Math.max(24, numberSize * LABEL_RATIO);
  const accentHeight = Math.max(9, numberSize * ACCENT_HEIGHT_RATIO);
  // The accent spine spans (near) the full number width — a structural bar, not a
  // hairline. Estimated from the final figure so it doesn't grow with the count.
  const accentWidth = numberSize * estWidthEm(finalDisplay) * 0.92;

  const pulseScale = interpolate(localFrame, [24, 27, 30], [1, 1.06, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const ruleScaleX = interpolate(localFrame, [24, 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const labelFadeIn = interpolate(localFrame, [26, 32], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const labelY = interpolate(localFrame, [26, 32], [8, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const exitDriftY = exitProgress * -10;
  const exitOpacity = 1 - exitProgress;

  const affixStyle: React.CSSProperties = {
    fontFamily: MG_FONTS.anton,
    fontSize: affixSize,
    fontWeight: 400,
    letterSpacing: "-0.02em",
    lineHeight: 1,
    opacity: 0.9,
    fontVariantNumeric: "tabular-nums",
  };

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        {/* Blur the WHOLE card as one subtree (count-up + scale + rule-draw).
            Wrapping only the number breaks the flex flow — CameraMotionBlur
            re-lays-out whatever it wraps. */}
        <MotionBlurWrap>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            transform: `translateY(${exitDriftY}px)`,
            opacity: exitOpacity,
          }}
        >
            <div
              style={{
                display: "flex",
                flexDirection: "row",
                alignItems: "baseline",
                justifyContent: "center",
                transform: `scale(${numberEnterScale * pulseScale})`,
                transformOrigin: "center",
                opacity: numberFadeIn,
                fontVariantNumeric: "tabular-nums",
                color: numberColor,
                lineHeight: 1,
                textShadow,
                whiteSpace: "nowrap",
              }}
            >
              {prefix ? (
                <span style={{ ...affixStyle, marginRight: affixGap }}>{prefix}</span>
              ) : null}
              <span
                style={{
                  fontFamily: MG_FONTS.anton,
                  fontSize: numberSize,
                  fontWeight: 400,
                  letterSpacing: "-0.02em",
                  lineHeight: 1,
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {display}
              </span>
              {suffix ? (
                <span style={{ ...affixStyle, marginLeft: affixGap }}>{suffix}</span>
              ) : null}
            </div>

          {/* STRUCTURAL ACCENT — the spine the label hangs from. Draws in on land. */}
          <div
            style={{
              width: accentWidth,
              height: accentHeight,
              backgroundColor: accentColor,
              // Small positive gap below the figure — the original stacking that
              // renders correctly; scaled up for the bigger number. The spine reads
              // as the number's baseline, the label hangs off it.
              marginTop: numberSize * 0.03,
              transform: `scaleX(${ruleScaleX})`,
              transformOrigin: "center",
              boxShadow: "0 3px 10px rgba(0,0,0,0.5)",
              borderRadius: accentHeight / 2,
            }}
          />

          {/* ANCHORED LABEL — tucked tight under the spine; one object, not a stack. */}
          <div
            style={{
              fontFamily: MG_FONTS.inter,
              fontSize: labelSize,
              fontWeight: 700,
              color: labelColor,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              textAlign: "center",
              lineHeight: 1.1,
              marginTop: numberSize * 0.03,
              opacity: labelFadeIn,
              transform: `translateY(${labelY}px)`,
              textShadow,
            }}
          >
            {label}
          </div>
        </div>
        </MotionBlurWrap>
      </div>
    </AbsoluteFill>
  );
};
